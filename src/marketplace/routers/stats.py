
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
import structlog

from src.models import JobStatus
from src.database import get_db_client
from src.marketplace.dependencies import limiter, logger

router = APIRouter(tags=["Marketplace"])

@router.get("/api/v1/sellers/{seller_address}/earnings")
@limiter.limit("60/minute")
async def get_seller_earnings(
    request: Request,
    seller_address: str,
    days: int = 30
):
    """
    Get seller earnings summary
    """
    db = get_db_client()
    
    # Get completed jobs for this seller
    jobs = await db.get_jobs_by_seller(
        seller_address=seller_address,
        status=JobStatus.COMPLETED,
        limit=1000
    )
    
    # Calculate earnings
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


@router.get("/api/v1/sellers/{seller_address}/jobs")
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


@router.get("/api/v1/stats")
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
