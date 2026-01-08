
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, HTTPException, status
import structlog

from src.marketplace.models import GPUType, JobSubmissionRequest, JobTemplateSubmissionRequest
from src.models import ComputeJob, JobStatus
from src.database import get_db_client
from src.templates import get_template, list_templates
from src.marketplace.dependencies import limiter, logger, get_buyer_key, get_node_key

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])

@router.post("/estimate")
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


@router.post("/submit", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_buyer_key)
async def submit_job(
    request: Request,
    job_request: JobSubmissionRequest
):
    """
    Submit a job to the queue
    """
    db = get_db_client()

    job = ComputeJob(
        buyer_address=job_request.buyer_address,
        script=job_request.script,
        requirements=job_request.requirements,
        max_price_per_hour=Decimal(str(job_request.max_price_per_hour)),
        timeout_seconds=job_request.timeout_seconds,
        required_gpu_type=GPUType(job_request.required_gpu_type) if job_request.required_gpu_type else None,
        min_vram_gb=Decimal(str(job_request.min_vram_gb)) if job_request.min_vram_gb else None,
        num_gpus=job_request.num_gpus,
        gpu_memory_limit_per_gpu=job_request.gpu_memory_limit_per_gpu,
        resume_from_checkpoint=job_request.resume_from_checkpoint
    )

    job_id = await db.submit_job(job)

    logger.info(
        "job_submitted_to_queue",
        job_id=job_id,
        buyer=job_request.buyer_address,
        max_price=float(job_request.max_price_per_hour),
        gpu_type=job_request.required_gpu_type
    )

    return {
        "job_id": job_id,
        "status": "PENDING",
        "message": "Job submitted to queue. Sellers will claim when available.",
        "buyer_address": job_request.buyer_address,
        "max_price_per_hour": job_request.max_price_per_hour
    }


@router.post("/submit_template", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute", key_func=get_buyer_key)
async def submit_template_job(
    request: Request,
    template_request: JobTemplateSubmissionRequest
):
    """
    Submit a job via a template (e.g. lora_finetune)
    """
    db = get_db_client()
    
    # Resolve template
    template = get_template(template_request.template_name)
    if not template:
        available = list_templates()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template '{template_request.template_name}' not found. Available: {available}"
        )
    
    # Render script and requirements
    try:
        script = template.render_script(template_request.parameters)
        requirements = template.get_requirements(template_request.parameters)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to render template: {str(e)}"
        )
    
    # Create job
    job = ComputeJob(
        buyer_address=template_request.buyer_address,
        script=script,
        requirements=requirements,
        max_price_per_hour=Decimal(str(template_request.max_price_per_hour)),
        timeout_seconds=template_request.timeout_seconds,
        required_gpu_type=GPUType(template_request.required_gpu_type) if template_request.required_gpu_type else None,
        min_vram_gb=Decimal(str(template_request.min_vram_gb)) if template_request.min_vram_gb else None,
        num_gpus=template_request.num_gpus
    )
    
    job_id = await db.submit_job(job)
    
    logger.info(
        "template_job_submitted",
        job_id=job_id,
        template=template_request.template_name,
        buyer=template_request.buyer_address
    )
    
    return {
        "job_id": job_id,
        "status": "PENDING",
        "template_name": template_request.template_name,
        "message": f"Job submitted via template '{template_request.template_name}'"
    }


@router.post("/claim")
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
            logger.debug(
                "no_jobs_matched",
                node_id=node_id,
                seller=seller_address
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
        logger.error("claim_job_error", error=str(e), node_id=node_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim job: {str(e)}"
        )


@router.post("/{job_id}/start")
async def start_job_execution(job_id: str):
    """
    Mark job as executing (Seller endpoint)
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


@router.post("/{job_id}/complete")
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
    """
    db = get_db_client()

    try:
        # Server-side Cost Validation logic
        job = await db.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
            
        price_per_hour = Decimal(str(job.get("locked_price_per_hour") or job["max_price_per_hour"]))

        duration_decimal = Decimal(str(execution_duration))
        billed_duration = max(duration_decimal, Decimal("1.0"))
        
        expected_cost = (billed_duration * price_per_hour) / Decimal("3600")
        reported_cost = Decimal(str(total_cost))
        
        tolerance = expected_cost * Decimal("0.01") + Decimal("0.01")
        
        final_cost = reported_cost
        if abs(reported_cost - expected_cost) > tolerance:
            logger.warning(
                "cost_validation_mismatch",
                job_id=job_id,
                reported=float(reported_cost),
                expected=float(expected_cost)
            )
            final_cost = expected_cost

        await db.complete_job(
            job_id=job_id,
            output=output,
            exit_code=exit_code,
            execution_duration=duration_decimal,
            total_cost=final_cost,
            payment_tx_hash=payment_tx_hash
        )

        logger.info("job_completed", job_id=job_id, cost=float(final_cost))

        return {
            "status": "COMPLETED",
            "job_id": job_id,
            "exit_code": exit_code,
            "total_cost": float(final_cost),
            "validation": "verified"
        }

    except Exception as e:
        logger.error("job_completion_failed", job_id=job_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete job: {str(e)}"
        )


@router.post("/{job_id}/fail")
async def fail_job(
    job_id: str,
    error: str,
    exit_code: Optional[int] = None,
    execution_duration: Optional[float] = None
):
    """
    Mark job as failed (Seller endpoint)
    """
    db = get_db_client()
    try:
        duration_decimal = Decimal(str(execution_duration)) if execution_duration else None
        
        await db.fail_job(
            job_id=job_id,
            error=error,
            exit_code=exit_code,
            execution_duration=duration_decimal
        )
        logger.info("job_failed", job_id=job_id, error=error)
        return {"status": "FAILED", "job_id": job_id}
    except Exception as e:
        logger.error("job_fail_reporting_failed", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str, buyer_address: str):
    """
    Cancel a pending or claimed job (Buyer endpoint)
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


@router.get("/{job_id}")
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


@router.get("/buyer/{buyer_address}")
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


@router.get("/seller/{seller_address}")
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


@router.get("/queue/pending")
@limiter.limit("100/minute")
async def get_pending_jobs(request: Request, gpu_type: Optional[str] = None, limit: int = 100):
    """
    Get pending jobs in queue (for monitoring/debugging)
    """
    db = get_db_client()

    gpu_type_enum = GPUType(gpu_type) if gpu_type else None

    jobs = await db.get_pending_jobs(gpu_type=gpu_type_enum, limit=limit)

    return {"jobs": jobs, "count": len(jobs)}

@router.get("/{job_id}/metrics")
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

@router.get("/{job_id}/checkpoints", tags=["Checkpoints"])
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
