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
    7. Tracks and displays earnings
    """

    def __init__(self):
        self.config = get_seller_config()
        self.node_id: Optional[str] = None
        self.gpu_info = None
        self.price_per_hour: Optional[Decimal] = None
        self.running = False
        self.is_busy = False
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Earnings tracking (session-only)
        self.session_earnings = Decimal("0")
        self.session_jobs_completed = 0
        self.session_jobs_failed = 0
        self.session_start_time: Optional[datetime] = None
        
        # Job executor will be initialized after GPU detection
        self.executor: Optional[JobExecutor] = None
        
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
        
        # Initialize job executor with GPU-aware configuration
        from pathlib import Path
        model_cache_path = Path(self.config.model_cache_dir).expanduser()
        
        self.executor = JobExecutor(
            docker_enabled=self.config.docker_enabled,
            docker_image=self.config.docker_image,
            docker_image_gpu=self.config.docker_image_gpu,
            docker_memory_limit=self.config.docker_memory_limit,
            docker_cpu_limit=self.config.docker_cpu_limit,
            docker_pids_limit=self.config.docker_pids_limit,
            docker_tmpfs_size=self.config.docker_tmpfs_size,
            model_cache_dir=model_cache_path if self.config.model_cache_enabled else None,
            gpu_type=self.gpu_info.gpu_type.value
        )
        
        logger.info(
            "executor_initialized",
            docker_enabled=self.config.docker_enabled,
            gpu_type=self.gpu_info.gpu_type.value,
            model_cache=str(model_cache_path) if self.config.model_cache_enabled else None
        )
        
        # Docker health check
        await self._check_docker_setup()

        # Register with marketplace
        await self.register()

        # Start background tasks
        self.running = True
        self.session_start_time = datetime.now()
        
        asyncio.create_task(self.heartbeat_loop())
        asyncio.create_task(self.job_polling_loop())
        asyncio.create_task(self.earnings_display_loop())

        # Display initial status
        self._display_status()

        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.stop()

    async def _check_docker_setup(self):
        """
        Check Docker availability and image status
        Provides helpful guidance if Docker is not properly configured
        """
        if not self.config.docker_enabled:
            logger.warning(
                "docker_disabled",
                message="Docker sandboxing is disabled. Jobs will run without isolation."
            )
            return
        
        # Check Docker availability
        docker_available = await self.executor._check_docker_available()
        
        if not docker_available:
            logger.error(
                "docker_not_available",
                message="Docker is not available. Please install Docker or disable sandboxing.",
                help="Run: ./scripts/setup_seller.sh"
            )
            print("\n" + "="*60)
            print("ERROR: Docker is not available")
            print("="*60)
            print("\nDocker is required for secure job execution.")
            print("\nOptions:")
            print("  1. Install Docker: https://docs.docker.com/get-docker/")
            print("  2. Run setup: ./scripts/setup_seller.sh")
            print("  3. Disable sandboxing (NOT RECOMMENDED):")
            print("     Set DOCKER_ENABLED=false in .env")
            print("="*60 + "\n")
            sys.exit(1)
        
        # Check if appropriate image exists
        if self.gpu_info.gpu_type.value == "cuda":
            image = self.config.docker_image_gpu
            image_type = "GPU"
        else:
            image = self.config.docker_image
            image_type = "CPU"
        
        image_exists = await self.executor._check_docker_image_exists(image)
        
        if not image_exists:
            logger.warning(
                "docker_image_missing",
                image=image,
                image_type=image_type,
                message=f"{image_type} sandbox image not found. Attempting to build..."
            )
            
            # Try to build the image
            build_success = await self._try_build_docker_image(image_type)
            
            if not build_success:
                logger.warning(
                    "docker_image_build_failed",
                    image=image,
                    message="Will fall back to subprocess execution (less secure)"
                )
                print(f"\nWARNING: {image_type} Docker image '{image}' not found")
                print("Jobs will run without Docker isolation (less secure)")
                print(f"\nTo build manually: ./scripts/build_docker.sh {image_type.lower()}")
                print("")
        else:
            logger.info("docker_image_ready", image=image, image_type=image_type)
        
        # Check nvidia-docker for CUDA
        if self.gpu_info.gpu_type.value == "cuda":
            nvidia_available = await self.executor._check_nvidia_docker_available()
            if not nvidia_available:
                logger.warning(
                    "nvidia_docker_unavailable",
                    message="GPU detected but nvidia-docker not working. GPU jobs will run on CPU.",
                    help="Install nvidia-container-toolkit"
                )
                print("\nWARNING: NVIDIA Docker not configured")
                print("GPU jobs will run on CPU instead")
                print("\nTo fix: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html")
                print("")
    
    async def _try_build_docker_image(self, image_type: str) -> bool:
        """Attempt to build Docker image automatically"""
        import subprocess
        from pathlib import Path
        
        project_root = Path(__file__).parent.parent.parent
        
        if image_type.lower() == "gpu":
            dockerfile = project_root / "Dockerfile.sandbox-gpu"
            tag = self.config.docker_image_gpu
        else:
            dockerfile = project_root / "Dockerfile.sandbox"
            tag = self.config.docker_image
        
        if not dockerfile.exists():
            logger.warning("dockerfile_not_found", path=str(dockerfile))
            return False
        
        logger.info("building_docker_image", tag=tag, dockerfile=str(dockerfile))
        print(f"\nBuilding {image_type} Docker image (this may take a few minutes)...")
        
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "build", "-t", tag, "-f", str(dockerfile), str(project_root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
            
            if process.returncode == 0:
                logger.info("docker_image_built", tag=tag)
                print(f"✓ {image_type} Docker image built successfully")
                return True
            else:
                logger.warning("docker_build_failed", stderr=stderr.decode()[:500])
                return False
                
        except asyncio.TimeoutError:
            logger.warning("docker_build_timeout", message="Image build timed out after 10 minutes")
            return False
        except Exception as e:
            logger.warning("docker_build_error", error=str(e))
            return False

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

    def _display_status(self):
        """Display current seller status"""
        uptime = ""
        if self.session_start_time:
            delta = datetime.now() - self.session_start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f"{hours}h {minutes}m {seconds}s"
        
        print("\n" + "=" * 60)
        print("  ComputeSwarm Seller Agent")
        print("=" * 60)
        print(f"  Node ID:      {self.node_id or 'Not registered'}")
        print(f"  GPU:          {self.gpu_info.device_name if self.gpu_info else 'Unknown'}")
        print(f"  Price:        ${float(self.price_per_hour):.2f}/hr" if self.price_per_hour else "")
        print(f"  Status:       {'Busy' if self.is_busy else 'Available'}")
        print("-" * 60)
        print(f"  Session Earnings:  ${float(self.session_earnings):.4f} USDC")
        print(f"  Jobs Completed:    {self.session_jobs_completed}")
        print(f"  Jobs Failed:       {self.session_jobs_failed}")
        print(f"  Uptime:            {uptime}")
        print("=" * 60 + "\n")

    async def earnings_display_loop(self):
        """Periodically display earnings summary"""
        display_interval = 300  # Every 5 minutes
        
        while self.running:
            try:
                await asyncio.sleep(display_interval)
                
                # Fetch server-side earnings
                try:
                    response = await self.client.get(
                        f"{self.config.marketplace_url}/api/v1/sellers/{self.config.seller_address}/earnings",
                        params={"days": 30}
                    )
                    if response.status_code == 200:
                        data = response.json()
                        server_earnings = data.get("earnings", {})
                        jobs_data = data.get("jobs", {})
                        
                        logger.info(
                            "earnings_summary",
                            session_usd=float(self.session_earnings),
                            today_usd=server_earnings.get("today_usd", 0),
                            month_usd=server_earnings.get("month_usd", 0),
                            total_jobs=jobs_data.get("total_completed", 0)
                        )
                except Exception as e:
                    logger.debug("earnings_fetch_failed", error=str(e))
                
                # Display session stats
                self._display_status()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("earnings_display_error", error=str(e))
    
    async def fetch_earnings(self) -> Optional[dict]:
        """Fetch earnings from marketplace"""
        try:
            response = await self.client.get(
                f"{self.config.marketplace_url}/api/v1/sellers/{self.config.seller_address}/earnings",
                params={"days": 30}
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning("fetch_earnings_failed", error=str(e))
        return None

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
            
            # Update session stats
            self.session_earnings += total_cost
            self.session_jobs_completed += 1
            
            # Display quick update
            print(f"\n✓ Job {job_id[:12]}... completed - Earned ${float(total_cost):.4f} USDC")
            print(f"  Session Total: ${float(self.session_earnings):.4f} | Jobs: {self.session_jobs_completed}")

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
            
            # Update session stats
            self.session_jobs_failed += 1
            print(f"\n✗ Job {job_id[:12]}... failed")
            print(f"  Session: {self.session_jobs_completed} completed, {self.session_jobs_failed} failed")

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

        # Display session summary
        print("\n" + "=" * 60)
        print("  Session Summary")
        print("=" * 60)
        print(f"  Total Earned:     ${float(self.session_earnings):.4f} USDC")
        print(f"  Jobs Completed:   {self.session_jobs_completed}")
        print(f"  Jobs Failed:      {self.session_jobs_failed}")
        if self.session_start_time:
            uptime = datetime.now() - self.session_start_time
            hours = uptime.total_seconds() / 3600
            print(f"  Uptime:           {hours:.1f} hours")
            if hours > 0 and self.session_earnings > 0:
                hourly_rate = float(self.session_earnings) / hours
                print(f"  Hourly Earnings:  ${hourly_rate:.4f}/hr")
        print("=" * 60 + "\n")

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
