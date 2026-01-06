"""
ComputeSwarm Marketplace Server
Queue-based job marketplace with Supabase database
"""

import os
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
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

    # Initialize database client (optional for health checks)
    try:
        db = get_db_client()
        logger.info("database_connected", database="supabase")
    except Exception as e:
        logger.warning("database_connection_failed", error=str(e))
        logger.warning("app_starting_without_database", message="Some endpoints may not work")
        db = None

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

# Initialize FastAPI app with enhanced documentation
app = FastAPI(
    title="ComputeSwarm Marketplace",
    description="""
    **Decentralized P2P GPU Marketplace with x402 Micropayments**
    
    ComputeSwarm connects GPU sellers with buyers through trustless, per-second USDC payments on Base L2.
    
    ### Features
    - Queue-based job submission and matching
    - x402 protocol for trustless payments
    - Multi-GPU support (NVIDIA CUDA, Apple Silicon MPS)
    - Real-time job monitoring and cost estimation
    - Seller earnings tracking
    
    ### Quick Start
    - Submit jobs: `POST /api/v1/jobs/submit`
    - Check status: `GET /api/v1/jobs/{job_id}`
    - View marketplace: `GET /api/v1/stats`
    
    Built for the x402 Hackathon.
    """,
    version="0.1.0",
    contact={
        "name": "ComputeSwarm",
        "url": "https://github.com/Archdiner/compute-swarm",
    },
    license_info={
        "name": "MIT",
    },
    tags_metadata=[
        {
            "name": "Marketplace",
            "description": "Core marketplace operations - job submission, stats, nodes",
        },
        {
            "name": "Jobs",
            "description": "Job management - submit, monitor, cancel, and track compute jobs",
        },
        {
            "name": "Nodes",
            "description": "GPU node management - registration, heartbeat, availability",
        },
        {
            "name": "Sellers",
            "description": "Seller operations - earnings, job history, profile management",
        },
        {
            "name": "Payments",
            "description": "x402 payment protocol integration",
        },
        {
            "name": "Health",
            "description": "System health and status endpoints",
        },
    ],
    lifespan=lifespan
)

# Attach limiter to app state and add exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with configurable origins
config = get_marketplace_config()
# Default frontend origins for development
default_origins = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]
cors_origins = config.cors_origins if config.cors_origins else default_origins

# Add frontend URL from environment if provided
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in cors_origins:
    cors_origins.append(frontend_url)

logger.info("cors_origins_configured", origins=cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint with basic info"""
    return {
        "name": "ComputeSwarm Marketplace",
        "version": "0.1.0",
        "status": "operational",
        "x402_manifest": "/x402.json"
    }


@app.get("/x402.json", response_model=X402Manifest, tags=["Payments"])
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


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint - works even without database"""
    try:
        # Try to connect to database for full health check
        db = get_db_client()
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
        # Return basic health status if database not configured
        logger.debug("health_check_database_unavailable", error=str(e))
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "database": "not_configured",
            "message": "App is running but database not configured yet"
        }


# ============================================================================
# Node Management Endpoints
# ============================================================================

@app.post("/api/v1/nodes/register", status_code=status.HTTP_201_CREATED, tags=["Nodes"])
@limiter.limit("5/minute")
async def register_node(request: Request, registration: NodeRegistration):
    """
    Register a new compute node in the marketplace
    Called by Seller Agent on startup
    """
    db = get_db_client()

    from src.models import ComputeNode, GPUInfo, GPUType as ModelsGPUType
    node_id = f"node_{uuid.uuid4().hex[:12]}"

    # Convert GPUInfo from marketplace.models to src.models format
    # Use model_dump(mode='python') to ensure enums are converted to their values
    gpu_info_dict = registration.gpu_info.model_dump(mode='python')
    # Convert vram_gb from float to Decimal if present
    if 'vram_gb' in gpu_info_dict and gpu_info_dict['vram_gb'] is not None:
        gpu_info_dict['vram_gb'] = Decimal(str(gpu_info_dict['vram_gb']))
    
    # Ensure gpu_type is converted to the correct enum type from src.models
    if 'gpu_type' in gpu_info_dict:
        gpu_info_dict['gpu_type'] = ModelsGPUType(gpu_info_dict['gpu_type'])
    
    gpu_info = GPUInfo(**gpu_info_dict)
    
    node = ComputeNode(
        node_id=node_id,
        seller_address=registration.seller_address,
        gpu_info=gpu_info,
        price_per_hour=Decimal(str(registration.price_per_hour)),
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


@app.get("/api/v1/nodes", tags=["Marketplace"])
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

@app.post("/api/v1/jobs/estimate", tags=["Jobs"])
@limiter.limit("30/minute")
async def estimate_job_cost(
    request: Request,
    timeout_seconds: int = 3600,
    required_gpu_type: Optional[str] = None,
    min_vram_gb: Optional[float] = None,
    num_gpus: int = 1
):
    """
    Estimate the cost of a job before submission
    
    Returns:
    - Estimated cost range based on available nodes
    - Number of matching nodes
    - Estimated wait time
    """
    db = get_db_client()
    
    # Get matching nodes
    gpu_type_enum = GPUType(required_gpu_type) if required_gpu_type else None
    max_price_decimal = None  # No limit for estimation
    
    nodes = await db.get_active_nodes(
        gpu_type=gpu_type_enum,
        max_price=max_price_decimal
    )
    
    # Filter by VRAM if specified
    if min_vram_gb:
        min_vram = Decimal(str(min_vram_gb))
        nodes = [n for n in nodes if n.get("vram_gb", 0) and Decimal(str(n["vram_gb"])) >= min_vram]
    
    # Filter by num_gpus if specified
    if num_gpus > 1:
        nodes = [n for n in nodes if n.get("num_gpus", 1) >= num_gpus]
    
    if not nodes:
        return {
            "estimated": False,
            "message": "No matching nodes currently available",
            "matching_nodes": 0,
            "suggestion": "Try lowering requirements or check back later"
        }
    
    # Calculate cost range
    prices = [Decimal(str(n["price_per_hour"])) for n in nodes]
    min_price = min(prices)
    max_price = max(prices)
    avg_price = sum(prices) / len(prices)
    
    # Calculate costs for the requested duration
    hours = Decimal(str(timeout_seconds)) / Decimal("3600")
    
    min_cost = min_price * hours
    max_cost = max_price * hours
    avg_cost = avg_price * hours
    
    # Estimate wait time based on queue depth
    stats = await db.get_queue_stats()
    pending_count = sum(s["job_count"] for s in stats if s["status"] == "PENDING")
    
    # Rough estimate: each pending job takes average 5 minutes
    estimated_wait_minutes = (pending_count / max(len(nodes), 1)) * 5
    
    # Get GPU info from nodes
    gpu_types_available = list(set(n.get("gpu_type", "unknown") for n in nodes))
    
    return {
        "estimated": True,
        "cost_estimate": {
            "min_usd": float(min_cost),
            "max_usd": float(max_cost),
            "avg_usd": float(avg_cost),
            "currency": "USDC"
        },
        "hourly_rates": {
            "min_per_hour": float(min_price),
            "max_per_hour": float(max_price),
            "avg_per_hour": float(avg_price)
        },
        "matching_nodes": len(nodes),
        "gpu_types_available": gpu_types_available,
        "queue": {
            "pending_jobs": pending_count,
            "estimated_wait_minutes": round(estimated_wait_minutes, 1)
        },
        "request": {
            "timeout_seconds": timeout_seconds,
            "timeout_hours": float(hours),
            "required_gpu_type": required_gpu_type,
            "min_vram_gb": min_vram_gb,
            "num_gpus": num_gpus
        }
    }


@app.post("/api/v1/jobs/submit", status_code=status.HTTP_201_CREATED, tags=["Jobs"])
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
        num_gpus=num_gpus,
        gpu_memory_limit_per_gpu=gpu_memory_limit_per_gpu,
        resume_from_checkpoint=resume_from_checkpoint
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

    try:
        job = await db.claim_job(
            node_id=node_id,
            seller_address=seller_address,
            gpu_type=gpu_type_enum,
            price_per_hour=Decimal(str(price_per_hour)),
            vram_gb=Decimal(str(vram_gb)),
            num_gpus=num_gpus
        )

        if not job:
            # Log debug info to help diagnose why no jobs matched
            logger.debug(
                "no_jobs_matched",
                node_id=node_id,
                seller=seller_address,
                gpu_type=gpu_type,
                price_per_hour=price_per_hour,
                vram_gb=vram_gb,
                num_gpus=num_gpus
            )
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
            "num_gpus": job.get("num_gpus", 1),
            "gpu_memory_limit_per_gpu": job.get("gpu_memory_limit_per_gpu")
        }
    except Exception as e:
        logger.error(
            "claim_job_error",
            error=str(e),
            node_id=node_id,
            seller=seller_address
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim job: {str(e)}"
        )


@app.post("/api/v1/maintenance/release-stale-claims", tags=["Maintenance"])
async def release_stale_claims_endpoint(request: Request, stale_minutes: int = 1):
    """
    Manually release stale CLAIMED jobs back to PENDING
    Useful for debugging when jobs get stuck in CLAIMED state
    """
    db = get_db_client()
    try:
        released = await db.release_stale_claims(stale_minutes=stale_minutes)
        logger.info("manual_stale_claims_release", count=released, stale_minutes=stale_minutes)
        return {
            "released": released,
            "message": f"Released {released} stale claims (claimed but not started in {stale_minutes} minute(s))"
        }
    except Exception as e:
        logger.error("release_stale_claims_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to release stale claims: {str(e)}"
        )


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
# Seller Earnings & Analytics
# ============================================================================

@app.get("/api/v1/sellers/{seller_address}/earnings")
@limiter.limit("60/minute")
async def get_seller_earnings(
    request: Request,
    seller_address: str,
    days: int = 30
):
    """
    Get seller earnings summary
    
    Returns:
    - Total earnings
    - Earnings by time period (daily, weekly)
    - Job statistics
    """
    db = get_db_client()
    
    # Get completed jobs for this seller
    jobs = await db.get_jobs_by_seller(
        seller_address=seller_address,
        status=JobStatus.COMPLETED,
        limit=1000
    )
    
    # Calculate earnings
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    cutoff_date = now - timedelta(days=days)
    
    total_earnings = Decimal("0")
    earnings_today = Decimal("0")
    earnings_week = Decimal("0")
    earnings_month = Decimal("0")
    
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)
    
    jobs_completed = 0
    total_compute_hours = Decimal("0")
    
    for job in jobs:
        cost = Decimal(str(job.get("total_cost", 0) or 0))
        total_earnings += cost
        
        # Parse completion time
        completed_at_str = job.get("completed_at")
        if completed_at_str:
            try:
                if isinstance(completed_at_str, str):
                    completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00')).replace(tzinfo=None)
                else:
                    completed_at = completed_at_str
                
                if completed_at >= today_start:
                    earnings_today += cost
                if completed_at >= week_start:
                    earnings_week += cost
                if completed_at >= month_start:
                    earnings_month += cost
            except:
                pass
        
        # Compute time
        duration = job.get("execution_duration", 0) or 0
        total_compute_hours += Decimal(str(duration)) / Decimal("3600")
        jobs_completed += 1
    
    # Get active node info
    nodes = await db.get_active_nodes()
    seller_nodes = [n for n in nodes if n.get("seller_address") == seller_address]
    
    return {
        "seller_address": seller_address,
        "earnings": {
            "total_usd": float(total_earnings),
            "today_usd": float(earnings_today),
            "week_usd": float(earnings_week),
            "month_usd": float(earnings_month),
            "currency": "USDC"
        },
        "jobs": {
            "total_completed": jobs_completed,
            "total_compute_hours": float(total_compute_hours),
            "avg_earnings_per_job": float(total_earnings / max(jobs_completed, 1))
        },
        "nodes": {
            "active_count": len(seller_nodes),
            "nodes": [
                {
                    "node_id": n.get("node_id"),
                    "gpu_type": n.get("gpu_type"),
                    "device_name": n.get("device_name"),
                    "price_per_hour": float(n.get("price_per_hour", 0)),
                    "is_available": n.get("is_available", False)
                }
                for n in seller_nodes
            ]
        },
        "period_days": days,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/sellers/{seller_address}/jobs")
@limiter.limit("100/minute")
async def get_seller_job_history(
    request: Request,
    seller_address: str,
    status_filter: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Get detailed job history for a seller
    """
    db = get_db_client()
    
    status_enum = JobStatus(status_filter) if status_filter else None
    
    jobs = await db.get_jobs_by_seller(
        seller_address=seller_address,
        status=status_enum,
        limit=limit
    )
    
    # Enrich with summary stats
    total_earnings = sum(Decimal(str(j.get("total_cost", 0) or 0)) for j in jobs)
    total_compute_time = sum(j.get("execution_duration", 0) or 0 for j in jobs)
    
    return {
        "seller_address": seller_address,
        "jobs": jobs,
        "count": len(jobs),
        "summary": {
            "total_earnings_usd": float(total_earnings),
            "total_compute_seconds": total_compute_time
        },
        "pagination": {
            "limit": limit,
            "offset": offset
        }
    }


# ============================================================================
# Statistics and Monitoring
# ============================================================================

@app.get("/api/v1/stats", tags=["Marketplace"])
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


# ============================================================================
# Metrics & Experiment Tracking Endpoints
# ============================================================================

@app.get("/api/v1/jobs/{job_id}/metrics", tags=["Metrics"])
@limiter.limit("100/minute")
async def get_job_metrics(request: Request, job_id: str, metric_name: Optional[str] = None):
    """Get metrics for a job"""
    db = get_db_client()
    
    # Verify job exists
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    # Get metrics from database
    metrics = await db.get_job_metrics(job_id, metric_name)
    
    # Organize metrics by name for time series
    metrics_by_name = {}
    for metric in metrics:
        name = metric["metric_name"]
        if name not in metrics_by_name:
            metrics_by_name[name] = []
        metrics_by_name[name].append({
            "value": float(metric["value"]),
            "step": metric.get("step"),
            "epoch": metric.get("epoch"),
            "timestamp": metric.get("timestamp")
        })
    
    # Calculate summary
    summary = {
        "total_metrics": len(metrics),
        "metric_names": list(set(m["metric_name"] for m in metrics)),
        "latest_values": {}
    }
    
    for name, values in metrics_by_name.items():
        if values:
            latest = max(values, key=lambda x: x.get("step", 0) or x.get("timestamp", ""))
            summary["latest_values"][name] = latest
    
    return {
        "job_id": job_id,
        "summary": summary,
        "time_series": metrics_by_name,
        "metrics": metrics
    }


@app.get("/api/v1/jobs/{job_id}/checkpoints", tags=["Checkpoints"])
@limiter.limit("100/minute")
async def list_job_checkpoints(request: Request, job_id: str):
    """List checkpoints for a job"""
    db = get_db_client()
    
    # Verify job exists
    job = await db.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )
    
    checkpoints = await db.list_checkpoints(job_id)
    
    return {
        "job_id": job_id,
        "checkpoints": checkpoints,
        "count": len(checkpoints)
    }


@app.get("/api/v1/experiments", tags=["Experiments"])
@limiter.limit("100/minute")
async def list_experiments(
    request: Request,
    buyer_address: Optional[str] = None,
    status: Optional[str] = "active",
    limit: int = 50
):
    """List experiments"""
    db = get_db_client()
    
    experiments = await db.list_experiments(
        buyer_address=buyer_address,
        status=status,
        limit=limit
    )
    
    return {
        "experiments": experiments,
        "count": len(experiments)
    }


@app.post("/api/v1/experiments", status_code=status.HTTP_201_CREATED, tags=["Experiments"])
@limiter.limit("10/minute")
async def create_experiment(
    request: Request,
    buyer_address: str,
    name: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    hyperparameters: Optional[Dict[str, Any]] = None
):
    """Create a new experiment"""
    db = get_db_client()
    
    try:
        experiment_id = await db.create_experiment(
            buyer_address=buyer_address,
            name=name,
            description=description,
            tags=tags,
            hyperparameters=hyperparameters
        )
        
        logger.info("experiment_created", experiment_id=experiment_id, name=name, buyer=buyer_address)
        
        return {
            "experiment_id": experiment_id,
            "name": name,
            "buyer_address": buyer_address,
            "status": "active"
        }
    except Exception as e:
        logger.error("experiment_creation_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create experiment: {str(e)}"
        )


@app.get("/api/v1/experiments/{experiment_id}/compare", tags=["Experiments"])
@limiter.limit("100/minute")
async def compare_experiments(request: Request, experiment_id: str):
    """Compare experiments - get all jobs and metrics for an experiment"""
    db = get_db_client()
    
    # Get experiment
    experiment = await db.get_experiment(experiment_id)
    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Experiment {experiment_id} not found"
        )
    
    # Get all jobs for this experiment
    jobs = await db.get_jobs_by_buyer(experiment["buyer_address"], limit=1000)
    experiment_jobs = [j for j in jobs if j.get("experiment_id") == experiment_id]
    
    # Get metrics for all jobs
    comparison_data = []
    for job in experiment_jobs:
        job_metrics = await db.get_job_metrics(job["job_id"])
        comparison_data.append({
            "job_id": job["job_id"],
            "status": job.get("status"),
            "metrics": job_metrics,
            "total_cost": float(job.get("total_cost_usd", 0)),
            "execution_time": job.get("execution_duration_seconds")
        })
    
    return {
        "experiment_id": experiment_id,
        "experiment_name": experiment["name"],
        "jobs": comparison_data,
        "job_count": len(comparison_data)
    }


@app.get("/api/v1/models", tags=["Models"])
@limiter.limit("100/minute")
async def list_models(
    request: Request,
    buyer_address: Optional[str] = None,
    experiment_id: Optional[str] = None,
    limit: int = 50
):
    """List trained models"""
    db = get_db_client()
    
    models = await db.list_models(
        buyer_address=buyer_address,
        experiment_id=experiment_id,
        limit=limit
    )
    
    return {
        "models": models,
        "count": len(models)
    }


@app.get("/api/v1/models/{model_id}/download", tags=["Models"])
@limiter.limit("10/minute")
async def download_model(request: Request, model_id: str):
    """Get download URL for a model"""
    from src.storage import get_storage_client
    
    db = get_db_client()
    storage = get_storage_client()
    
    # Get model metadata
    model = await db.get_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    
    # Generate signed download URL
    storage_path = model["storage_path"]
    download_url = storage.get_signed_download_url(storage_path, expires_in_seconds=3600)
    
    return {
        "model_id": model_id,
        "model_name": model["name"],
        "version": model["version"],
        "download_url": download_url,
        "expires_in": 3600,
        "file_size_bytes": model["file_size_bytes"]
    }


@app.get("/api/v1/datasets", tags=["Datasets"])
@limiter.limit("100/minute")
async def list_datasets(
    request: Request,
    buyer_address: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_public: Optional[bool] = None,
    limit: int = 50
):
    """List datasets"""
    from src.storage.dataset_manager import get_dataset_manager
    
    dataset_manager = get_dataset_manager()
    datasets = await dataset_manager.list_datasets(
        buyer_address=buyer_address,
        tags=tags,
        is_public=is_public,
        limit=limit
    )
    
    return {
        "datasets": datasets,
        "count": len(datasets)
    }


@app.post("/api/v1/datasets", status_code=status.HTTP_201_CREATED, tags=["Datasets"])
@limiter.limit("10/minute")
async def create_dataset(
    request: Request,
    buyer_address: str,
    name: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_public: bool = False
):
    """Create a new dataset"""
    from src.storage.dataset_manager import get_dataset_manager
    
    dataset_manager = get_dataset_manager()
    dataset = await dataset_manager.create_dataset(
        buyer_address=buyer_address,
        name=name,
        description=description,
        tags=tags,
        is_public=is_public
    )
    
    return dataset


@app.post("/api/v1/files/upload/chunked", tags=["Files"])
@limiter.limit("5/minute")
async def start_chunked_upload(
    request: Request,
    file_name: str,
    file_size: int,
    content_type: Optional[str] = None
):
    """Start a chunked file upload"""
    from src.storage import get_storage_client
    
    storage = get_storage_client()
    job_id = str(uuid.uuid4())  # Would come from request context
    
    storage_path = storage.generate_storage_path(
        job_id=job_id,
        file_name=file_name,
        file_type="input"
    )
    
    # Generate upload URL
    upload_url = storage.get_signed_upload_url(storage_path)
    
    return {
        "upload_id": str(uuid.uuid4()),
        "storage_path": storage_path,
        "upload_url": upload_url,
        "chunk_size": 10 * 1024 * 1024,  # 10MB
        "expires_in": 3600
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
