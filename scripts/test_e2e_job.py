
import asyncio
import os
import sys
import time
import signal
import subprocess
import httpx
from pathlib import Path
from multiprocessing import Process

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.config import get_seller_config

MARKETPLACE_PORT = 8002
SELLER_PORT = 8003
MARKETPLACE_URL = f"http://localhost:{MARKETPLACE_PORT}"

def run_marketplace():
    """Run Marketplace API in a separate process with Mock DB"""
    import uvicorn
    import uuid
    from decimal import Decimal
    from datetime import datetime
    import src.database.client
    import src.database

    # --- Mock DB Implementation ---
    class MockDB:
        def __init__(self):
            self.nodes = {}
            self.jobs = {}
            print("🔶 MockDB Initialized")

        async def register_node(self, node):
            # store node as dict
            data = node.model_dump(mode='json')
            self.nodes[node.node_id] = data
            return True

        async def get_active_nodes(self, gpu_type=None, max_price=None):
            return list(self.nodes.values())

        async def get_node(self, node_id):
            return self.nodes.get(node_id)

        async def update_node_heartbeat(self, node_id, available=True, p2p_url=None):
            if node_id in self.nodes:
                self.nodes[node_id]["last_heartbeat"] = datetime.utcnow().isoformat()
                self.nodes[node_id]["is_available"] = available
                if p2p_url:
                    self.nodes[node_id]["p2p_url"] = p2p_url
            return True

        async def set_node_availability(self, node_id, available):
            if node_id in self.nodes:
                self.nodes[node_id]["is_available"] = available
            return True

        async def submit_job(self, job):
            job_id = f"job_{uuid.uuid4().hex[:12]}"
            data = job.model_dump(mode='json')
            data["job_id"] = job_id
            data["status"] = "PENDING"
            data["created_at"] = datetime.utcnow().isoformat()
            self.jobs[job_id] = data
            return job_id

        async def claim_job(self, node_id, seller_address, gpu_type, price_per_hour, vram_gb, num_gpus=1):
            # Find a pending job
            for job_id, job in self.jobs.items():
                if job["status"] == "PENDING":
                    # Simple matching logic (ignore constraints for E2E simplicity or implement basics)
                    job["status"] = "CLAIMED"
                    job["node_id"] = node_id
                    job["seller_address"] = seller_address
                    job["locked_price_per_hour"] = float(price_per_hour)
                    return job
            return None

        async def start_job_execution(self, job_id):
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = "EXECUTING"
                self.jobs[job_id]["started_at"] = datetime.utcnow().isoformat()
            return True

        async def complete_job(self, job_id, output, exit_code, execution_duration, total_cost, payment_tx_hash=None):
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = "COMPLETED"
                self.jobs[job_id]["output"] = output
                self.jobs[job_id]["exit_code"] = exit_code
                self.jobs[job_id]["total_cost"] = float(total_cost)
                self.jobs[job_id]["ended_at"] = datetime.utcnow().isoformat()
            return True

        async def fail_job(self, job_id, error, exit_code=None, execution_duration=None):
            if job_id in self.jobs:
                self.jobs[job_id]["status"] = "FAILED"
                self.jobs[job_id]["error"] = error
            return True
            
        async def get_job(self, job_id):
            job = self.jobs.get(job_id)
            if job and job.get("node_id"):
                node = self.nodes.get(job["node_id"])
                if node:
                    job["p2p_url"] = node.get("p2p_url")
            return job
            
        async def get_queue_stats(self):
            return []
            
        async def get_active_sellers_view(self):
            return []

    # --- Patch DB Client ---
    mock_db = MockDB()
    src.database.client.get_db_client = lambda: mock_db
    src.database.get_db_client = lambda: mock_db

    # Clean env vars that might confuse config
    os.environ["Role"] = "Marketplace"
    os.environ["SUPABASE_URL"] = "https://example.supabase.co"
    os.environ["SUPABASE_ANON_KEY"] = "dummy-key"
    
    sys.argv = ["uvicorn", "src.marketplace.server:app", "--host", "0.0.0.0", "--port", str(MARKETPLACE_PORT)]
    from src.marketplace.server import app
    uvicorn.run(app, host="0.0.0.0", port=MARKETPLACE_PORT, log_level="info")

def run_seller():
    """Run Seller Agent in a separate process"""
    # Clean env vars
    os.environ["Role"] = "Seller"
    os.environ["MARKETPLACE_URL"] = MARKETPLACE_URL
    os.environ["SELLER_PORT"] = str(SELLER_PORT)
    
    # We need to run the agent main loop
    # Ideally we'd import and run, but agent.py has if __name__ == "__main__"
    # calling asyncio.run(main()) which is perfect.
    
    cmd = [sys.executable, "src/seller/agent.py"]
    env = os.environ.copy()
    env["MARKETPLACE_URL"] = MARKETPLACE_URL
    
    subprocess.run(cmd, env=env)

async def wait_for_service(url, name, retries=10):
    async with httpx.AsyncClient() as client:
        for i in range(retries):
            try:
                await client.get(url)
                print(f"✅ {name} is up!")
                return True
            except:
                print(f"Waiting for {name}...")
                await asyncio.sleep(1)
    print(f"❌ {name} failed to start.")
    return False

async def run_test():
    print("=== STARTING E2E 'FIRST CONTACT' TEST ===")
    
    # 1. Start Marketplace
    marketplace_proc = Process(target=run_marketplace, daemon=True)
    marketplace_proc.start()
    
    if not await wait_for_service(f"{MARKETPLACE_URL}/health", "Marketplace"):
        return False

    # 2. Start Seller (as subprocess to keep clean isolation)
    # We use a subprocess for seller to simulate a real separate entity easily
    # and avoid asyncio loop conflicts if we tried to run two loops in one process
    print("Starting Seller Agent...")
    seller_proc = subprocess.Popen(
        [sys.executable, "src/seller/agent.py", "--port", "8010"],
        env={**os.environ, "MARKETPLACE_URL": MARKETPLACE_URL, "PYTHONUNBUFFERED": "1", "SELLER_PORT": "8010", "DOCKER_ENABLED": "false"},
        stdout=sys.stdout,
        stderr=sys.stderr
    )
    
    # Wait for seller to register (we can poll marketplace nodes)
    print("Waiting for Seller to register...")
    node_id = None
    async with httpx.AsyncClient() as client:
        for _ in range(30):
            resp = await client.get(f"{MARKETPLACE_URL}/api/v1/nodes")
            data = resp.json()
            nodes = data.get("nodes", [])
            if nodes:
                node_id = nodes[0]["node_id"]
                print(f"✅ Seller registered! Node ID: {node_id}")
                break
            await asyncio.sleep(1)
            
    if node_id:
        print("Waiting for P2P URL to be advertised via heartbeat...")
        async with httpx.AsyncClient() as client:
            for _ in range(40): # Wait up to 40s for heartbeat
                resp = await client.get(f"{MARKETPLACE_URL}/api/v1/nodes")
                data = resp.json()
                nodes = data.get("nodes", [])
                if nodes and nodes[0].get("p2p_url"):
                    print(f"✅ P2P URL active: {nodes[0]['p2p_url']}")
                    break
                await asyncio.sleep(1)
            
    if not node_id:
        print("❌ Seller failed to register.")
        seller_proc.terminate()
        marketplace_proc.terminate()
        return False

    # 3. Submit Job
    print("Submitting Job...")
    job_id = None
    buyer_address = "0xbuyer123"
    
    # Simple job: Print, calculate, sleep briefly
    # Simple job: Print, calculate, and create a fake checkpoint file
    script = """
import time
import os
from pathlib import Path

print('Hello E2E World!')
# Simulate checkpoint creation (CheckpointManager expects them in 'checkpoints/' folder)
checkpoint_dir = Path('checkpoints')
checkpoint_dir.mkdir(exist_ok=True)
with open(checkpoint_dir / 'adapter_model.safetensors', 'w') as f:
    f.write('fake-weights-data')

print('Checkpoint created.')
time.sleep(1)
"""
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{MARKETPLACE_URL}/api/v1/jobs/submit",
            json={
                "buyer_address": buyer_address,
                "script": script,
                "requirements": "",
                "timeout_seconds": 60,
                "max_price_per_hour": 1.0,
                "gpu_type": "cpu" # Force CPU for local test if needed, or let it match
            }
        )
        if resp.status_code not in (200, 201):
            print(f"❌ Job submission failed: {resp.text}")
            return False
            
        job_data = resp.json()
        job_id = job_data["job_id"]
        print(f"✅ Job submitted! ID: {job_id}")

    # 4. Wait for Execution
    print("Waiting for execution...")
    success = False
    async with httpx.AsyncClient() as client:
        for _ in range(60):
            resp = await client.get(f"{MARKETPLACE_URL}/api/v1/jobs/{job_id}")
            job = resp.json()
            status = job["status"]
            print(f"Job Status: {status}")
            
            if status == "COMPLETED":
                print("✅ Job Completed!")
                print(f"Output:\n{job.get('output', 'No output recorded')}")
                
                # Verify P2P Download
                p2p_url = job.get("p2p_url")
                if p2p_url:
                    print(f"🔗 P2P URL detected: {p2p_url}")
                    
                    # Diagnostics: list files
                    from pathlib import Path
                    p2p_dir = Path("public_checkpoints")
                    if p2p_dir.exists():
                        print(f"📂 Contents of {p2p_dir.absolute()}:")
                        for f in p2p_dir.glob("**/*"):
                            if f.is_file():
                                print(f"  - {f.name} ({f.stat().st_size} bytes)")
                    else:
                        print(f"❌ {p2p_dir.absolute()} does not exist!")

                    # In E2E, we need to wait for the FileServer to actually have the file
                    # The seller agent copies it after completion.
                    print("Attempting to download checkpoint via P2P...")
                    try:
                        # The filename is {job_id}_adapter_model.safetensors (mocked in our test script below)
                        checkpoint_name = f"{job_id}_adapter_model.safetensors"
                        dl_resp = await client.get(f"{p2p_url}/files/{checkpoint_name}", timeout=10.0)
                        if dl_resp.status_code == 200:
                            print(f"✅ P2P Download Successful! Size: {len(dl_resp.content)} bytes")
                            success = True
                        else:
                            print(f"❌ P2P Download Failed: {dl_resp.status_code}")
                    except Exception as e:
                        print(f"❌ P2P Download Error: {str(e)}")
                else:
                    print("❌ No P2P URL found in job status")
                break
            elif status == "FAILED":
                print(f"❌ Job Failed! Error: {job.get('error')}")
                break
                
            await asyncio.sleep(1)

    # Cleanup
    print("Stopping services...")
    seller_proc.terminate()
    marketplace_proc.terminate()
    
    return success

if __name__ == "__main__":
    try:
        if asyncio.run(run_test()):
            print("🚀 E2E TEST PASSED")
            sys.exit(0)
        else:
            print("💥 E2E TEST FAILED")
            sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted")
