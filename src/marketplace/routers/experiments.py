
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, HTTPException, status
import structlog

from src.database import get_db_client
from src.marketplace.dependencies import limiter, logger

router = APIRouter(prefix="/api/v1/experiments", tags=["Experiments"])

@router.get("")
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


@router.post("", status_code=status.HTTP_201_CREATED)
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


@router.get("/{experiment_id}/compare")
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
