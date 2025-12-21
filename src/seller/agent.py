"""
ComputeSwarm Seller Agent
Registers GPU hardware with marketplace and executes compute jobs
"""

import asyncio
import sys
import signal
from typing import Optional
from datetime import datetime
import httpx
import structlog

from src.compute.gpu_detector import GPUDetector
from src.marketplace.models import NodeRegistration, ComputeNode, NodeStatus
from src.config import get_seller_config

logger = structlog.get_logger()


class SellerAgent:
    """
    Seller Agent that:
    1. Detects local GPU hardware
    2. Registers with the marketplace
    3. Listens for compute jobs
    4. Executes jobs and returns results
    5. Handles x402 payment verification
    """

    def __init__(self):
        self.config = get_seller_config()
        self.node_id: Optional[str] = None
        self.node_info: Optional[ComputeNode] = None
        self.running = False
        self.client = httpx.AsyncClient(timeout=30.0)

    async def start(self):
        """Start the seller agent"""
        logger.info("seller_agent_starting", seller=self.config.seller_address)

        # Detect GPU
        gpu_info = GPUDetector.detect_gpu()
        logger.info(
            "gpu_detected",
            gpu_type=gpu_info.gpu_type,
            device_name=gpu_info.device_name,
            vram_gb=gpu_info.vram_gb
        )

        # Test GPU
        if not GPUDetector.test_gpu():
            logger.error("gpu_test_failed", message="GPU is not functioning properly")
            sys.exit(1)

        # Determine pricing based on GPU type
        if gpu_info.gpu_type.value == "cuda":
            price_per_hour = self.config.default_price_per_hour_cuda
        elif gpu_info.gpu_type.value == "mps":
            price_per_hour = self.config.default_price_per_hour_mps
        else:
            price_per_hour = 0.10  # Default low price for unknown/CPU

        # TODO: Determine actual endpoint (will be set up in Day 2)
        # For now, use placeholder
        endpoint = "http://localhost:8001"

        # Register with marketplace
        try:
            registration = NodeRegistration(
                seller_address=self.config.seller_address,
                gpu_info=gpu_info,
                price_per_hour=price_per_hour,
                endpoint=endpoint
            )

            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/nodes/register",
                json=registration.model_dump()
            )
            response.raise_for_status()

            self.node_info = ComputeNode(**response.json())
            self.node_id = self.node_info.node_id

            logger.info(
                "registered_with_marketplace",
                node_id=self.node_id,
                price_per_hour=price_per_hour,
                marketplace_url=self.config.marketplace_url
            )

        except Exception as e:
            logger.error("registration_failed", error=str(e))
            sys.exit(1)

        # Start heartbeat loop
        self.running = True
        asyncio.create_task(self.heartbeat_loop())

        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.stop()

    async def heartbeat_loop(self):
        """Send periodic heartbeats to marketplace"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Heartbeat every 30 seconds

                if not self.node_id:
                    continue

                response = await self.client.post(
                    f"{self.config.marketplace_url}/api/v1/nodes/{self.node_id}/heartbeat",
                    params={"node_status": NodeStatus.AVAILABLE.value}
                )
                response.raise_for_status()

                logger.debug("heartbeat_sent", node_id=self.node_id)

            except Exception as e:
                logger.warning("heartbeat_failed", error=str(e))

    async def stop(self):
        """Gracefully shut down the seller agent"""
        logger.info("seller_agent_stopping", node_id=self.node_id)

        self.running = False

        # Unregister from marketplace
        if self.node_id:
            try:
                response = await self.client.delete(
                    f"{self.config.marketplace_url}/api/v1/nodes/{self.node_id}"
                )
                response.raise_for_status()
                logger.info("unregistered_from_marketplace", node_id=self.node_id)
            except Exception as e:
                logger.warning("unregistration_failed", error=str(e))

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
