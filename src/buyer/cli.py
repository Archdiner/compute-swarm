"""
ComputeSwarm Buyer CLI
Command-line interface for discovering nodes and submitting jobs
"""

import asyncio
import sys
from typing import Optional, List
import httpx
import structlog
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from src.marketplace.models import ComputeNode, GPUType, JobRequest, Job
from src.config import get_buyer_config

logger = structlog.get_logger()
console = Console()


class BuyerCLI:
    """
    Buyer CLI for:
    1. Discovering available compute nodes
    2. Submitting jobs to nodes
    3. Monitoring job status
    4. Handling x402 payment flow
    """

    def __init__(self):
        self.config = get_buyer_config()
        self.client = httpx.AsyncClient(timeout=30.0)

    async def discover_nodes(
        self,
        gpu_type: Optional[str] = None,
        max_price: Optional[float] = None
    ) -> List[ComputeNode]:
        """Discover available compute nodes"""
        try:
            params = {}
            if gpu_type:
                params["gpu_type"] = gpu_type
            if max_price:
                params["max_price"] = max_price

            response = await self.client.get(
                f"{self.config.marketplace_url}/api/v1/nodes",
                params=params
            )
            response.raise_for_status()

            nodes = [ComputeNode(**node) for node in response.json()]

            logger.info("nodes_discovered", count=len(nodes))
            return nodes

        except Exception as e:
            logger.error("node_discovery_failed", error=str(e))
            return []

    def display_nodes(self, nodes: List[ComputeNode]):
        """Display available nodes in a formatted table"""
        if not nodes:
            console.print("[yellow]No nodes available[/yellow]")
            return

        table = Table(title="Available Compute Nodes", show_header=True, header_style="bold magenta")

        table.add_column("Node ID", style="cyan", no_wrap=True)
        table.add_column("GPU Type", style="green")
        table.add_column("Device", style="white")
        table.add_column("VRAM (GB)", justify="right", style="blue")
        table.add_column("Price/hr (USD)", justify="right", style="yellow")
        table.add_column("Status", style="green")

        for node in nodes:
            table.add_row(
                node.node_id[:20] + "...",
                node.gpu_info.gpu_type.value.upper(),
                node.gpu_info.device_name,
                f"{node.gpu_info.vram_gb:.1f}",
                f"${node.price_per_hour:.2f}",
                node.status.value
            )

        console.print(table)

    async def submit_job(
        self,
        node_id: str,
        script: str,
        job_type: str = "train",
        max_duration: int = 3600
    ) -> Optional[Job]:
        """Submit a compute job to a specific node"""
        try:
            job_request = JobRequest(
                job_type=job_type,
                script=script,
                max_duration_seconds=max_duration
            )

            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/submit",
                params={
                    "node_id": node_id,
                    "buyer_address": self.config.buyer_address
                },
                json=job_request.model_dump()
            )

            # Check for x402 Payment Required
            if response.status_code == 402:
                console.print("[yellow]Payment required - x402 flow will be implemented in Day 3[/yellow]")
                # TODO: Handle x402 payment challenge
                return None

            response.raise_for_status()

            job = Job(**response.json())
            logger.info("job_submitted", job_id=job.job_id, node_id=node_id)

            console.print(f"[green]Job submitted successfully: {job.job_id}[/green]")
            return job

        except Exception as e:
            logger.error("job_submission_failed", error=str(e))
            console.print(f"[red]Job submission failed: {e}[/red]")
            return None

    async def get_job_status(self, job_id: str) -> Optional[Job]:
        """Get the status of a job"""
        try:
            response = await self.client.get(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}"
            )
            response.raise_for_status()

            job = Job(**response.json())
            return job

        except Exception as e:
            logger.error("get_job_status_failed", error=str(e), job_id=job_id)
            return None

    def display_job_status(self, job: Job):
        """Display job status in a formatted way"""
        console.print("\n[bold]Job Status[/bold]")
        console.print(f"Job ID: {job.job_id}")
        console.print(f"Status: [{'green' if job.status.value == 'completed' else 'yellow'}]{job.status.value}[/]")
        console.print(f"Node: {job.node_id}")
        console.print(f"Buyer: {job.buyer_address}")
        console.print(f"Created: {job.created_at}")

        if job.started_at:
            console.print(f"Started: {job.started_at}")
        if job.completed_at:
            console.print(f"Completed: {job.completed_at}")
        if job.total_cost_usd:
            console.print(f"Total Cost: ${job.total_cost_usd:.4f}")
        if job.output:
            console.print(f"\n[bold]Output:[/bold]\n{job.output}")
        if job.error:
            console.print(f"\n[bold red]Error:[/bold red]\n{job.error}")

    async def interactive_mode(self):
        """Run interactive CLI mode"""
        console.print("[bold cyan]ComputeSwarm Buyer CLI[/bold cyan]")
        console.print("Commands: discover, submit, status, quit\n")

        while True:
            try:
                command = console.input("[bold green]>[/bold green] ").strip().lower()

                if command == "quit" or command == "exit":
                    break

                elif command == "discover":
                    gpu_filter = console.input("GPU type filter (cuda/mps/all): ").strip().lower()
                    gpu_type = None if gpu_filter == "all" else gpu_filter

                    nodes = await self.discover_nodes(gpu_type=gpu_type)
                    self.display_nodes(nodes)

                elif command == "submit":
                    node_id = console.input("Node ID: ").strip()
                    script_path = console.input("Path to Python script: ").strip()

                    try:
                        with open(script_path, "r") as f:
                            script = f.read()

                        job = await self.submit_job(node_id, script)
                        if job:
                            self.display_job_status(job)
                    except FileNotFoundError:
                        console.print(f"[red]Script not found: {script_path}[/red]")

                elif command == "status":
                    job_id = console.input("Job ID: ").strip()
                    job = await self.get_job_status(job_id)
                    if job:
                        self.display_job_status(job)

                else:
                    console.print(f"[yellow]Unknown command: {command}[/yellow]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' to exit[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        await self.client.aclose()

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()


async def main():
    """Main entry point for buyer CLI"""
    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer()
        ]
    )

    cli = BuyerCLI()

    if len(sys.argv) > 1:
        # Command-line mode
        command = sys.argv[1]

        if command == "discover":
            nodes = await cli.discover_nodes()
            cli.display_nodes(nodes)

        elif command == "status" and len(sys.argv) > 2:
            job_id = sys.argv[2]
            job = await cli.get_job_status(job_id)
            if job:
                cli.display_job_status(job)

        else:
            console.print("[red]Invalid command[/red]")
            console.print("Usage: python -m src.buyer.cli [discover|status <job_id>]")

    else:
        # Interactive mode
        await cli.interactive_mode()

    await cli.close()


if __name__ == "__main__":
    asyncio.run(main())
