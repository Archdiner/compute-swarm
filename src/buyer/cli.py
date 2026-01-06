"""
ComputeSwarm Buyer CLI
Queue-based job submission, monitoring, and x402 payment handling
"""

import asyncio
import sys
import time
from typing import Optional
import httpx
import structlog
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich.align import Align

from src.marketplace.models import GPUType
from src.config import get_buyer_config
from src.payments import PaymentProcessor
from src.templates import list_templates, get_template, render_template, get_template_help, TemplateCategory
from pathlib import Path

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

    async def estimate_job_cost(
        self,
        timeout_seconds: int = 3600,
        required_gpu_type: Optional[str] = None,
        min_vram_gb: Optional[float] = None,
        num_gpus: int = 1
    ) -> Optional[dict]:
        """
        Estimate job cost before submission
        """
        try:
            params = {
                "timeout_seconds": timeout_seconds,
                "num_gpus": num_gpus
            }
            if required_gpu_type:
                params["required_gpu_type"] = required_gpu_type
            if min_vram_gb:
                params["min_vram_gb"] = min_vram_gb
            
            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/estimate",
                params=params
            )
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            logger.error("cost_estimation_failed", error=str(e))
            return None
    
    async def upload_input_file(self, file_path: str, job_id: str) -> Optional[str]:
        """
        Upload an input file for a job
        Returns the storage URL that can be used in the job script
        """
        try:
            path = Path(file_path)
            if not path.exists():
                console.print(f"[red]File not found: {file_path}[/red]")
                return None
            
            # Read file and upload via marketplace API
            with open(path, "rb") as f:
                file_data = f.read()
            
            import base64
            file_b64 = base64.b64encode(file_data).decode('utf-8')
            
            response = await self.client.post(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}/files/upload",
                json={
                    "file_name": path.name,
                    "file_type": "input",
                    "content_base64": file_b64
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                console.print(f"[green]✓ Uploaded: {path.name}[/green]")
                console.print(f"  Storage path: [dim]{data.get('storage_path')}[/dim]")
                return data.get('download_url')
            else:
                console.print(f"[yellow]File upload not available (storage not configured)[/yellow]")
                return None
                
        except Exception as e:
            logger.warning("file_upload_failed", error=str(e))
            console.print(f"[yellow]File upload failed: {e}[/yellow]")
            return None
    
    async def download_output_file(self, job_id: str, output_dir: str = ".") -> bool:
        """
        Download output files from a completed job
        """
        try:
            # List files for job
            response = await self.client.get(
                f"{self.config.marketplace_url}/api/v1/jobs/{job_id}/files"
            )
            
            if response.status_code != 200:
                console.print("[yellow]No files available for this job[/yellow]")
                return False
            
            files = response.json().get("files", [])
            output_files = [f for f in files if f.get("file_type") == "output"]
            
            if not output_files:
                console.print("[yellow]No output files found[/yellow]")
                return False
            
            # Download each file
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            for file_info in output_files:
                file_name = file_info.get("file_name", "output")
                download_url = file_info.get("download_url")
                
                if download_url:
                    # Download via signed URL
                    async with httpx.AsyncClient() as client:
                        file_response = await client.get(download_url)
                        if file_response.status_code == 200:
                            dest = output_path / file_name
                            dest.write_bytes(file_response.content)
                            console.print(f"[green]✓ Downloaded: {dest}[/green]")
            
            return True
            
        except Exception as e:
            logger.warning("file_download_failed", error=str(e))
            console.print(f"[yellow]File download failed: {e}[/yellow]")
            return False

    def display_cost_estimate(self, estimate: dict):
        """Display cost estimate in a formatted way"""
        if not estimate or not estimate.get("estimated"):
            console.print(f"[yellow]{estimate.get('message', 'Unable to estimate cost')}[/yellow]")
            if estimate.get("suggestion"):
                console.print(f"[dim]{estimate['suggestion']}[/dim]")
            return
        
        console.print("\n[bold cyan]Cost Estimate[/bold cyan]")
        console.print("=" * 40)
        
        cost = estimate["cost_estimate"]
        hourly = estimate["hourly_rates"]
        queue = estimate["queue"]
        
        console.print(f"\n[bold]Estimated Cost:[/bold]")
        console.print(f"  Min: [green]${cost['min_usd']:.4f}[/green] USDC")
        console.print(f"  Max: [yellow]${cost['max_usd']:.4f}[/yellow] USDC")
        console.print(f"  Avg: [cyan]${cost['avg_usd']:.4f}[/cyan] USDC")
        
        console.print(f"\n[bold]Hourly Rates:[/bold]")
        console.print(f"  ${hourly['min_per_hour']:.2f} - ${hourly['max_per_hour']:.2f}/hr")
        
        console.print(f"\n[bold]Availability:[/bold]")
        console.print(f"  Matching nodes: [green]{estimate['matching_nodes']}[/green]")
        console.print(f"  GPU types: {', '.join(estimate['gpu_types_available'])}")
        console.print(f"  Pending jobs: {queue['pending_jobs']}")
        console.print(f"  Est. wait time: ~{queue['estimated_wait_minutes']} min")
        
        console.print("")

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

            # Create submission success panel
            success_content = f"""[bold]Job ID:[/bold] [cyan]{job_id}[/cyan]
[bold]Status:[/bold] [yellow]{data['status']}[/yellow]
[bold]Max Price:[/bold] ${max_price_per_hour}/hr
[bold]Timeout:[/bold] {timeout_seconds}s"""
            
            console.print("\n")
            console.print(Panel(success_content, title="✓ Job Submitted", border_style="green"))
            console.print(f"[dim]Job submitted to queue. Sellers will claim when available.[/dim]\n")

            if wait_for_completion:
                console.print("[yellow]Starting live monitoring...[/yellow]\n")
                await self.wait_for_job(job_id, live_view=True)

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
        """Display job status in a formatted way with rich panels"""
        if not job:
            console.print(Panel("[yellow]Job not found[/yellow]", title="Error", border_style="red"))
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
        status_color = status_colors.get(status, "white")
        
        # Create main info panel
        info_lines = []
        info_lines.append(f"[bold]Job ID:[/bold] [cyan]{job['job_id']}[/cyan]")
        info_lines.append(f"[bold]Status:[/bold] [{status_color}]{status}[/]")
        info_lines.append(f"[bold]Buyer:[/bold] {job['buyer_address'][:20]}...")
        info_lines.append(f"[bold]Max Price:[/bold] ${job['max_price_per_hour']}/hr")
        info_lines.append(f"[bold]Timeout:[/bold] {job['timeout_seconds']}s")
        
        if job.get("seller_address"):
            info_lines.append(f"[bold]Seller:[/bold] {job['seller_address'][:20]}...")
        if job.get("node_id"):
            info_lines.append(f"[bold]Node:[/bold] {job['node_id'][:20]}...")
        
        info_panel = Panel("\n".join(info_lines), title="Job Information", border_style=status_color)
        
        # Create timeline panel
        timeline_lines = []
        if job.get("created_at"):
            timeline_lines.append(f"[green]✓ Created:[/green] {job['created_at']}")
        if job.get("claimed_at"):
            timeline_lines.append(f"[blue]✓ Claimed:[/blue] {job['claimed_at']}")
        if job.get("started_at"):
            timeline_lines.append(f"[cyan]⚡ Started:[/cyan] {job['started_at']}")
        if job.get("completed_at"):
            timeline_lines.append(f"[green]✓ Completed:[/green] {job['completed_at']}")
        
        timeline_panel = Panel("\n".join(timeline_lines) if timeline_lines else "[dim]No timeline data[/dim]", 
                               title="Timeline", border_style="blue")
        
        # Create payment panel
        payment_lines = []
        if job.get("execution_duration_seconds"):
            payment_lines.append(f"[bold]Duration:[/bold] {job['execution_duration_seconds']:.2f}s")
        if job.get("total_cost_usd"):
            payment_lines.append(f"[bold]Total Cost:[/bold] [yellow]${job['total_cost_usd']:.6f}[/yellow] USDC")
            if job.get("execution_duration_seconds"):
                hourly_rate = (job['total_cost_usd'] / job['execution_duration_seconds']) * 3600
                payment_lines.append(f"[bold]Effective Rate:[/bold] ${hourly_rate:.4f}/hr")
        if job.get("payment_tx_hash"):
            payment_lines.append(f"[bold]Payment TX:[/bold] [dim]{job['payment_tx_hash'][:30]}...[/dim]")
            payment_lines.append("[green]✓ Payment processed via x402[/green]")
        elif status == "COMPLETED":
            payment_lines.append("[yellow]⏳ Payment processing...[/yellow]")
        
        payment_panel = Panel("\n".join(payment_lines) if payment_lines else "[dim]No payment data[/dim]",
                             title="x402 Payment", border_style="yellow")
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(info_panel, name="info"),
            Layout(name="bottom")
        )
        layout["bottom"].split_row(
            Layout(timeline_panel, name="timeline"),
            Layout(payment_panel, name="payment")
        )
        
        console.print("\n")
        console.print(layout)
        
        # Output section
        if job.get("result_output"):
            output_text = job["result_output"]
            # Truncate very long outputs
            if len(output_text) > 2000:
                output_text = output_text[:2000] + "\n...[truncated]"
            console.print("\n")
            console.print(Panel(output_text, title="Job Output", border_style="green"))

        if job.get("result_error"):
            console.print("\n")
            console.print(Panel(job["result_error"], title="Error Output", border_style="red"))

    async def wait_for_job(self, job_id: str, poll_interval: int = 2, live_view: bool = True):
        """Wait for job to complete, showing progress with rich visualizations"""
        if not live_view:
            # Simple mode - just spinner
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
            self.display_job_status(job)
            return

        # Enhanced live view mode
        status_colors = {
            "PENDING": "yellow",
            "CLAIMED": "blue",
            "EXECUTING": "cyan",
            "COMPLETED": "green",
            "FAILED": "red",
            "CANCELLED": "magenta"
        }
        
        start_time = time.time()
        previous_status = None
        
        def create_status_panel(job_data):
            """Create a rich panel showing job status"""
            if not job_data:
                return Panel("[red]Failed to fetch job status[/red]", title="Job Status", border_style="red")
            
            status = job_data.get("status", "UNKNOWN")
            status_color = status_colors.get(status, "white")
            
            lines = []
            lines.append(f"[bold]Job ID:[/bold] [cyan]{job_data.get('job_id', 'N/A')[:20]}...[/cyan]")
            lines.append(f"[bold]Status:[/bold] [{status_color}]{status}[/]")
            
            if job_data.get("seller_address"):
                lines.append(f"[bold]Seller:[/bold] {job_data['seller_address'][:20]}...")
            if job_data.get("node_id"):
                lines.append(f"[bold]Node:[/bold] {job_data['node_id'][:20]}...")
            
            elapsed = time.time() - start_time
            lines.append(f"[bold]Elapsed:[/bold] {elapsed:.1f}s")
            
            if job_data.get("execution_duration_seconds"):
                lines.append(f"[bold]Duration:[/bold] {job_data['execution_duration_seconds']:.2f}s")
            
            if job_data.get("total_cost_usd"):
                lines.append(f"[bold]Cost:[/bold] [yellow]${job_data['total_cost_usd']:.6f}[/yellow] USDC")
            
            if status == "EXECUTING":
                lines.append("")
                lines.append("[cyan]⚡ GPU compute in progress...[/cyan]")
            elif status == "COMPLETED":
                lines.append("")
                lines.append("[green]✓ Job completed successfully![/green]")
            elif status == "FAILED":
                lines.append("")
                lines.append("[red]✗ Job failed[/red]")
            
            content = "\n".join(lines)
            return Panel(content, title="Job Status", border_style=status_color)
        
        def create_payment_panel(job_data):
            """Create a panel showing payment information"""
            lines = []
            
            if job_data.get("payment_tx_hash"):
                lines.append(f"[bold]Transaction:[/bold] [dim]{job_data['payment_tx_hash'][:30]}...[/dim]")
                lines.append("[green]✓ Payment processed via x402[/green]")
            elif job_data.get("status") == "COMPLETED":
                lines.append("[yellow]⏳ Payment processing...[/yellow]")
            else:
                lines.append("[dim]Payment will be processed after completion[/dim]")
            
            if job_data.get("total_cost_usd"):
                lines.append(f"[bold]Amount:[/bold] [yellow]${job_data['total_cost_usd']:.6f}[/yellow] USDC")
            
            content = "\n".join(lines) if lines else "[dim]Waiting for payment info...[/dim]"
            return Panel(content, title="x402 Payment", border_style="yellow")
        
        try:
            with Live(console=console, refresh_per_second=2, screen=False) as live:
                while True:
                    job = await self.get_job_status(job_id)
                    
                    if not job:
                        live.update(Panel("[red]Failed to fetch job status[/red]", title="Error", border_style="red"))
                        await asyncio.sleep(1)
                        continue
                    
                    status = job.get("status", "UNKNOWN")
                    
                    # Create layout
                    layout = Layout()
                    layout.split_column(
                        Layout(name="status", size=10),
                        Layout(name="payment", size=6)
                    )
                    
                    layout["status"].update(create_status_panel(job))
                    layout["payment"].update(create_payment_panel(job))
                    
                    live.update(layout)
                    
                    # Status change notification
                    if previous_status and previous_status != status:
                        status_icons = {
                            "CLAIMED": "🎯",
                            "EXECUTING": "⚡",
                            "COMPLETED": "✓",
                            "FAILED": "✗"
                        }
                        icon = status_icons.get(status, "")
                        console.print(f"\n{icon} Status changed: [bold]{previous_status}[/bold] → [{status_colors.get(status, 'white')}]{status}[/]")
                    
                    previous_status = status
                    
                    if status in ["COMPLETED", "FAILED", "CANCELLED"]:
                        await asyncio.sleep(1)  # Final update
                        break
                    
                    await asyncio.sleep(poll_interval)
        
        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring cancelled by user[/yellow]")
        
        # Display final detailed results
        job = await self.get_job_status(job_id)
        console.print("\n" + "="*60)
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
                    await self.wait_for_job(job_id, live_view=True)
                
                elif command == "monitor":
                    job_id = console.input("Job ID to monitor: ").strip()
                    await self.wait_for_job(job_id, live_view=True)

                elif command == "templates":
                    self.display_templates()
                
                elif command == "template":
                    await self.submit_from_template()
                
                elif command == "estimate":
                    try:
                        timeout = int(console.input("Timeout (seconds) [3600]: ").strip() or "3600")
                        gpu_type = console.input("GPU type (cuda/mps/any) [any]: ").strip() or None
                        if gpu_type == "any":
                            gpu_type = None
                        num_gpus = int(console.input("Number of GPUs [1]: ").strip() or "1")
                        
                        estimate = await self.estimate_job_cost(
                            timeout_seconds=timeout,
                            required_gpu_type=gpu_type,
                            num_gpus=num_gpus
                        )
                        self.display_cost_estimate(estimate)
                    except ValueError as e:
                        console.print(f"[red]Invalid input: {e}[/red]")
                
                elif command == "download":
                    job_id = console.input("Job ID: ").strip()
                    output_dir = console.input("Output directory [.]: ").strip() or "."
                    await self.download_output_file(job_id, output_dir)

                elif command == "help":
                    console.print("\n[bold]Available Commands:[/bold]")
                    console.print("  stats     - Show marketplace statistics")
                    console.print("  wallet    - Show wallet balance and info")
                    console.print("  estimate  - Estimate job cost before submitting")
                    console.print("  submit    - Submit a new job to queue")
                    console.print("  templates - List available job templates")
                    console.print("  template  - Submit job using a template")
                    console.print("  status    - Get status of a specific job")
                    console.print("  list      - List your jobs")
                    console.print("  download  - Download output files from a job")
                    console.print("  cancel    - Cancel a pending/claimed job")
                    console.print("  wait      - Wait for job completion (with live view)")
                    console.print("  monitor   - Monitor job with live status updates (same as wait)")
                    console.print("  quit      - Exit CLI\n")

                else:
                    console.print(f"[yellow]Unknown command: {command}. Type 'help' for commands.[/yellow]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Use 'quit' to exit[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                logger.error("cli_error", error=str(e))

        await self.client.aclose()

    def display_templates(self):
        """Display available job templates"""
        console.print("\n[bold cyan]Available Job Templates[/bold cyan]")
        console.print("=" * 50)
        
        for category in TemplateCategory:
            templates = list_templates(category)
            if templates:
                console.print(f"\n[bold]{category.value.upper()}[/bold]")
                console.print("-" * 40)
                
                for t in templates:
                    gpu_indicator = "[green]GPU[/green]" if t.gpu_required else "[yellow]CPU[/yellow]"
                    console.print(f"  [cyan]{t.name}[/cyan] {gpu_indicator}")
                    console.print(f"    {t.description}")
                    if t.parameters:
                        console.print("    Parameters:")
                        for param, desc in t.parameters.items():
                            console.print(f"      --{param}: [dim]{desc}[/dim]")
        
        console.print("\n[dim]Use 'template' command to submit a job from a template[/dim]\n")

    async def submit_from_template(self):
        """Submit a job using a template"""
        # Show available templates
        all_templates = list_templates()
        if not all_templates:
            console.print("[red]No templates available[/red]")
            return
        
        console.print("\n[bold]Available Templates:[/bold]")
        for i, t in enumerate(all_templates, 1):
            console.print(f"  {i}. [cyan]{t.name}[/cyan] - {t.description}")
        
        # Select template
        try:
            choice = console.input("\nSelect template (number or name): ").strip()
            
            # Try as number first
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(all_templates):
                    template = all_templates[idx]
                else:
                    console.print("[red]Invalid selection[/red]")
                    return
            else:
                # Try as name
                template = get_template(choice)
                if not template:
                    console.print(f"[red]Template '{choice}' not found[/red]")
                    return
            
            console.print(f"\n[green]Selected: {template.name}[/green]")
            console.print(f"[dim]{template.description}[/dim]")
            
            # Collect parameters
            params = {}
            if template.parameters:
                console.print("\n[bold]Enter parameters:[/bold]")
                for param, desc in template.parameters.items():
                    value = console.input(f"  {param} ({desc}): ").strip()
                    if not value:
                        console.print(f"[red]Parameter '{param}' is required[/red]")
                        return
                    params[param] = value
            
            # Render script
            try:
                script = render_template(template.name, **params)
            except Exception as e:
                console.print(f"[red]Error rendering template: {e}[/red]")
                return
            
            # Show preview
            console.print("\n[bold]Generated Script Preview:[/bold]")
            console.print("[dim]" + "-" * 50 + "[/dim]")
            preview = script[:500] + ("..." if len(script) > 500 else "")
            console.print(f"[dim]{preview}[/dim]")
            console.print("[dim]" + "-" * 50 + "[/dim]")
            
            # Confirm and submit
            max_price = float(console.input(f"Max price per hour (USD) [10.0]: ").strip() or "10.0")
            timeout = int(console.input(f"Timeout (seconds) [{template.default_timeout}]: ").strip() or str(template.default_timeout))
            
            gpu_type = None
            if template.gpu_required:
                gpu_type = console.input("GPU type (cuda/mps/any) [any]: ").strip() or None
            
            confirm = console.input("\nSubmit job? (y/n) [y]: ").strip().lower()
            if confirm == "n":
                console.print("[yellow]Cancelled[/yellow]")
                return
            
            wait = console.input("Wait for completion? (y/n) [n]: ").strip().lower() == "y"
            
            await self.submit_job(
                script=script,
                requirements=template.default_requirements,
                max_price_per_hour=max_price,
                timeout_seconds=timeout,
                required_gpu_type=gpu_type,
                wait_for_completion=wait
            )
            
        except ValueError as e:
            console.print(f"[red]Invalid input: {e}[/red]")

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

        elif command == "templates":
            cli.display_templates()
        
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
            console.print("[red]Invalid command or missing arguments[/red]")
            console.print("\nUsage: python -m src.buyer.cli <command> [args]")
            console.print("\nCommands:")
            console.print("  stats                    Show marketplace statistics")
            console.print("  wallet                   Show wallet balance")
            console.print("  templates                List available job templates")
            console.print("  submit <script> [--wait] Submit a job from file")
            console.print("  status <job_id>          Get job status")
            console.print("  list                     List your jobs")
            console.print("\nOr run without arguments for interactive mode.")

    else:
        # Interactive mode
        await cli.interactive_mode()

    await cli.close()


if __name__ == "__main__":
    asyncio.run(main())
