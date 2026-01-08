"""
Swarm CLI - Buyer/Agent Job Submission Tool
Usage:
  python src/buyer/cli.py submit --template lora_finetune --params '{"base_model": "...", "dataset_name": "..."}'
  python src/buyer/cli.py status <job_id>
  python src/buyer/cli.py download <job_id>
"""

import os
import json
import time
import argparse
import httpx
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

MARKETPLACE_URL = os.getenv("MARKETPLACE_URL", "http://localhost:8000")
BUYER_ADDRESS = os.getenv("BUYER_ADDRESS", "0x0000000000000000000000000000000000000000")

class SwarmCLI:
    def __init__(self, marketplace_url: str = MARKETPLACE_URL):
        self.url = marketplace_url
        self.client = httpx.Client(timeout=30.0)

    def submit_job(self, template: str, parameters: Dict[str, Any], max_price: float = 1.0) -> str:
        """Submit a job via template"""
        print(f"Submitting {template} job to {self.url}...")
        
        payload = {
            "buyer_address": BUYER_ADDRESS,
            "template_name": template,
            "parameters": parameters,
            "max_price_per_hour": max_price
        }
        
        # Note: In the actual server, we might use a different endpoint for template-based submission
        # For the POC, we assume the marketplace has an endpoint for this or we map it to the raw script.
        # Here we mock the behavior of converting template to script if needed.
        
        response = self.client.post(f"{self.url}/api/v1/jobs/submit_template", json=payload)
        response.raise_for_status()
        job_id = response.json()["job_id"]
        print(f"✓ Job Submitted! ID: {job_id}")
        return job_id

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """Poll job status"""
        response = self.client.get(f"{self.url}/api/v1/jobs/{job_id}")
        response.raise_for_status()
        return response.json()

    async def wait_for_job(self, job_id: str, poll_interval: int = 10):
        """Wait until job is completed and print progress"""
        print(f"Waiting for job {job_id} to complete...")
        while True:
            status = self.get_status(job_id)
            state = status["status"]
            print(f"   Status: {state} | Progress: {status.get('progress', 0)}%")
            
            if state == "COMPLETED":
                print("🎉 Job Completed Successfully!")
                return status
            if state == "FAILED":
                print(f"❌ Job Failed: {status.get('error')}")
                return status
            
            await asyncio.sleep(poll_interval)

    def download_results(self, job_id: str, output_dir: str = "results"):
        """Download output files using P2P URL if available"""
        status = self.get_status(job_id)
        if status["status"] != "COMPLETED":
            print("Job not completed yet.")
            return

        p2p_url = status.get("p2p_url")
        if not p2p_url:
            print("No P2P delivery URL found. Falling back to central storage (TODO).")
            return

        print(f"Downloading results from Swarm Tunnel: {p2p_url}...")
        Path(output_dir).mkdir(exist_ok=True)
        
        # In a real scenario, the status would contains a list of files.
        # For the POC, we look for typical LoRA filenames or a known list.
        # We'll try to fetch the file index or just the job_id adapter.
        
        # Test file name based on CheckpointManager implementation: {job_id}_adapter_model.safetensors
        # Actually it depends on what the template saves.
        filename = f"{job_id}_adapter_model.safetensors"
        
        try:
            download_url = f"{p2p_url}/files/{filename}"
            print(f"Fetching {download_url}...")
            response = self.client.get(download_url)
            if response.status_code == 200:
                with open(Path(output_dir) / filename, "wb") as f:
                    f.write(response.content)
                print(f"✓ Downloaded {filename} to {output_dir}/")
            else:
                print(f"Failed to download: {response.status_code}")
        except Exception as e:
            print(f"Download error: {e}")

def main():
    parser = argparse.ArgumentParser(description="ComputeSwarm Buyer CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Submit
    submit_parser = subparsers.add_parser("submit")
    submit_parser.add_argument("--template", required=True)
    submit_parser.add_argument("--params", required=True)
    submit_parser.add_argument("--max_price", type=float, default=1.0)

    # Status
    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("job_id")

    # Wait
    wait_parser = subparsers.add_parser("wait")
    wait_parser.add_argument("job_id")

    # Download
    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("job_id")
    download_parser.add_argument("--output", default="results")

    args = parser.parse_args()
    cli = SwarmCLI()

    if args.command == "submit":
        params = json.loads(args.params)
        cli.submit_job(args.template, params, args.max_price)
    elif args.command == "status":
        print(json.dumps(cli.get_status(args.job_id), indent=2))
    elif args.command == "wait":
        asyncio.run(cli.wait_for_job(args.job_id))
    elif args.command == "download":
        cli.download_results(args.job_id, args.output)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
