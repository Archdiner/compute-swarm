
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, status
import structlog

from src.marketplace.models import X402Manifest
from src.config import get_marketplace_config
from src.database import get_db_client
from src.marketplace.dependencies import logger

router = APIRouter(tags=["General"])

@router.get("/", tags=["Health"])
async def root():
    """Root endpoint with basic info"""
    return {
        "name": "ComputeSwarm Marketplace",
        "version": "0.1.0",
        "status": "operational",
        "x402_manifest": "/x402.json"
    }


@router.get("/x402.json", response_model=X402Manifest, tags=["Payments"])
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


@router.get("/health", tags=["Health"])
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


@router.post("/api/v1/maintenance/release-stale-claims", tags=["Maintenance"])
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
