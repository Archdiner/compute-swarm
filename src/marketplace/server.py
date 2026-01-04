"""
ComputeSwarm Marketplace Server
Queue-based job marketplace with Supabase database
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from contextlib import asynccontextmanager
from decimal import Decimal

from fastapi import FastAPI, HTTPException, status, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from src.marketplace.models import (
    NodeRegistration,
    X402Manifest,
    GPUType,
)
from src.models import JobStatus, ComputeJob
from src.config import get_marketplace_config
from src.database import get_db_client

# Initialize structured logger
logger = structlog.get_logger()


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

    # Initialize database client
    try:
        db = get_db_client()
        logger.info("database_connected", database="supabase")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise

    # Start background maintenance tasks
    import asyncio
    maintenance_task = asyncio.create_task(run_maintenance_tasks())

    yield

    # Cleanup
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass

    logger.info("marketplace_shutting_down")


async def run_maintenance_tasks():
    """Background task to clean up stale jobs and claims"""
    db = get_db_client()

    while True:
        try:
            await asyncio.sleep(60)  # Run every minute

            # Release stale claims (claimed but not started in 5 minutes)
            released = await db.release_stale_claims(stale_minutes=5)
            if released > 0:
                logger.info("stale_claims_released", count=released)

            # Mark stale executions as failed (executing > 2x timeout)
            failed = await db.mark_stale_executions_failed(timeout_multiplier=2.0)
            if failed > 0:
                logger.warning("stale_executions_marked_failed", count=failed)

        except asyncio.CancelledError:
            logger.info("maintenance_tasks_stopped")
            raise
        except Exception as e:
            logger.error("maintenance_task_error", error=str(e))


# Initialize rate limiter
# Key function extracts client identifier for rate limiting
def get_client_key(request: Request) -> str:
    """Get client identifier for rate limiting - uses IP address"""
    return get_remote_address(request)


def get_buyer_key(request: Request) -> str:
    """Get buyer address for rate limiting job submissions"""
    buyer = request.query_params.get("buyer_address", "")
    if buyer:
        return buyer
    return get_remote_address(request)


def get_node_key(request: Request) -> str:
    """Get node_id for rate limiting seller operations"""
    node_id = request.query_params.get("node_id", "")
    if node_id:
        return node_id
    return get_remote_address(request)


limiter = Limiter(key_func=get_client_key)

# Initialize FastAPI app
app = FastAPI(
    title="ComputeSwarm Marketplace",
    description="Decentralized P2P GPU Marketplace using x402 protocol",
    version="0.1.0",
    lifespan=lifespan
)

# Attach limiter to app state and add exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with configurable origins
config = get_marketplace_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
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
    db = get_db_client()

    try:
        # Get statistics from database
        stats = await db.get_queue_stats()
        active_sellers = await db.get_active_sellers_view()

        status_counts = {s["status"]: s["job_count"] for s in stats}

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "connected",
            "active_nodes": len(active_sellers),
            "jobs": {
                "pending": status_counts.get("PENDING", 0),
                "executing": status_counts.get("EXECUTING", 0),
                "completed": status_counts.get("COMPLETED", 0),
                "failed": status_counts.get("FAILED", 0)
            }
        }
    except Exception as e:
        logger.error("health_check_failed", error=str(e))
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }, 503


# ============================================================================
# Node Management Endpoints
# ============================================================================

@app.post("/api/v1/nodes/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_node(request: Request, registration: NodeRegistration):
    """
    Register a new compute node in the marketplace
    Called by Seller Agent on startup
    """
    db = get_db_client()

    from src.models import ComputeNode
    node_id = f"node_{uuid.uuid4().hex[:12]}"

    node = ComputeNode(
        node_id=node_id,
        seller_address=registration.seller_address,
        gpu_info=registration.gpu_info,
        price_per_hour=registration.price_per_hour,
        is_available=True
    )

    await db.register_node(node)

    logger.info(
        "node_registered",
        node_id=node_id,
        seller=registration.seller_address,
        gpu_type=registration.gpu_info.gpu_type.value,
        price=float(registration.price_per_hour)
    )

    return {
        "node_id": node_id,
        "seller_address": node.seller_address,
        "gpu_info": {
            "gpu_type": node.gpu_info.gpu_type.value,
            "device_name": node.gpu_info.device_name,
            "vram_gb": float(node.gpu_info.vram_gb) if node.gpu_info.vram_gb else None,
            "compute_capability": node.gpu_info.compute_capability
        },
        "price_per_hour": float(node.price_per_hour),
        "is_available": node.is_available
    }


@app.get("/api/v1/nodes")
@limiter.limit("100/minute")
async def list_nodes(
    request: Request,
    gpu_type: Optional[str] = None,
    max_price: Optional[float] = None,
):
    """
    Discover available compute nodes
    Shows only nodes with recent heartbeat (active)
    """
    db = get_db_client()

    gpu_type_enum = GPUType(gpu_type) if gpu_type else None
    max_price_decimal = Decimal(str(max_price)) if max_price else None

    nodes = await db.get_active_nodes(
        gpu_type=gpu_type_enum,
        max_price=max_price_decimal
    )

    logger.info("nodes_listed", count=len(nodes), filters={
        "gpu_type": gpu_type,
        "max_price": max_price
    })

    return {"nodes": nodes, "count": len(nodes)}


@app.get("/api/v1/nodes/{node_id}")
@limiter.limit("100/minute")
async def get_node(request: Request, node_id: str):
    """Get details for a specific node"""
    db = get_db_client()

    node = await db.get_node(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )

    return node


@app.post("/api/v1/nodes/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, available: bool = True):
    """
    Update node heartbeat and availability
    Called periodically by Seller Agent (every 30-60 seconds recommended)
    """
    db = get_db_client()

    try:
        await db.update_node_heartbeat(node_id)
        await db.set_node_availability(node_id, available)

        logger.debug("heartbeat_received", node_id=node_id, available=available)

        return {"status": "ok", "node_id": node_id, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("heartbeat_failed", node_id=node_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update heartbeat: {str(e)}"
        )


@app.post("/api/v1/nodes/{node_id}/unavailable")
async def mark_node_unavailable(node_id: str):
    """
    Mark node as unavailable (busy with job or going offline)
    Called by Seller Agent before executing job or shutdown
    """
    db = get_db_client()

    await db.set_node_availability(node_id, False)
    logger.info("node_marked_unavailable", node_id=node_id)

    return {"status": "unavailable", "node_id": node_id}


# ============================================================================
# Job Management Endpoints (Queue-Based)
# ============================================================================

@app.post("/api/v1/jobs/submit", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_buyer_key)
async def submit_job(
    request: Request,
    buyer_address: str,
    script: str,
    requirements: Optional[str] = None,
    max_price_per_hour: float = 10.0,
    timeout_seconds: int = 3600,
    required_gpu_type: Optional[str] = None,
    min_vram_gb: Optional[float] = None,
    num_gpus: int = 1
):
    """
    Submit a job to the queue
    Job will be picked up by matching seller nodes

    Queue-based system: Buyer just submits, sellers claim when available
    """
    db = get_db_client()

    job = ComputeJob(
        buyer_address=buyer_address,
        script=script,
        requirements=requirements,
        max_price_per_hour=Decimal(str(max_price_per_hour)),
        timeout_seconds=timeout_seconds,
        required_gpu_type=GPUType(required_gpu_type) if required_gpu_type else None,
        min_vram_gb=Decimal(str(min_vram_gb)) if min_vram_gb else None,
        num_gpus=num_gpus
    )

    job_id = await db.submit_job(job)

    logger.info(
        "job_submitted_to_queue",
        job_id=job_id,
        buyer=buyer_address,
        max_price=float(max_price_per_hour),
        gpu_type=required_gpu_type
    )

    return {
        "job_id": job_id,
        "status": "PENDING",
        "message": "Job submitted to queue. Sellers will claim when available.",
        "buyer_address": buyer_address,
        "max_price_per_hour": max_price_per_hour
    }


@app.post("/api/v1/jobs/claim")
@limiter.limit("30/minute", key_func=get_node_key)
async def claim_job(
    request: Request,
    node_id: str,
    seller_address: str,
    gpu_type: str,
    price_per_hour: float,
    vram_gb: float,
    num_gpus: int = 1
):
    """
    Claim the next available job from queue (Seller endpoint)
    Atomically assigns job to seller

    This is called by seller agents polling for work
    """
    db = get_db_client()

    try:
        gpu_type_enum = GPUType(gpu_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid GPU type: {gpu_type}"
        )

    job = await db.claim_job(
        node_id=node_id,
        seller_address=seller_address,
        gpu_type=gpu_type_enum,
        price_per_hour=Decimal(str(price_per_hour)),
        vram_gb=Decimal(str(vram_gb)),
        num_gpus=num_gpus
    )

    if not job:
        return {
            "claimed": False,
            "message": "No matching jobs available in queue"
        }

    logger.info(
        "job_claimed",
        job_id=job["job_id"],
        node_id=node_id,
        seller=seller_address
    )

    return {
        "claimed": True,
        "job_id": job["job_id"],
        "script": job["script"],
        "requirements": job["requirements"],
        "timeout_seconds": job["timeout_seconds"],
        "max_price_per_hour": float(job["max_price_per_hour"]),
        "buyer_address": job.get("buyer_address", ""),
        "num_gpus": job.get("num_gpus", 1)
    }


@app.post("/api/v1/jobs/{job_id}/start")
async def start_job_execution(job_id: str):
    """
    Mark job as executing (Seller endpoint)
    Called when seller actually starts running the job
    """
    db = get_db_client()

    try:
        await db.start_job_execution(job_id)

        logger.info("job_execution_started", job_id=job_id)

        return {
            "status": "EXECUTING",
            "job_id": job_id,
            "started_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error("job_start_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start job: {str(e)}"
        )


@app.post("/api/v1/jobs/{job_id}/complete")
async def complete_job(
    job_id: str,
    output: str,
    exit_code: int,
    execution_duration: float,
    total_cost: float,
    payment_tx_hash: Optional[str] = None
):
    """
    Mark job as completed with results (Seller endpoint)
    Called when job finishes successfully
    """
    db = get_db_client()

    try:
        await db.complete_job(
            job_id=job_id,
            output=output,
            exit_code=exit_code,
            execution_duration=Decimal(str(execution_duration)),
            total_cost=Decimal(str(total_cost)),
            payment_tx_hash=payment_tx_hash
        )

        logger.info(
            "job_completed",
            job_id=job_id,
            exit_code=exit_code,
            duration=execution_duration,
            cost=total_cost
        )

        return {
            "status": "COMPLETED",
            "job_id": job_id,
            "exit_code": exit_code,
            "total_cost": total_cost
        }

    except Exception as e:
        logger.error("job_completion_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete job: {str(e)}"
        )


@app.post("/api/v1/jobs/{job_id}/fail")
async def fail_job(
    job_id: str,
    error: str,
    exit_code: Optional[int] = None,
    execution_duration: Optional[float] = None
):
    """
    Mark job as failed (Seller endpoint)
    Called when job execution fails
    """
    db = get_db_client()

    try:
        await db.fail_job(
            job_id=job_id,
            error=error,
            exit_code=exit_code,
            execution_duration=Decimal(str(execution_duration)) if execution_duration else None
        )

        logger.warning("job_failed", job_id=job_id, error=error[:200])

        return {
            "status": "FAILED",
            "job_id": job_id,
            "error": error
        }

    except Exception as e:
        logger.error("job_failure_reporting_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to report job failure: {str(e)}"
        )


@app.post("/api/v1/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, buyer_address: str):
    """
    Cancel a pending or claimed job (Buyer endpoint)
    Only works if job hasn't started executing yet
    """
    db = get_db_client()

    cancelled = await db.cancel_job(job_id, buyer_address)

    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job cannot be cancelled (not found, wrong buyer, or already executing)"
        )

    logger.info("job_cancelled", job_id=job_id, buyer=buyer_address)

    return {
        "status": "CANCELLED",
        "job_id": job_id
    }


@app.get("/api/v1/jobs/{job_id}")
@limiter.limit("100/minute")
async def get_job_status(request: Request, job_id: str):
    """Get the status and details of a job"""
    db = get_db_client()

    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    return job


@app.get("/api/v1/jobs/buyer/{buyer_address}")
@limiter.limit("100/minute")
async def list_buyer_jobs(
    request: Request,
    buyer_address: str,
    status_filter: Optional[str] = None,
    limit: int = 50
):
    """List jobs for a specific buyer"""
    db = get_db_client()

    status_enum = JobStatus(status_filter) if status_filter else None

    jobs = await db.get_jobs_by_buyer(
        buyer_address=buyer_address,
        status=status_enum,
        limit=limit
    )

    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/v1/jobs/seller/{seller_address}")
@limiter.limit("100/minute")
async def list_seller_jobs(
    request: Request,
    seller_address: str,
    status_filter: Optional[str] = None,
    limit: int = 50
):
    """List jobs for a specific seller"""
    db = get_db_client()

    status_enum = JobStatus(status_filter) if status_filter else None

    jobs = await db.get_jobs_by_seller(
        seller_address=seller_address,
        status=status_enum,
        limit=limit
    )

    return {"jobs": jobs, "count": len(jobs)}


@app.get("/api/v1/jobs/queue/pending")
@limiter.limit("100/minute")
async def get_pending_jobs(request: Request, gpu_type: Optional[str] = None, limit: int = 100):
    """
    Get pending jobs in queue (for monitoring/debugging)
    Sellers should use /api/v1/jobs/claim instead
    """
    db = get_db_client()

    gpu_type_enum = GPUType(gpu_type) if gpu_type else None

    jobs = await db.get_pending_jobs(gpu_type=gpu_type_enum, limit=limit)

    return {"jobs": jobs, "count": len(jobs)}


# ============================================================================
# Statistics and Monitoring
# ============================================================================

@app.get("/api/v1/stats")
@limiter.limit("100/minute")
async def get_marketplace_stats(request: Request):
    """Get comprehensive marketplace statistics"""
    db = get_db_client()

    # Get queue statistics
    queue_stats = await db.get_queue_stats()
    active_sellers = await db.get_active_sellers_view()

    # Group by GPU type
    gpu_types = {}
    for seller in active_sellers:
        gpu_type = seller["gpu_type"]
        if gpu_type not in gpu_types:
            gpu_types[gpu_type] = {
                "count": 0,
                "avg_price": 0,
                "min_price": float('inf'),
                "max_price": 0
            }
        gpu_types[gpu_type]["count"] += 1
        price = float(seller["price_per_hour"])
        gpu_types[gpu_type]["min_price"] = min(gpu_types[gpu_type]["min_price"], price)
        gpu_types[gpu_type]["max_price"] = max(gpu_types[gpu_type]["max_price"], price)

    # Calculate average prices
    for gpu_type in gpu_types:
        sellers_of_type = [s for s in active_sellers if s["gpu_type"] == gpu_type]
        if sellers_of_type:
            gpu_types[gpu_type]["avg_price"] = sum(float(s["price_per_hour"]) for s in sellers_of_type) / len(sellers_of_type)

    # Build job statistics
    job_stats = {stat["status"]: stat["job_count"] for stat in queue_stats}

    return {
        "nodes": {
            "total_active": len(active_sellers),
            "by_gpu_type": gpu_types
        },
        "jobs": {
            "pending": job_stats.get("PENDING", 0),
            "claimed": job_stats.get("CLAIMED", 0),
            "executing": job_stats.get("EXECUTING", 0),
            "completed": job_stats.get("COMPLETED", 0),
            "failed": job_stats.get("FAILED", 0),
            "cancelled": job_stats.get("CANCELLED", 0),
            "total": sum(job_stats.values())
        },
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
