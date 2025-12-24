"""
ComputeSwarm Seller Agent
Queue-based job polling, claiming, and execution
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

logger = structlog.get_logger()


class SellerAgent:
    """
    Queue-based Seller Agent that:
    1. Detects local GPU hardware
    2. Registers with the marketplace
    3. Polls job queue for matching jobs
    4. Claims jobs atomically
    5. Executes jobs with safety controls
    6. Reports results and handles payment
    """

    def __init__(self):
        self.config = get_seller_config()
        self.node_id: Optional[str] = None
        self.gpu_info = None
        self.price_per_hour: Optional[Decimal] = None
        self.running = False
        self.is_busy = False
        self.client = httpx.AsyncClient(timeout=30.0)
        self.executor = JobExecutor()

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
            self.price_per_hour = self.config.default_price_per_hour_cuda
        elif self.gpu_info.gpu_type.value == "mps":
            self.price_per_hour = self.config.default_price_per_hour_mps
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
                    "vram_gb": float(self.gpu_info.vram_gb) if self.gpu_info.vram_gb else 0.0
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

                logger.info(
                    "job_claimed_from_queue",
                    job_id=job_id,
                    timeout=timeout_seconds,
                    max_price=float(max_price_per_hour)
                )

                # Execute job in background
                asyncio.create_task(self.execute_job(
                    job_id=job_id,
                    script=script,
                    requirements=requirements,
                    timeout_seconds=timeout_seconds,
                    max_price_per_hour=max_price_per_hour
                ))

        except Exception as e:
            logger.warning("job_claim_failed", error=str(e))

    async def execute_job(
        self,
        job_id: str,
        script: str,
        requirements: Optional[str],
        timeout_seconds: int,
        max_price_per_hour: Decimal
    ):
        """Execute a claimed job"""
        self.is_busy = True

        try:
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

            # Calculate cost
            hours = result.execution_time / Decimal("3600")  # Convert seconds to hours
            total_cost = hours * self.price_per_hour

            logger.info(
                "job_execution_finished",
                job_id=job_id,
                success=result.success,
                exit_code=result.exit_code,
                duration=float(result.execution_time),
                cost=float(total_cost)
            )

            # Report results
            if result.success:
                await self.complete_job(
                    job_id=job_id,
                    output=result.output,
                    exit_code=result.exit_code,
                    execution_duration=result.execution_time,
                    total_cost=total_cost
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
        total_cost: Decimal
    ):
        """Report job completion to marketplace"""
        try:
            # TODO: Implement x402 payment verification and get tx hash
            payment_tx_hash = None

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
                cost=float(total_cost)
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
