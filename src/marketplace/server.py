"""
ComputeSwarm Marketplace Server
FastAPI-based discovery layer for P2P GPU marketplace
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from src.marketplace.models import (
    ComputeNode,
    NodeRegistration,
    NodeStatus,
    X402Manifest,
    GPUType,
    Job,
    JobRequest,
    JobStatus
)
from src.config import get_marketplace_config

# Initialize structured logger
logger = structlog.get_logger()

# In-memory storage (will be replaced with database in Phase 2)
nodes_db: Dict[str, ComputeNode] = {}
jobs_db: Dict[str, Job] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app"""
    config = get_marketplace_config()
    logger.info(
        "marketplace_starting",
        host=config.marketplace_host,
        port=config.marketplace_port,
        network=config.network
    )
    yield
    logger.info("marketplace_shutting_down")


# Initialize FastAPI app
app = FastAPI(
    title="ComputeSwarm Marketplace",
    description="Decentralized P2P GPU Marketplace using x402 protocol",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with basic info"""
    return {
        "name": "ComputeSwarm Marketplace",
        "version": "0.1.0",
        "status": "operational",
        "x402_manifest": "/x402.json"
    }


@app.get("/x402.json", response_model=X402Manifest)
async def get_x402_manifest():
    """
    x402 protocol manifest
    Machine-readable specification for payment protocol
    """
    config = get_marketplace_config()
    manifest = X402Manifest(
        version="1.0",
        name="ComputeSwarm",
        description="Decentralized P2P GPU Marketplace for the Agentic Economy",
        payment_methods=["x402-usdc-base"],
        supported_networks=[config.network],
        endpoints={
            "discovery": "/api/v1/nodes",
            "register": "/api/v1/nodes/register",
            "submit_job": "/api/v1/jobs/submit",
            "job_status": "/api/v1/jobs/{job_id}",
            "heartbeat": "/api/v1/nodes/{node_id}/heartbeat"
        }
    )
    return manifest


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_nodes": len([n for n in nodes_db.values() if n.status == NodeStatus.AVAILABLE]),
        "total_nodes": len(nodes_db),
        "active_jobs": len([j for j in jobs_db.values() if j.status == JobStatus.RUNNING])
    }


# ============================================================================
# Node Management Endpoints
# ============================================================================

@app.post("/api/v1/nodes/register", response_model=ComputeNode, status_code=status.HTTP_201_CREATED)
async def register_node(registration: NodeRegistration):
    """
    Register a new compute node in the marketplace
    Called by Seller Agent on startup
    """
    node_id = f"node_{uuid.uuid4()}"

    node = ComputeNode(
        node_id=node_id,
        seller_address=registration.seller_address,
        gpu_info=registration.gpu_info,
        price_per_hour=registration.price_per_hour,
        endpoint=registration.endpoint,
        status=NodeStatus.AVAILABLE
    )

    nodes_db[node_id] = node

    logger.info(
        "node_registered",
        node_id=node_id,
        seller=registration.seller_address,
        gpu_type=registration.gpu_info.gpu_type,
        price=registration.price_per_hour
    )

    return node


@app.get("/api/v1/nodes", response_model=List[ComputeNode])
async def list_nodes(
    gpu_type: Optional[GPUType] = None,
    max_price: Optional[float] = None,
    status_filter: Optional[NodeStatus] = None
):
    """
    Discover available compute nodes
    Called by Buyer Agent to find suitable hardware
    """
    nodes = list(nodes_db.values())

    # Apply filters
    if gpu_type:
        nodes = [n for n in nodes if n.gpu_info.gpu_type == gpu_type]

    if max_price:
        nodes = [n for n in nodes if n.price_per_hour <= max_price]

    if status_filter:
        nodes = [n for n in nodes if n.status == status_filter]
    else:
        # Default: only show available nodes
        nodes = [n for n in nodes if n.status == NodeStatus.AVAILABLE]

    # Sort by price (ascending)
    nodes.sort(key=lambda n: n.price_per_hour)

    logger.info("nodes_listed", count=len(nodes), filters={
        "gpu_type": gpu_type,
        "max_price": max_price,
        "status": status_filter
    })

    return nodes


@app.get("/api/v1/nodes/{node_id}", response_model=ComputeNode)
async def get_node(node_id: str):
    """Get details for a specific node"""
    if node_id not in nodes_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )
    return nodes_db[node_id]


@app.post("/api/v1/nodes/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, node_status: NodeStatus):
    """
    Update node heartbeat and status
    Called periodically by Seller Agent
    """
    if node_id not in nodes_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )

    node = nodes_db[node_id]
    node.last_heartbeat = datetime.utcnow()
    node.status = node_status

    logger.debug("heartbeat_received", node_id=node_id, status=node_status)

    return {"status": "ok", "node_id": node_id}


@app.delete("/api/v1/nodes/{node_id}")
async def unregister_node(node_id: str):
    """
    Unregister a compute node
    Called by Seller Agent on shutdown
    """
    if node_id not in nodes_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )

    node = nodes_db.pop(node_id)
    logger.info("node_unregistered", node_id=node_id, seller=node.seller_address)

    return {"status": "unregistered", "node_id": node_id}


# ============================================================================
# Job Management Endpoints
# ============================================================================

@app.post("/api/v1/jobs/submit", response_model=Job, status_code=status.HTTP_201_CREATED)
async def submit_job(job_request: JobRequest, node_id: str, buyer_address: str):
    """
    Submit a job to a specific node
    This creates the job record; actual execution happens on the seller node
    """
    if node_id not in nodes_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )

    node = nodes_db[node_id]
    if node.status != NodeStatus.AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Node {node_id} is not available (status: {node.status})"
        )

    job_id = f"job_{uuid.uuid4()}"

    job = Job(
        job_id=job_id,
        buyer_address=buyer_address,
        node_id=node_id,
        job_request=job_request,
        status=JobStatus.PENDING
    )

    jobs_db[job_id] = job

    # Mark node as busy
    node.status = NodeStatus.BUSY

    logger.info(
        "job_submitted",
        job_id=job_id,
        buyer=buyer_address,
        node_id=node_id,
        job_type=job_request.job_type
    )

    return job


@app.get("/api/v1/jobs/{job_id}", response_model=Job)
async def get_job_status(job_id: str):
    """Get the status and details of a job"""
    if job_id not in jobs_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    return jobs_db[job_id]


@app.get("/api/v1/jobs", response_model=List[Job])
async def list_jobs(buyer_address: Optional[str] = None, node_id: Optional[str] = None):
    """List all jobs, optionally filtered by buyer or node"""
    jobs = list(jobs_db.values())

    if buyer_address:
        jobs = [j for j in jobs if j.buyer_address == buyer_address]

    if node_id:
        jobs = [j for j in jobs if j.node_id == node_id]

    # Sort by creation time (most recent first)
    jobs.sort(key=lambda j: j.created_at, reverse=True)

    return jobs


# ============================================================================
# Statistics and Monitoring
# ============================================================================

@app.get("/api/v1/stats")
async def get_marketplace_stats():
    """Get marketplace statistics"""
    total_nodes = len(nodes_db)
    available_nodes = len([n for n in nodes_db.values() if n.status == NodeStatus.AVAILABLE])

    gpu_types = {}
    for node in nodes_db.values():
        gpu_type = node.gpu_info.gpu_type.value
        gpu_types[gpu_type] = gpu_types.get(gpu_type, 0) + 1

    total_jobs = len(jobs_db)
    completed_jobs = len([j for j in jobs_db.values() if j.status == JobStatus.COMPLETED])

    total_compute_hours = sum(n.total_compute_hours for n in nodes_db.values())

    return {
        "nodes": {
            "total": total_nodes,
            "available": available_nodes,
            "by_gpu_type": gpu_types
        },
        "jobs": {
            "total": total_jobs,
            "completed": completed_jobs,
            "active": len([j for j in jobs_db.values() if j.status == JobStatus.RUNNING])
        },
        "compute_hours": total_compute_hours,
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    config = get_marketplace_config()

    uvicorn.run(
        "src.marketplace.server:app",
        host=config.marketplace_host,
        port=config.marketplace_port,
        reload=config.reload,
        log_level=config.log_level.lower()
    )
