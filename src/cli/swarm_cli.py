#!/usr/bin/env python3
"""
swarm-cli: A clean CLI for ComputeSwarm
Submit jobs, monitor status, and download results.

Usage:
    swarm submit --model llama3 --data dataset.json [--wait] [--json]
    swarm status <job_id> [--json]
    swarm download <job_id> [--output ./results]
    swarm nodes [--json]
    swarm balance [--json]
"""

import argparse
import asyncio
import json as json_lib
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

from src.config import get_buyer_config
from src.templates import list_templates, get_template, render_template

console = Console()


class SwarmCLI:
    """Clean CLI wrapper for ComputeSwarm operations"""

    def __init__(self, json_output: bool = False):
        self.config = get_buyer_config()
        self.client = httpx.AsyncClient(timeout=60.0)
        self.base_url = self.config.marketplace_url
        self.json_output = json_output

    def _output(self, data: dict, human_message: str = None):
        """Output data in JSON or human-readable format"""
        if self.json_output:
            print(json_lib.dumps(data, indent=2, default=str))
        elif human_message:
            console.print(human_message)

    async def submit(
        self,
        model: Optional[str] = None,
        data: Optional[str] = None,
        script: Optional[str] = None,
        template: Optional[str] = None,
        wait: bool = False,
        max_price: float = 10.0,
        timeout: int = 3600
    ) -> Optional[str]:
        """Submit a job to the network"""
        
        # Determine script content
        if script and Path(script).exists():
            script_content = Path(script).read_text()
        elif template:
            tmpl = get_template(template)
            if not tmpl:
                self._output({"error": f"Template '{template}' not found"}, f"[red]Template '{template}' not found[/red]")
                return None
            params = {}
            if model:
                params["model_name"] = model
            if data:
                params["data_path"] = data
            script_content = render_template(template, **params)
        elif model:
            script_content = f'''
# Auto-generated inference script
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

model_name = "{model}"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16)

data_path = "{data or ''}"
if data_path:
    import json
    with open(data_path) as f:
        data = json.load(f)
    print(f"Loaded {{len(data)}} samples")
else:
    data = [{{"prompt": "Hello, world!"}}]

for item in data[:5]:
    prompt = item.get("prompt", str(item))
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=100)
    print(tokenizer.decode(outputs[0], skip_special_tokens=True))
'''
        else:
            self._output({"error": "Please provide --model, --script, or --template"}, "[red]Please provide --model, --script, or --template[/red]")
            return None

        # Submit job
        if not self.json_output:
            console.print("[cyan]Submitting job to network...[/cyan]")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/api/v1/jobs/submit",
                params={
                    "buyer_address": self.config.buyer_address,
                    "script": script_content,
                    "max_price_per_hour": max_price,
                    "timeout_seconds": timeout,
                    "required_gpu_type": "cuda"
                }
            )
            response.raise_for_status()
            result = response.json()
            job_id = result["job_id"]
        except Exception as e:
            self._output({"error": str(e)}, f"[red]Submission failed: {e}[/red]")
            return None

        # Output result
        output_data = {
            "success": True,
            "job_id": job_id,
            "status": "PENDING",
            "max_price_per_hour": max_price,
            "timeout_seconds": timeout
        }
        
        if self.json_output:
            print(json_lib.dumps(output_data))
        else:
            console.print(Panel(
                f"[green]✓ Job Submitted![/green]\n\n"
                f"[bold]Job ID:[/bold] {job_id}\n"
                f"[bold]Status:[/bold] PENDING\n"
                f"[bold]Max Price:[/bold] ${max_price}/hr",
                title="🐝 Swarm Job",
                border_style="green"
            ))

        if wait and not self.json_output:
            await self.wait_for_job(job_id)

        return job_id

    async def status(self, job_id: str):
        """Get job status"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/jobs/{job_id}")
            response.raise_for_status()
            job = response.json()
        except Exception as e:
            self._output({"error": str(e)}, f"[red]Failed to get status: {e}[/red]")
            return

        if self.json_output:
            print(json_lib.dumps(job, default=str))
            return

        status = job.get("status", "UNKNOWN")
        status_colors = {
            "PENDING": "yellow",
            "CLAIMED": "blue",
            "EXECUTING": "cyan",
            "COMPLETED": "green",
            "FAILED": "red"
        }
        color = status_colors.get(status, "white")

        lines = [
            f"[bold]Status:[/bold] [{color}]{status}[/]",
            f"[bold]Created:[/bold] {job.get('created_at', 'N/A')[:19]}",
        ]
        
        if job.get("seller_address"):
            lines.append(f"[bold]Worker:[/bold] {job['seller_address'][:12]}...")
        if job.get("execution_duration_seconds"):
            lines.append(f"[bold]Duration:[/bold] {job['execution_duration_seconds']:.1f}s")
        if job.get("total_cost_usd"):
            lines.append(f"[bold]Cost:[/bold] ${job['total_cost_usd']:.6f}")

        console.print(Panel("\n".join(lines), title=f"Job {job_id[:12]}...", border_style=color))

        if status == "COMPLETED" and job.get("result_output"):
            console.print("\n[bold]Output:[/bold]")
            output = job["result_output"]
            if len(output) > 1000:
                output = output[:1000] + "\n...[truncated]"
            console.print(Panel(output, border_style="green"))

        if status == "FAILED" and job.get("result_error"):
            console.print("\n[bold red]Error:[/bold red]")
            console.print(Panel(job["result_error"], border_style="red"))

    async def wait_for_job(self, job_id: str):
        """Wait for job completion with live status"""
        console.print("\n[cyan]Waiting for job completion...[/cyan]\n")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.fields[status]}"),
            console=console
        ) as progress:
            task = progress.add_task("Processing", total=100, status="PENDING")
            
            while True:
                try:
                    response = await self.client.get(f"{self.base_url}/api/v1/jobs/{job_id}")
                    job = response.json()
                    status = job.get("status", "UNKNOWN")
                    
                    if status == "PENDING":
                        progress.update(task, completed=10, status="⏳ Waiting for worker")
                    elif status == "CLAIMED":
                        progress.update(task, completed=30, status="🎯 Worker claimed")
                    elif status == "EXECUTING":
                        progress.update(task, completed=60, status="⚡ Computing...")
                    elif status == "COMPLETED":
                        progress.update(task, completed=100, status="✓ Done!")
                        break
                    elif status == "FAILED":
                        progress.update(task, completed=100, status="✗ Failed")
                        break
                    
                    await asyncio.sleep(2)
                except Exception:
                    await asyncio.sleep(2)
        
        await self.status(job_id)

    async def download(self, job_id: str, output_dir: str = "."):
        """Download job results"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/jobs/{job_id}/files")
            if response.status_code != 200:
                self._output({"error": "No files available"}, "[yellow]No files available for download[/yellow]")
                return
            
            files = response.json().get("files", [])
            output_files = [f for f in files if f.get("file_type") == "output"]
            
            if not output_files:
                self._output({"error": "No output files"}, "[yellow]No output files found[/yellow]")
                return
            
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            downloaded = []
            for file_info in output_files:
                file_name = file_info.get("file_name", "output")
                download_url = file_info.get("download_url")
                
                if download_url:
                    file_response = await self.client.get(download_url)
                    if file_response.status_code == 200:
                        dest = output_path / file_name
                        dest.write_bytes(file_response.content)
                        downloaded.append(str(dest))
                        if not self.json_output:
                            console.print(f"[green]✓ Downloaded: {dest}[/green]")
            
            if self.json_output:
                print(json_lib.dumps({"downloaded": downloaded}))
            
        except Exception as e:
            self._output({"error": str(e)}, f"[red]Download failed: {e}[/red]")

    async def nodes(self):
        """List available nodes"""
        try:
            response = await self.client.get(f"{self.base_url}/api/v1/stats")
            response.raise_for_status()
            stats = response.json()
        except Exception as e:
            self._output({"error": str(e)}, f"[red]Failed to get nodes: {e}[/red]")
            return

        if self.json_output:
            print(json_lib.dumps(stats, default=str))
            return

        table = Table(title="🐝 Available Hives", show_header=True, header_style="bold yellow")
        table.add_column("GPU Type", style="cyan")
        table.add_column("Count", justify="right")
        table.add_column("Price Range", justify="right", style="green")

        by_gpu = stats.get("nodes", {}).get("by_gpu_type", {})
        for gpu_type, info in by_gpu.items():
            table.add_row(
                gpu_type.upper(),
                str(info["count"]),
                f"${info['min_price']:.2f} - ${info['max_price']:.2f}/hr"
            )

        console.print(table)
        console.print(f"\n[dim]Total Active: {stats['nodes']['total_active']}[/dim]")

    async def balance(self):
        """Show wallet balance"""
        from src.payments import PaymentProcessor
        
        if not self.config.buyer_private_key:
            self._output({"error": "No wallet configured"}, "[yellow]No wallet configured. Set BUYER_PRIVATE_KEY in .env[/yellow]")
            return

        try:
            pp = PaymentProcessor(
                private_key=self.config.buyer_private_key,
                rpc_url=self.config.rpc_url,
                usdc_address=self.config.usdc_contract_address,
                network=self.config.network
            )
            balance = pp.get_usdc_balance()
            
            if self.json_output:
                print(json_lib.dumps({
                    "address": pp.address,
                    "network": self.config.network,
                    "usdc_balance": float(balance)
                }))
            else:
                console.print(Panel(
                    f"[bold]Address:[/bold] {pp.address}\n"
                    f"[bold]Network:[/bold] {self.config.network}\n"
                    f"[bold]USDC Balance:[/bold] [green]${balance:.6f}[/green]",
                    title="💰 Wallet",
                    border_style="yellow"
                ))
        except Exception as e:
            self._output({"error": str(e)}, f"[red]Failed to get balance: {e}[/red]")

    async def close(self):
        await self.client.aclose()


def main():
    parser = argparse.ArgumentParser(
        prog="swarm",
        description="🐝 ComputeSwarm CLI - Decentralized GPU Compute",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  swarm submit --model meta-llama/Llama-2-7b-hf --wait
  swarm submit --script train.py --wait
  swarm status abc123 --json
  swarm download abc123 --output ./results
  swarm nodes --json
  swarm balance
        """
    )
    
    # Global --json flag
    parser.add_argument("--json", "-j", action="store_true", help="Output in JSON format (for scripting/agents)")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit a job")
    submit_parser.add_argument("--model", "-m", help="Model name (e.g., llama3)")
    submit_parser.add_argument("--data", "-d", help="Path to data file")
    submit_parser.add_argument("--script", "-s", help="Path to Python script")
    submit_parser.add_argument("--template", "-t", help="Use a job template")
    submit_parser.add_argument("--wait", "-w", action="store_true", help="Wait for completion")
    submit_parser.add_argument("--max-price", type=float, default=10.0, help="Max $/hr")
    submit_parser.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds")

    # Status command
    status_parser = subparsers.add_parser("status", help="Get job status")
    status_parser.add_argument("job_id", help="Job ID")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download job results")
    download_parser.add_argument("job_id", help="Job ID")
    download_parser.add_argument("--output", "-o", default=".", help="Output directory")

    # Nodes command
    subparsers.add_parser("nodes", help="List available nodes")

    # Balance command
    subparsers.add_parser("balance", help="Show wallet balance")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    async def run():
        cli = SwarmCLI(json_output=args.json)
        try:
            if args.command == "submit":
                await cli.submit(
                    model=args.model,
                    data=args.data,
                    script=args.script,
                    template=args.template,
                    wait=args.wait,
                    max_price=args.max_price,
                    timeout=args.timeout
                )
            elif args.command == "status":
                await cli.status(args.job_id)
            elif args.command == "download":
                await cli.download(args.job_id, args.output)
            elif args.command == "nodes":
                await cli.nodes()
            elif args.command == "balance":
                await cli.balance()
        finally:
            await cli.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
