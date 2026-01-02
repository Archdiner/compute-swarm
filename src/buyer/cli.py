"""
ComputeSwarm Buyer CLI
Queue-based job submission, monitoring, and x402 payment handling
"""

import asyncio
import sys
from typing import Optional
import httpx
import structlog
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.marketplace.models import GPUType
from src.config import get_buyer_config
from src.payments import PaymentProcessor

logger = structlog.get_logger()
console = Console()


class BuyerCLI:
    """
    Queue-based Buyer CLI for:
    1. Viewing marketplace statistics
    2. Submitting jobs to queue
    3. Monitoring job status
    4. Listing user's jobs
    5. Handling x402 payments
    """

    def __init__(self):
        self.config = get_buyer_config()
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # Initialize payment processor if private key is available
        self.payment_processor: Optional[PaymentProcessor] = None
        if self.config.buyer_private_key:
            self.payment_processor = PaymentProcessor(
                private_key=self.config.buyer_private_key,
                rpc_url=self.config.rpc_url,
                usdc_address=self.config.usdc_contract_address,
                network=self.config.network,
            )
            console.print(f"[dim]Wallet: {self.payment_processor.address}[/dim]")

    async def get_marketplace_stats(self):
        """Get marketplace statistics"""
        try:
            response = await self.client.get(
                f"{self.config.marketplace_url}/api/v1/stats"
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("stats_fetch_failed", error=str(e))
            return None

    def display_marketplace_stats(self, stats):
        """Display marketplace statistics"""
        if not stats:
            console.print("[yellow]Failed to fetch marketplace stats[/yellow]")
            return

        console.print("\n[bold cyan]Marketplace Statistics[/bold cyan]")
        console.print(f"Active Nodes: {stats['nodes']['total_active']}")

        if stats['nodes']['by_gpu_type']:
            console.print("\n[bold]GPUs Available:[/bold]")
            for gpu_type, info in stats['nodes']['by_gpu_type'].items():
                console.print(
                    f"  {gpu_type.upper()}: {info['count']} nodes "
                    f"(${info['min_price']:.2f}-${info['max_price']:.2f}/hr)"
                )

        console.print(f"\n[bold]Job Queue:[/bold]")
        console.print(f"  Pending: {stats['jobs']['pending']}")
        console.print(f"  Executing: {stats['jobs']['executing']}")
        console.print(f"  Completed: {stats['jobs']['completed']}")
        console.print(f"  Failed: {stats['jobs']['failed']}")

    async def get_wallet_balance(self):
        """Get wallet USDC balance"""
        if not self.payment_processor:
            console.print("[yellow]No wallet configured[/yellow]")
            return None
        
        try:
            balance = self.payment_processor.get_usdc_balance()
            return balance
        except Exception as e:
            logger.error("balance_fetch_failed", error=str(e))
            return None

    def display_wallet_info(self, balance):
        """Display wallet information"""
        if not self.payment_processor:
            console.print("[yellow]No wallet configured. Set BUYER_PRIVATE_KEY in .env[/yellow]")
            return
            
        console.print("\n[bold cyan]Wallet Information[/bold cyan]")
        console.print(f"Address: {self.payment_processor.address}")
        console.print(f"Network: {self.config.network}")
        if balance is not None:
            console.print(f"USDC Balance: [green]${balance:.6f}[/green]")
        else:
            console.print(f"USDC Balance: [yellow]Unable to fetch[/yellow]")

    async def submit_job(
        self,
        script: str,
        requirements: Optional[str] = None,
        max_price_per_hour: float = 10.0,
        timeout_seconds: int = 3600,
        required_gpu_type: Optional[str] = None,
        min_vram_gb: Optional[float] = None,
        wait_for_completion: bool = False
    ) -> Optional[str]:
        """
        Submit a job to the queue
        Returns job_id if successful
        """
        try:
            params = {
                "buyer_address": self.config.buyer_address,
                "script": script,
                "max_price_per_hour": max_price_per_hour,
                "timeout_seconds": timeout_seconds
            }

            if requirements:
                params["requirements"] = requirements
            if required_gpu_type:
                params["required_gpu_type"] = required_gpu_type
            if min_vram_gb:
                params["min_vram_gb"] = min_vram_gb

            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/submit",
                params=params
            )
            response.raise_for_status()

            data = response.json()
            job_id = data["job_id"]

            logger.info("job_submitted_to_queue", job_id=job_id)

            console.print(f"\n[green]✓ Job submitted to queue[/green]")
            console.print(f"Job ID: [cyan]{job_id}[/cyan]")
            console.print(f"Max Price: ${max_price_per_hour}/hr")
            console.print(f"Status: {data['status']}")

            if wait_for_completion:
                console.print("\n[yellow]Waiting for job to complete...[/yellow]")
                await self.wait_for_job(job_id)

            return job_id

        except Exception as e:
            logger.error("job_submission_failed", error=str(e))
            console.print(f"[red]✗ Job submission failed: {e}[/red]")
            return None

    async def get_job_status(self, job_id: str):
        """Get the status of a job"""
        try:
            response = await self.client.get(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}"
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error("get_job_status_failed", error=str(e), job_id=job_id)
            return None

    def display_job_status(self, job):
        """Display job status in a formatted way"""
        if not job:
            console.print("[yellow]Job not found[/yellow]")
            return

        status = job["status"]
        status_colors = {
            "PENDING": "yellow",
            "CLAIMED": "blue",
            "EXECUTING": "cyan",
            "COMPLETED": "green",
            "FAILED": "red",
            "CANCELLED": "magenta"
        }

        console.print("\n[bold]Job Details[/bold]")
        console.print(f"Job ID: [cyan]{job['job_id']}[/cyan]")
        console.print(f"Status: [{status_colors.get(status, 'white')}]{status}[/]")
        console.print(f"Buyer: {job['buyer_address']}")
        console.print(f"Max Price: ${job['max_price_per_hour']}/hr")
        console.print(f"Timeout: {job['timeout_seconds']}s")

        if job.get("seller_address"):
            console.print(f"Seller: {job['seller_address']}")
            console.print(f"Node: {job['node_id']}")

        if job.get("created_at"):
            console.print(f"Created: {job['created_at']}")
        if job.get("claimed_at"):
            console.print(f"Claimed: {job['claimed_at']}")
        if job.get("started_at"):
            console.print(f"Started: {job['started_at']}")
        if job.get("completed_at"):
            console.print(f"Completed: {job['completed_at']}")

        if job.get("execution_duration_seconds"):
            console.print(f"Duration: {job['execution_duration_seconds']:.2f}s")
        if job.get("total_cost_usd"):
            console.print(f"Total Cost: [yellow]${job['total_cost_usd']:.6f}[/yellow]")
        if job.get("payment_tx_hash"):
            console.print(f"Payment TX: [dim]{job['payment_tx_hash']}[/dim]")

        if job.get("result_output"):
            console.print(f"\n[bold green]Output:[/bold green]")
            console.print(job["result_output"])

        if job.get("result_error"):
            console.print(f"\n[bold red]Error:[/bold red]")
            console.print(job["result_error"])

    async def wait_for_job(self, job_id: str, poll_interval: int = 2):
        """Wait for job to complete, showing progress"""
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("Waiting for job...", total=None)

            while True:
                job = await self.get_job_status(job_id)

                if not job:
                    console.print("[red]Failed to fetch job status[/red]")
                    return

                status = job["status"]
                progress.update(task, description=f"Status: {status}")

                if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                    break

                await asyncio.sleep(poll_interval)

        # Display final results
        self.display_job_status(job)

    async def list_my_jobs(self, status_filter: Optional[str] = None, limit: int = 10):
        """List jobs submitted by this buyer"""
        try:
            url = f"{self.config.marketplace_url}/api/v1/jobs/buyer/{self.config.buyer_address}"
            params = {"limit": limit}
            if status_filter:
                params["status_filter"] = status_filter

            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            jobs = data["jobs"]

            if not jobs:
                console.print("[yellow]No jobs found[/yellow]")
                return

            table = Table(title=f"My Jobs ({data['count']} total)", show_header=True, header_style="bold magenta")

            table.add_column("Job ID", style="cyan", no_wrap=True)
            table.add_column("Status", style="white")
            table.add_column("Created", style="blue")
            table.add_column("Duration (s)", justify="right", style="green")
            table.add_column("Cost (USD)", justify="right", style="yellow")

            for job in jobs:
                job_id_short = job["job_id"][:13] + "..."
                status = job["status"]
                created = job["created_at"][:19] if job.get("created_at") else "N/A"
                duration = f"{job['execution_duration_seconds']:.1f}" if job.get("execution_duration_seconds") else "-"
                cost = f"${job['total_cost_usd']:.6f}" if job.get("total_cost_usd") else "-"

                table.add_row(job_id_short, status, created, duration, cost)

            console.print(table)

        except Exception as e:
            logger.error("list_jobs_failed", error=str(e))
            console.print(f"[red]Failed to list jobs: {e}[/red]")

    async def cancel_job(self, job_id: str):
        """Cancel a pending/claimed job"""
        try:
            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}/cancel",
                params={"buyer_address": self.config.buyer_address}
            )
            response.raise_for_status()

            console.print(f"[green]✓ Job {job_id} cancelled[/green]")
            return True

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                console.print(f"[red]Cannot cancel job (not found, wrong buyer, or already executing)[/red]")
            else:
                console.print(f"[red]Failed to cancel job: {e}[/red]")
            return False

    async def interactive_mode(self):
        """Run interactive CLI mode"""
        console.print("[bold cyan]ComputeSwarm Buyer CLI (Queue-Based)[/bold cyan]")
        console.print("Commands: stats, submit, status, list, cancel, wait, wallet, quit\n")

        while True:
            try:
                command = console.input("[bold green]>[/bold green] ").strip().lower()

                if command in ["quit", "exit", "q"]:
                    break

                elif command == "stats":
                    stats = await self.get_marketplace_stats()
                    self.display_marketplace_stats(stats)

                elif command == "wallet":
                    balance = await self.get_wallet_balance()
                    self.display_wallet_info(balance)

                elif command == "submit":
                    script_path = console.input("Path to Python script: ").strip()

                    try:
                        with open(script_path, "r") as f:
                            script = f.read()

                        max_price = float(console.input("Max price per hour (USD) [10.0]: ").strip() or "10.0")
                        timeout = int(console.input("Timeout (seconds) [3600]: ").strip() or "3600")
                        gpu_type = console.input("Required GPU type (cuda/mps/none) [none]: ").strip().lower()
                        gpu_type = gpu_type if gpu_type in ["cuda", "mps"] else None

                        wait = console.input("Wait for completion? (y/n) [n]: ").strip().lower() == "y"

                        await self.submit_job(
                            script=script,
                            max_price_per_hour=max_price,
                            timeout_seconds=timeout,
                            required_gpu_type=gpu_type,
                            wait_for_completion=wait
                        )

                    except FileNotFoundError:
                        console.print(f"[red]Script not found: {script_path}[/red]")
                    except ValueError as e:
                        console.print(f"[red]Invalid input: {e}[/red]")

                elif command == "status":
                    job_id = console.input("Job ID: ").strip()
                    job = await self.get_job_status(job_id)
                    self.display_job_status(job)

                elif command == "list":
                    status_filter = console.input("Status filter (PENDING/EXECUTING/COMPLETED/all) [all]: ").strip().upper()
                    status_filter = status_filter if status_filter != "ALL" else None
                    await self.list_my_jobs(status_filter=status_filter)

                elif command == "cancel":
                    job_id = console.input("Job ID to cancel: ").strip()
                    await self.cancel_job(job_id)

                elif command == "wait":
                    job_id = console.input("Job ID to wait for: ").strip()
                    await self.wait_for_job(job_id)

                elif command == "help":
                    console.print("\n[bold]Available Commands:[/bold]")
                    console.print("  stats  - Show marketplace statistics")
                    console.print("  wallet - Show wallet balance and info")
                    console.print("  submit - Submit a new job to queue")
                    console.print("  status - Get status of a specific job")
                    console.print("  list   - List your jobs")
                    console.print("  cancel - Cancel a pending/claimed job")
                    console.print("  wait   - Wait for job completion")
                    console.print("  quit   - Exit CLI\n")

                else:
                    console.print(f"[yellow]Unknown command: {command}. Type 'help' for commands.[/yellow]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' to exit[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                logger.error("cli_error", error=str(e))

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

        if command == "stats":
            stats = await cli.get_marketplace_stats()
            cli.display_marketplace_stats(stats)

        elif command == "wallet":
            balance = await cli.get_wallet_balance()
            cli.display_wallet_info(balance)

        elif command == "status" and len(sys.argv) > 2:
            job_id = sys.argv[2]
            job = await cli.get_job_status(job_id)
            cli.display_job_status(job)

        elif command == "list":
            await cli.list_my_jobs()

        elif command == "submit" and len(sys.argv) > 2:
            script_path = sys.argv[2]
            try:
                with open(script_path, "r") as f:
                    script = f.read()

                wait = "--wait" in sys.argv

                await cli.submit_job(script=script, wait_for_completion=wait)
            except FileNotFoundError:
                console.print(f"[red]Script not found: {script_path}[/red]")

        else:
            console.print("[red]Invalid command[/red]")
            console.print("Usage: python -m src.buyer.cli [stats|wallet|status <job_id>|list|submit <script_path> [--wait]]")

    else:
        # Interactive mode
        await cli.interactive_mode()

    await cli.close()


if __name__ == "__main__":
    asyncio.run(main())
