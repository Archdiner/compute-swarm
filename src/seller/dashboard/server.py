"""
Seller Dashboard Backend
Serves the local "Miner UI" and handles control API
(Track C: Product Builder)
"""

import os
import asyncio
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import structlog
from pathlib import Path

logger = structlog.get_logger()

app = FastAPI(title="ComputeSwarm Seller Dashboard")

# Global State Reference (In production, this would link to the running Agent instance)
# For this PoC, we will simulate the connection or use a shared state object if possible.
class AgentState:
    def __init__(self):
        self.running = False
        self.node_id = os.getenv("NODE_ID", "node_unknown")
        self.wallet_address = os.getenv("SELLER_PRIVATE_KEY", "0x...")[0:10] # Mock
        self.price_per_hour = 0.50
        self.earnings = 0.0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.uptime_start = None
        self.gpu_info = {"name": "Detecting...", "temp": 0}

_state = AgentState()

class ControlRequest(BaseModel):
    action: str

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the single-page dashboard"""
    html_path = Path(__file__).parent / "index.html"
    if html_path.exists():
        return html_path.read_text()
    return "Dashboard HTML not found. Verify installation."

@app.get("/api/status")
async def get_status():
    """Get current agent status"""
    uptime = "00:00:00"
    if _state.running and _state.uptime_start:
        import time
        diff = int(time.time() - _state.uptime_start)
        h = diff // 3600
        m = (diff % 3600) // 60
        s = diff % 60
        uptime = f"{h:02d}:{m:02d}:{s:02d}"

    return {
        "running": _state.running,
        "is_busy": False, # TODO: Hook into Engine
        "node_id": _state.node_id,
        "wallet_address": _state.wallet_address,
        "generated_wallet": False, # TODO: Check if wallet was auto-generated
        "earnings": _state.earnings,
        "jobs_completed": _state.jobs_completed,
        "jobs_failed": _state.jobs_failed,
        "price_per_hour": _state.price_per_hour,
        "uptime": uptime,
        "gpu": _state.gpu_info
    }

@app.post("/api/control/{action}")
async def control_node(action: str):
    """Start/Stop the node"""
    import time
    if action == "start":
        if _state.running:
            return {"message": "Already running"}
        _state.running = True
        _state.uptime_start = time.time()
        # TODO: Actually start the Agent Loop background task here
        logger.info("dashboard_command_start_node")
        return {"message": "Node started"}
    
    elif action == "stop":
        if not _state.running:
            return {"message": "Already stopped"}
        _state.running = False
        _state.uptime_start = None
        # TODO: Stop the Agent Loop
        logger.info("dashboard_command_stop_node")
        return {"message": "Node stopped"}
    
    raise HTTPException(status_code=400, detail="Invalid action")

def run_dashboard(host="0.0.0.0", port=3000):
    """Run the dashboard server"""
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    run_dashboard()
