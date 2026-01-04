"""
ComputeSwarm Seller Agent
Queue-based job polling, claiming, and execution with x402 payments
"""

import asyncio
import sys
import signal
from typing import Optional
from datetime import datetime
from decimal import Decimal
import httpx
import structlog

from src.compute.gpu_detector import GPUDetector
from src.marketplace.models import NodeRegistration, GPUType
from src.config import get_seller_config
from src.execution import JobExecutor
from src.payments import PaymentProcessor, calculate_job_cost, calculate_estimated_cost

logger = structlog.get_logger()


class SellerAgent:
    """
    Queue-based Seller Agent that:
    1. Detects local GPU hardware
    2. Registers with the marketplace
    3. Polls job queue for matching jobs
    4. Claims jobs atomically
    5. Executes jobs with safety controls
    6. Processes payments and reports results
    """

    def __init__(self):
        self.config = get_seller_config()
        self.node_id: Optional[str] = None
        self.gpu_info = None
        self.price_per_hour: Optional[Decimal] = None
        self.running = False
        self.is_busy = False
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Initialize job executor with Docker sandboxing config
        self.executor = JobExecutor(
            docker_enabled=self.config.docker_enabled,
            docker_image=self.config.docker_image,
            docker_memory_limit=self.config.docker_memory_limit,
            docker_cpu_limit=self.config.docker_cpu_limit,
            docker_pids_limit=self.config.docker_pids_limit,
            docker_tmpfs_size=self.config.docker_tmpfs_size
        )
        
        # Initialize payment processor if private key is available
        self.payment_processor: Optional[PaymentProcessor] = None
        if self.config.seller_private_key:
            self.payment_processor = PaymentProcessor(
                private_key=self.config.seller_private_key,
                rpc_url=self.config.rpc_url,
                usdc_address=self.config.usdc_contract_address,
                network=self.config.network,
                testnet_mode=self.config.testnet_mode,
            )
            logger.info(
                "payment_processor_initialized", 
                address=self.payment_processor.address,
                testnet_mode=self.config.testnet_mode
            )

    async def start(self):
        """Start the seller agent"""
        logger.info("seller_agent_starting", seller=self.config.seller_address)

        # Detect GPU
        self.gpu_info = GPUDetector.detect_gpu()
        logger.info(
            "gpu_detected",
            gpu_type=self.gpu_info.gpu_type.value,
            device_name=self.gpu_info.device_name,
            vram_gb=float(self.gpu_info.vram_gb) if self.gpu_info.vram_gb else None
        )

        # Test GPU
        if not GPUDetector.test_gpu():
            logger.error("gpu_test_failed", message="GPU is not functioning properly")
            sys.exit(1)

        # Determine pricing based on GPU type
        if self.gpu_info.gpu_type.value == "cuda":
            self.price_per_hour = Decimal(str(self.config.default_price_per_hour_cuda))
        elif self.gpu_info.gpu_type.value == "mps":
            self.price_per_hour = Decimal(str(self.config.default_price_per_hour_mps))
        else:
            self.price_per_hour = Decimal("0.10")  # Default low price for CPU

        # Register with marketplace
        await self.register()

        # Start background tasks
        self.running = True
        asyncio.create_task(self.heartbeat_loop())
        asyncio.create_task(self.job_polling_loop())

        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.stop()

    async def register(self):
        """Register node with marketplace"""
        try:
            registration = NodeRegistration(
                seller_address=self.config.seller_address,
                gpu_info=self.gpu_info,
                price_per_hour=self.price_per_hour,
                endpoint=""  # Not used in queue-based system
            )

            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/nodes/register",
                json=registration.model_dump()
            )
            response.raise_for_status()

            data = response.json()
            self.node_id = data["node_id"]

            logger.info(
                "registered_with_marketplace",
                node_id=self.node_id,
                price_per_hour=float(self.price_per_hour),
                marketplace_url=self.config.marketplace_url
            )

        except Exception as e:
            logger.error("registration_failed", error=str(e))
            sys.exit(1)

    async def heartbeat_loop(self):
        """Send periodic heartbeats to marketplace"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Heartbeat every 30 seconds

                if not self.node_id:
                    continue

                response = await self.client.post(
                    f"{self.config.marketplace_url}/api/v1/nodes/{self.node_id}/heartbeat",
                    params={"available": not self.is_busy}
                )
                response.raise_for_status()

                logger.debug("heartbeat_sent", node_id=self.node_id, available=not self.is_busy)

            except Exception as e:
                logger.warning("heartbeat_failed", error=str(e))

    async def job_polling_loop(self):
        """Poll job queue for available jobs"""
        while self.running:
            try:
                # Only poll if not busy
                if not self.is_busy:
                    await self.try_claim_job()

                # Poll every 5 seconds when idle
                await asyncio.sleep(5)

            except Exception as e:
                logger.error("job_polling_error", error=str(e))
                await asyncio.sleep(10)  # Back off on error

    async def try_claim_job(self):
        """Try to claim a job from the queue"""
        if not self.node_id:
            return

        try:
            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/claim",
                params={
                    "node_id": self.node_id,
                    "seller_address": self.config.seller_address,
                    "gpu_type": self.gpu_info.gpu_type.value,
                    "price_per_hour": float(self.price_per_hour),
                    "vram_gb": float(self.gpu_info.vram_gb) if self.gpu_info.vram_gb else 0.0,
                    "num_gpus": self.gpu_info.num_gpus if hasattr(self.gpu_info, 'num_gpus') else 1
                }
            )
            response.raise_for_status()

            data = response.json()

            if data.get("claimed"):
                # Job claimed! Execute it
                job_id = data["job_id"]
                script = data["script"]
                requirements = data.get("requirements")
                timeout_seconds = data["timeout_seconds"]
                max_price_per_hour = Decimal(str(data["max_price_per_hour"]))
                buyer_address = data.get("buyer_address", "")

                logger.info(
                    "job_claimed_from_queue",
                    job_id=job_id,
                    timeout=timeout_seconds,
                    max_price=float(max_price_per_hour),
                    buyer=buyer_address
                )

                # Execute job in background
                asyncio.create_task(self.execute_job(
                    job_id=job_id,
                    script=script,
                    requirements=requirements,
                    timeout_seconds=timeout_seconds,
                    max_price_per_hour=max_price_per_hour,
                    buyer_address=buyer_address
                ))

        except Exception as e:
            logger.warning("job_claim_failed", error=str(e))

    async def execute_job(
        self,
        job_id: str,
        script: str,
        requirements: Optional[str],
        timeout_seconds: int,
        max_price_per_hour: Decimal,
        buyer_address: str = ""
    ):
        """Execute a claimed job with payment processing"""
        self.is_busy = True

        try:
            # Pre-authorization: Check buyer can pay estimated cost BEFORE execution
            if self.payment_processor and buyer_address:
                estimated_cost = calculate_estimated_cost(
                    timeout_seconds=timeout_seconds,
                    price_per_hour=self.price_per_hour
                )
                
                try:
                    buyer_balance = self.payment_processor.get_usdc_balance(buyer_address)
                    
                    if buyer_balance < estimated_cost:
                        logger.warning(
                            "insufficient_buyer_balance",
                            job_id=job_id,
                            buyer=buyer_address,
                            balance=float(buyer_balance),
                            required=float(estimated_cost)
                        )
                        await self.fail_job(
                            job_id=job_id,
                            error=f"Insufficient USDC balance: {buyer_balance:.6f} < {estimated_cost:.6f} required"
                        )
                        return
                    
                    logger.info(
                        "pre_authorization_passed",
                        job_id=job_id,
                        buyer=buyer_address,
                        balance=float(buyer_balance),
                        estimated_cost=float(estimated_cost)
                    )
                except Exception as e:
                    logger.warning(
                        "pre_authorization_check_failed",
                        job_id=job_id,
                        error=str(e)
                    )
                    # Continue execution if balance check fails - will catch at settlement

            # Notify marketplace that execution is starting
            await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}/start"
            )

            logger.info("job_execution_starting", job_id=job_id)

            # Execute the job
            result = await self.executor.execute_job(
                job_id=job_id,
                script=script,
                requirements=requirements,
                timeout_seconds=timeout_seconds
            )

            # Calculate cost using per-second billing
            cost_usd, cost_usdc_wei = calculate_job_cost(
                execution_time_seconds=result.execution_time,
                price_per_hour=self.price_per_hour
            )

            logger.info(
                "job_execution_finished",
                job_id=job_id,
                success=result.success,
                exit_code=result.exit_code,
                duration_seconds=float(result.execution_time),
                cost_usd=float(cost_usd),
                cost_usdc_wei=cost_usdc_wei
            )

            # Report results
            if result.success:
                await self.complete_job(
                    job_id=job_id,
                    output=result.output,
                    exit_code=result.exit_code,
                    execution_duration=result.execution_time,
                    total_cost=cost_usd,
                    cost_usdc_wei=cost_usdc_wei,
                    buyer_address=buyer_address
                )
            else:
                await self.fail_job(
                    job_id=job_id,
                    error=result.error,
                    exit_code=result.exit_code,
                    execution_duration=result.execution_time
                )

        except Exception as e:
            logger.error("job_execution_error", job_id=job_id, error=str(e))
            await self.fail_job(
                job_id=job_id,
                error=f"Internal execution error: {str(e)}"
            )

        finally:
            self.is_busy = False

    async def complete_job(
        self,
        job_id: str,
        output: str,
        exit_code: int,
        execution_duration: Decimal,
        total_cost: Decimal,
        cost_usdc_wei: int = 0,
        buyer_address: str = ""
    ):
        """Report job completion to marketplace with payment settlement"""
        payment_tx_hash = None
        payment_status = "success"
        
        try:
            # Process payment if payment processor is available
            if self.payment_processor and buyer_address and cost_usdc_wei > 0:
                # Re-check buyer balance before settlement (edge case: buyer spent during execution)
                try:
                    cost_usdc = Decimal(cost_usdc_wei) / Decimal(10**6)
                    buyer_balance = self.payment_processor.get_usdc_balance(buyer_address)
                    
                    if buyer_balance < cost_usdc:
                        logger.warning(
                            "buyer_balance_insufficient_at_settlement",
                            job_id=job_id,
                            buyer=buyer_address,
                            balance=float(buyer_balance),
                            required=float(cost_usdc)
                        )
                        payment_status = "insufficient_funds"
                        # Continue to report job completion but mark payment as failed
                except Exception as e:
                    logger.warning("balance_recheck_failed", job_id=job_id, error=str(e))
                
                if payment_status == "success":
                    logger.info(
                        "processing_payment",
                        job_id=job_id,
                        buyer=buyer_address,
                        amount_usdc_wei=cost_usdc_wei
                    )
                    
                    receipt = await self.payment_processor.settle_payment(
                        from_address=buyer_address,
                        amount=cost_usdc_wei,
                        job_id=job_id
                    )
                    
                    if receipt.success:
                        payment_tx_hash = receipt.tx_hash
                        logger.info(
                            "payment_settled",
                            job_id=job_id,
                            tx_hash=payment_tx_hash,
                            amount=cost_usdc_wei
                        )
                    else:
                        payment_status = "settlement_failed"
                        logger.warning(
                            "payment_settlement_failed",
                            job_id=job_id,
                            error=receipt.error
                        )

            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}/complete",
                params={
                    "job_id": job_id,
                    "output": output,
                    "exit_code": exit_code,
                    "execution_duration": float(execution_duration),
                    "total_cost": float(total_cost),
                    "payment_tx_hash": payment_tx_hash
                }
            )
            response.raise_for_status()

            logger.info(
                "job_completion_reported",
                job_id=job_id,
                cost_usd=float(total_cost),
                payment_tx_hash=payment_tx_hash
            )

        except Exception as e:
            logger.error("job_completion_report_failed", job_id=job_id, error=str(e))

    async def fail_job(
        self,
        job_id: str,
        error: str,
        exit_code: Optional[int] = None,
        execution_duration: Optional[Decimal] = None
    ):
        """Report job failure to marketplace"""
        try:
            params = {
                "job_id": job_id,
                "error": error
            }

            if exit_code is not None:
                params["exit_code"] = exit_code
            if execution_duration is not None:
                params["execution_duration"] = float(execution_duration)

            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}/fail",
                params=params
            )
            response.raise_for_status()

            logger.info("job_failure_reported", job_id=job_id)

        except Exception as e:
            logger.error("job_failure_report_failed", job_id=job_id, error=str(e))

    async def stop(self):
        """Gracefully shut down the seller agent"""
        logger.info("seller_agent_stopping", node_id=self.node_id)

        self.running = False

        # Mark node as unavailable
        if self.node_id:
            try:
                await self.client.post(
                    f"{self.config.marketplace_url}/api/v1/nodes/{self.node_id}/unavailable"
                )
                logger.info("node_marked_unavailable", node_id=self.node_id)
            except Exception as e:
                logger.warning("node_unavailable_failed", error=str(e))

        await self.client.aclose()
        logger.info("seller_agent_stopped")


async def main():
    """Main entry point for seller agent"""
    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer()
        ]
    )

    agent = SellerAgent()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info("shutdown_signal_received", signal=sig)
        asyncio.create_task(agent.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    await agent.start()


if __name__ == "__main__":
    asyncio.run(main())
