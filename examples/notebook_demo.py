"""
ComputeSwarm Notebook Demo
This script demonstrates how to start a Jupyter notebook session programmatically
"""

import asyncio
import httpx


async def start_notebook_session():
    """
    Start a Jupyter notebook session on ComputeSwarm
    """
    marketplace_url = "http://localhost:8000"
    buyer_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5a123"  # Replace with your address
    
    async with httpx.AsyncClient() as client:
        # Start a notebook session
        response = await client.post(
            f"{marketplace_url}/api/v1/sessions/start",
            params={
                "buyer_address": buyer_address,
                "session_type": "notebook_session",
                "max_price_per_hour": 5.0,
                "duration_minutes": 60,
                "required_gpu_type": "cuda"
            }
        )
        
        if response.status_code != 201:
            print(f"Error: {response.text}")
            return
        
        data = response.json()
        job_id = data["job_id"]
        print(f"Session requested! Job ID: {job_id}")
        print("Waiting for session to start...")
        
        # Poll for session URL
        for i in range(30):  # Wait up to 1 minute
            await asyncio.sleep(2)
            
            status_response = await client.get(
                f"{marketplace_url}/api/v1/sessions/{job_id}"
            )
            
            if status_response.status_code == 200:
                session = status_response.json()
                
                if session.get("session_url"):
                    print(f"\n✓ Session is ready!")
                    print(f"  URL: {session['session_url']}")
                    print(f"  Expires: {session.get('expires_at', 'N/A')}")
                    print(f"\nOpen the URL in your browser to access JupyterLab!")
                    return job_id
                
                print(f"  Status: {session.get('job_status', 'PENDING')}")
        
        print("Session is taking too long to start. Check marketplace logs.")
        return job_id


async def stop_notebook_session(job_id: str):
    """
    Stop a notebook session
    """
    marketplace_url = "http://localhost:8000"
    buyer_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f5a123"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{marketplace_url}/api/v1/sessions/{job_id}/stop",
            params={"buyer_address": buyer_address}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Session stopped!")
            print(f"  Billed minutes: {data.get('billed_minutes', 0)}")
            print(f"  Total cost: ${data.get('total_cost_usd', 0):.4f}")
        else:
            print(f"Error stopping session: {response.text}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "stop":
        if len(sys.argv) > 2:
            asyncio.run(stop_notebook_session(sys.argv[2]))
        else:
            print("Usage: python notebook_demo.py stop <job_id>")
    else:
        asyncio.run(start_notebook_session())

