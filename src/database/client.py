"""
Supabase database client for ComputeSwarm
Provides type-safe database operations for queue-based job management
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import os

from supabase import create_client, Client
from pydantic import BaseModel

from src.models import ComputeNode, ComputeJob, JobStatus, GPUType, SellerProfile, VerificationStatus


class DatabaseClient:
    """
    Thread-safe Supabase client for ComputeSwarm operations
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize Supabase client"""
        self.client: Client = create_client(supabase_url, supabase_key)

    # ===== NODE OPERATIONS =====

    async def register_node(self, node: ComputeNode) -> ComputeNode:
        """
        Register or update a compute node
        Uses upsert to handle both new and existing nodes
        """
        # Convert GPU type to uppercase to match database enum (CUDA, MPS, CPU)
        gpu_type_upper = node.gpu_info.gpu_type.value.upper()
        
        node_data = {
            "node_id": node.node_id,
            "seller_address": node.seller_address,
            "gpu_type": gpu_type_upper,
            "device_name": node.gpu_info.device_name,
            "vram_gb": float(node.gpu_info.vram_gb) if node.gpu_info.vram_gb else None,
            "num_gpus": node.gpu_info.num_gpus if hasattr(node.gpu_info, 'num_gpus') else 1,
            "compute_capability": node.gpu_info.compute_capability,
            "price_per_hour": float(node.price_per_hour),
            "is_available": node.is_available,
            "last_heartbeat": datetime.utcnow().isoformat(),
        }

        if node.seller_profile_id:
            node_data["seller_profile_id"] = node.seller_profile_id

        result = self.client.table("compute_nodes").upsert(node_data).execute()
        return node

    async def update_node_heartbeat(self, node_id: str) -> None:
        """Update node's last heartbeat timestamp"""
        self.client.table("compute_nodes").update({
            "last_heartbeat": datetime.utcnow().isoformat(),
            "is_available": True
        }).eq("node_id", node_id).execute()

    async def set_node_availability(self, node_id: str, available: bool) -> None:
        """Set node availability status"""
        self.client.table("compute_nodes").update({
            "is_available": available,
            "last_heartbeat": datetime.utcnow().isoformat()
        }).eq("node_id", node_id).execute()

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by ID"""
        result = self.client.table("compute_nodes").select("*").eq("node_id", node_id).execute()
        return result.data[0] if result.data else None

    async def get_active_nodes(
        self,
        gpu_type: Optional[GPUType] = None,
        max_price: Optional[Decimal] = None,
        min_vram: Optional[Decimal] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all active nodes (heartbeat within last 5 minutes)
        with optional filters
        """
        cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()

        query = self.client.table("compute_nodes").select("*").gte("last_heartbeat", cutoff).eq("is_available", True)

        if gpu_type:
            query = query.eq("gpu_type", gpu_type.value)
        if max_price:
            query = query.lte("price_per_hour", float(max_price))
        if min_vram:
            query = query.gte("vram_gb", float(min_vram))

        result = query.order("price_per_hour").execute()
        return result.data

    # ===== JOB OPERATIONS =====

    async def submit_job(self, job: ComputeJob) -> str:
        """
        Submit a new job to the queue
        Returns job_id
        """
        job_data = {
            "buyer_address": job.buyer_address,
            "script": job.script,
            "requirements": job.requirements,
            "max_price_per_hour": float(job.max_price_per_hour),
            "timeout_seconds": job.timeout_seconds,
            "required_gpu_type": job.required_gpu_type.value.upper() if job.required_gpu_type else None,
            "min_vram_gb": float(job.min_vram_gb) if job.min_vram_gb else None,
            "num_gpus": job.num_gpus,
            "gpu_memory_limit_per_gpu": job.gpu_memory_limit_per_gpu,
            "distributed_backend": job.distributed_backend.value if job.distributed_backend else None,
            "status": "PENDING"
        }
        
        # Add experiment_id if job has it (would need to add to ComputeJob model)
        if hasattr(job, 'experiment_id') and job.experiment_id:
            job_data["experiment_id"] = job.experiment_id

        result = self.client.table("jobs").insert(job_data).execute()
        return result.data[0]["job_id"]

    async def claim_job(
        self,
        node_id: str,
        seller_address: str,
        gpu_type: GPUType,
        price_per_hour: Decimal,
        vram_gb: Decimal,
        num_gpus: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Atomically claim the next available job that matches seller's capabilities
        Uses Supabase RPC to call the claim_job PostgreSQL function
        """
        try:
            result = self.client.rpc(
                "claim_job",
                {
                    "p_node_id": node_id,
                    "p_seller_address": seller_address,
                    "p_gpu_type": gpu_type.value.upper(),  # Convert to uppercase for database enum
                    "p_price_per_hour": float(price_per_hour),
                    "p_vram_gb": float(vram_gb),
                    "p_num_gpus": num_gpus
                }
            ).execute()
        except Exception as e:
            import structlog
            logger = structlog.get_logger()
            logger.error(
                "claim_job_rpc_failed",
                error=str(e),
                node_id=node_id,
                gpu_type=gpu_type.value,
                price_per_hour=float(price_per_hour)
            )
            raise

        # Log what we got back from the SQL function
        import structlog
        logger = structlog.get_logger()
        if result.data:
            logger.debug(
                "claim_job_rpc_success",
                node_id=node_id,
                result_count=len(result.data),
                job_id=result.data[0].get("job_id") if result.data else None
            )
        else:
            logger.debug(
                "claim_job_rpc_no_data",
                node_id=node_id,
                gpu_type=gpu_type.value,
                price_per_hour=float(price_per_hour),
                vram_gb=float(vram_gb),
                num_gpus=num_gpus
            )

        if result.data:
            job_data = result.data[0]
            # The SQL function already returns all necessary fields
            # Convert job_id to string (it comes as TEXT from SQL function but DB stores as UUID)
            job_id = str(job_data["job_id"])
            
            # Try to get full job details, but if it fails, use the data from the SQL function
            # This handles the case where job_id format doesn't match exactly
            full_job = await self.get_job(job_id)
            if full_job:
                return full_job
            
            # If get_job fails, use the data from SQL function directly
            # The SQL function returns: job_id, script, requirements, timeout_seconds, 
            # max_price_per_hour, buyer_address, job_type, docker_image
            import structlog
            logger = structlog.get_logger()
            logger.warning(
                "claim_job_get_job_failed_using_rpc_data",
                job_id=job_id,
                rpc_result=job_data
            )
            
            # Build job dict from SQL function result
            # job_id from SQL function is TEXT, but we need to ensure it's a valid UUID string
            return {
                "job_id": job_id,
                "script": job_data.get("script", ""),
                "requirements": job_data.get("requirements"),
                "timeout_seconds": job_data.get("timeout_seconds", 3600),
                "max_price_per_hour": Decimal(str(job_data.get("max_price_per_hour", 0))),
                "buyer_address": job_data.get("buyer_address", ""),
                "job_type": job_data.get("job_type", "batch_job"),
                "docker_image": job_data.get("docker_image"),
                "num_gpus": job_data.get("num_gpus", 1),
                "gpu_memory_limit_per_gpu": job_data.get("gpu_memory_limit_per_gpu")
            }
        return None

    async def start_job_execution(self, job_id: str) -> None:
        """Mark job as executing"""
        self.client.table("jobs").update({
            "status": "EXECUTING",
            "started_at": datetime.utcnow().isoformat()
        }).eq("job_id", job_id).execute()

    async def complete_job(
        self,
        job_id: str,
        output: str,
        exit_code: int,
        execution_duration: Decimal,
        total_cost: Decimal,
        payment_tx_hash: Optional[str] = None
    ) -> None:
        """Mark job as completed with results"""
        self.client.table("jobs").update({
            "status": "COMPLETED",
            "result_output": output,
            "exit_code": exit_code,
            "execution_duration_seconds": float(execution_duration),
            "total_cost_usd": float(total_cost),
            "payment_tx_hash": payment_tx_hash,
            "completed_at": datetime.utcnow().isoformat()
        }).eq("job_id", job_id).execute()

    async def fail_job(
        self,
        job_id: str,
        error: str,
        exit_code: Optional[int] = None,
        execution_duration: Optional[Decimal] = None
    ) -> None:
        """Mark job as failed with error details"""
        update_data = {
            "status": "FAILED",
            "result_error": error,
            "completed_at": datetime.utcnow().isoformat()
        }

        if exit_code is not None:
            update_data["exit_code"] = exit_code
        if execution_duration is not None:
            update_data["execution_duration_seconds"] = float(execution_duration)

        self.client.table("jobs").update(update_data).eq("job_id", job_id).execute()

    async def cancel_job(self, job_id: str, buyer_address: str) -> bool:
        """
        Cancel a pending job (buyer only)
        Returns True if cancelled, False if job not found or not cancellable
        """
        # Only allow cancelling PENDING or CLAIMED jobs
        result = self.client.table("jobs").update({
            "status": "CANCELLED",
            "completed_at": datetime.utcnow().isoformat()
        }).eq("job_id", job_id).eq("buyer_address", buyer_address).in_("status", ["PENDING", "CLAIMED"]).execute()

        return len(result.data) > 0

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        result = self.client.table("jobs").select("*").eq("job_id", job_id).execute()
        return result.data[0] if result.data else None

    async def get_jobs_by_buyer(
        self,
        buyer_address: str,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get jobs submitted by a buyer"""
        query = self.client.table("jobs").select("*").eq("buyer_address", buyer_address)

        if status:
            query = query.eq("status", status.value)

        result = query.order("created_at", desc=True).limit(limit).execute()
        return result.data

    async def get_jobs_by_seller(
        self,
        seller_address: str,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get jobs assigned to a seller"""
        query = self.client.table("jobs").select("*").eq("seller_address", seller_address)

        if status:
            query = query.eq("status", status.value)

        result = query.order("claimed_at", desc=True).limit(limit).execute()
        return result.data

    async def get_pending_jobs(
        self,
        gpu_type: Optional[GPUType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pending jobs in queue"""
        query = self.client.table("jobs").select("*").eq("status", "PENDING")

        if gpu_type:
            query = query.or_(f"required_gpu_type.is.null,required_gpu_type.eq.{gpu_type.value}")

        result = query.order("created_at").limit(limit).execute()
        return result.data

    # ===== MAINTENANCE OPERATIONS =====

    async def release_stale_claims(self, stale_minutes: int = 5) -> int:
        """
        Release jobs that were claimed but never started
        Returns number of jobs released
        """
        result = self.client.rpc("release_stale_claims", {"stale_minutes": stale_minutes}).execute()
        return result.data

    async def mark_stale_executions_failed(self, timeout_multiplier: float = 2.0) -> int:
        """
        Mark executing jobs as failed if they've exceeded timeout
        Returns number of jobs marked as failed
        """
        result = self.client.rpc("mark_stale_executions_failed", {"timeout_multiplier": timeout_multiplier}).execute()
        return result.data

    # ===== STATISTICS =====

    async def get_queue_stats(self) -> List[Dict[str, Any]]:
        """Get queue statistics by status"""
        result = self.client.table("queue_stats").select("*").execute()
        return result.data

    async def get_active_sellers_view(self) -> List[Dict[str, Any]]:
        """Get active sellers view"""
        result = self.client.table("active_sellers").select("*").execute()
        return result.data

    async def get_job_state_transitions(self, job_id: str) -> List[Dict[str, Any]]:
        """Get state transition history for a job (audit trail)"""
        result = self.client.table("job_state_transitions").select("*").eq("job_id", job_id).order("transitioned_at").execute()
        return result.data

    # ===== SELLER PROFILE OPERATIONS =====

    async def get_seller_profile(self, seller_address: str) -> Optional[Dict[str, Any]]:
        """Get seller profile by address"""
        result = self.client.table("seller_profiles").select("*").eq(
            "seller_address", seller_address.lower()
        ).execute()
        return result.data[0] if result.data else None

    async def upsert_seller_profile_from_github(
        self,
        seller_address: str,
        github_id: int,
        github_username: str,
        github_avatar_url: Optional[str] = None,
        github_profile_url: Optional[str] = None
    ) -> str:
        """Create or update seller profile with GitHub verification"""
        profile_data = {
            "seller_address": seller_address.lower(),
            "github_id": github_id,
            "github_username": github_username,
            "github_avatar_url": github_avatar_url,
            "github_profile_url": github_profile_url,
            "verification_status": "verified",
            "verified_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = self.client.table("seller_profiles").upsert(
            profile_data, 
            on_conflict="seller_address"
        ).execute()
        
        return result.data[0]["id"] if result.data else None

    async def update_seller_profile(
        self,
        seller_address: str,
        updates: Dict[str, Any]
    ) -> None:
        """Update seller profile fields"""
        updates["updated_at"] = datetime.utcnow().isoformat()
        self.client.table("seller_profiles").update(updates).eq(
            "seller_address", seller_address.lower()
        ).execute()

    async def add_seller_rating(
        self,
        job_id: str,
        buyer_address: str,
        seller_address: str,
        rating: int,
        comment: Optional[str] = None
    ) -> str:
        """Add a rating for a seller and update their reputation score"""
        rating_data = {
            "job_id": job_id,
            "buyer_address": buyer_address.lower(),
            "seller_address": seller_address.lower(),
            "rating": rating,
            "comment": comment
        }
        
        result = self.client.table("seller_ratings").insert(rating_data).execute()
        
        # Update seller's reputation score (trigger should handle this, but we can do it here too)
        return result.data[0]["id"] if result.data else None

    # ===== EXPERIMENT TRACKING OPERATIONS =====

    async def save_job_metrics(
        self,
        job_id: str,
        metrics: List[Dict[str, Any]],
        experiment_id: Optional[str] = None
    ) -> int:
        """
        Save job metrics to database
        
        Args:
            job_id: Job ID
            metrics: List of metric dicts with metric_name, value, step, epoch, timestamp
            experiment_id: Optional experiment ID to link metrics
            
        Returns:
            Number of metrics saved
        """
        import structlog
        logger = structlog.get_logger()
        
        if not metrics:
            return 0
        
        metrics_data = []
        for metric in metrics:
            metric_data = {
                "job_id": job_id,
                "metric_name": metric.get("metric_name"),
                "value": float(metric.get("value", 0)),
                "step": metric.get("step"),
                "epoch": metric.get("epoch"),
            }
            
            if experiment_id:
                metric_data["experiment_id"] = experiment_id
            
            if metric.get("timestamp"):
                metric_data["timestamp"] = metric["timestamp"]
            
            metrics_data.append(metric_data)
        
        try:
            result = self.client.table("job_metrics").insert(metrics_data).execute()
            saved_count = len(result.data) if result.data else len(metrics_data)
            logger.info("job_metrics_saved", job_id=job_id, count=saved_count, experiment_id=experiment_id)
            return saved_count
        except Exception as e:
            logger.error("job_metrics_save_failed", job_id=job_id, error=str(e))
            raise

    async def get_job_metrics(
        self,
        job_id: str,
        metric_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get metrics for a job
        
        Args:
            job_id: Job ID
            metric_name: Optional metric name to filter
            
        Returns:
            List of metric dicts
        """
        query = self.client.table("job_metrics").select("*").eq("job_id", job_id)
        
        if metric_name:
            query = query.eq("metric_name", metric_name)
        
        query = query.order("timestamp", desc=False)
        
        result = query.execute()
        return result.data if result.data else []

    async def create_experiment(
        self,
        buyer_address: str,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new experiment
        
        Args:
            buyer_address: Buyer address
            name: Experiment name
            description: Optional description
            tags: Optional tags
            hyperparameters: Optional hyperparameters dict
            
        Returns:
            Experiment ID
        """
        import structlog
        logger = structlog.get_logger()
        
        experiment_data = {
            "buyer_address": buyer_address,
            "name": name,
            "description": description,
            "tags": tags or [],
            "hyperparameters": hyperparameters,
            "status": "active"
        }
        
        result = self.client.table("experiments").insert(experiment_data).execute()
        
        if result.data:
            experiment_id = result.data[0]["id"]
            logger.info("experiment_created", experiment_id=experiment_id, name=name, buyer=buyer_address)
            return experiment_id
        else:
            raise Exception("Failed to create experiment")

    async def get_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get experiment by ID"""
        result = self.client.table("experiments").select("*").eq("id", experiment_id).execute()
        return result.data[0] if result.data else None

    async def list_experiments(
        self,
        buyer_address: Optional[str] = None,
        status: Optional[str] = "active",
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List experiments
        
        Args:
            buyer_address: Filter by buyer
            status: Filter by status (default: active)
            limit: Maximum results
            
        Returns:
            List of experiment dicts
        """
        query = self.client.table("experiments").select("*")
        
        if buyer_address:
            query = query.eq("buyer_address", buyer_address)
        
        if status:
            query = query.eq("status", status)
        
        query = query.order("created_at", desc=True).limit(limit)
        
        result = query.execute()
        return result.data if result.data else []

    async def save_checkpoint(
        self,
        job_id: str,
        storage_path: str,
        file_size_bytes: int,
        checkpoint_name: Optional[str] = None,
        epoch: Optional[int] = None,
        step: Optional[int] = None,
        loss: Optional[float] = None,
        metric_values: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        experiment_id: Optional[str] = None,
        checksum: Optional[str] = None
    ) -> str:
        """
        Save checkpoint metadata
        
        Args:
            job_id: Job ID
            storage_path: Path in storage
            file_size_bytes: File size
            checkpoint_name: Optional checkpoint name
            epoch: Optional epoch number
            step: Optional step number
            loss: Optional loss value
            metric_values: Optional dict of metrics at this checkpoint
            description: Optional description
            experiment_id: Optional experiment ID
            checksum: Optional file checksum
            
        Returns:
            Checkpoint ID
        """
        import structlog
        logger = structlog.get_logger()
        
        checkpoint_data = {
            "job_id": job_id,
            "storage_path": storage_path,
            "file_size_bytes": file_size_bytes,
            "checkpoint_name": checkpoint_name,
            "epoch": epoch,
            "step": step,
            "loss": float(loss) if loss is not None else None,
            "metric_values": metric_values,
            "description": description,
            "checksum": checksum
        }
        
        if experiment_id:
            checkpoint_data["experiment_id"] = experiment_id
        
        result = self.client.table("checkpoints").insert(checkpoint_data).execute()
        
        if result.data:
            checkpoint_id = result.data[0]["id"]
            logger.info("checkpoint_saved", checkpoint_id=checkpoint_id, job_id=job_id, epoch=epoch, step=step)
            return checkpoint_id
        else:
            raise Exception("Failed to save checkpoint")

    async def list_checkpoints(
        self,
        job_id: str,
        experiment_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List checkpoints for a job or experiment
        
        Args:
            job_id: Job ID (optional if experiment_id provided)
            experiment_id: Optional experiment ID
            
        Returns:
            List of checkpoint dicts
        """
        query = self.client.table("checkpoints").select("*")
        
        if job_id:
            query = query.eq("job_id", job_id)
        
        if experiment_id:
            query = query.eq("experiment_id", experiment_id)
        
        query = query.order("created_at", desc=True)
        
        result = query.execute()
        return result.data if result.data else []

    async def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Get checkpoint by ID"""
        result = self.client.table("checkpoints").select("*").eq("id", checkpoint_id).execute()
        return result.data[0] if result.data else None

    async def save_model(
        self,
        job_id: str,
        buyer_address: str,
        name: str,
        version: str,
        storage_path: str,
        file_size_bytes: int,
        checksum: Optional[str] = None,
        format: Optional[str] = None,
        architecture: Optional[str] = None,
        framework: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        experiment_id: Optional[str] = None
    ) -> str:
        """
        Save model metadata
        
        Args:
            job_id: Training job ID
            buyer_address: Buyer address
            name: Model name
            version: Model version (semantic versioning)
            storage_path: Path in storage
            file_size_bytes: File size
            checksum: Optional checksum
            format: Model format (pt, pth, safetensors, onnx, h5)
            architecture: Model architecture
            framework: Framework (pytorch, tensorflow, etc.)
            metrics: Optional metrics dict
            description: Optional description
            experiment_id: Optional experiment ID
            
        Returns:
            Model ID
        """
        import structlog
        logger = structlog.get_logger()
        
        model_data = {
            "job_id": job_id,
            "buyer_address": buyer_address,
            "name": name,
            "version": version,
            "storage_path": storage_path,
            "file_size_bytes": file_size_bytes,
            "checksum": checksum,
            "format": format,
            "architecture": architecture,
            "framework": framework,
            "metrics": metrics,
            "description": description,
            "status": "active"
        }
        
        if experiment_id:
            model_data["experiment_id"] = experiment_id
        
        result = self.client.table("models").insert(model_data).execute()
        
        if result.data:
            model_id = result.data[0]["id"]
            logger.info("model_saved", model_id=model_id, name=name, version=version, buyer=buyer_address)
            return model_id
        else:
            raise Exception("Failed to save model")

    async def list_models(
        self,
        buyer_address: Optional[str] = None,
        experiment_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List models
        
        Args:
            buyer_address: Filter by buyer
            experiment_id: Filter by experiment
            limit: Maximum results
            
        Returns:
            List of model dicts
        """
        query = self.client.table("models").select("*").eq("status", "active")
        
        if buyer_address:
            query = query.eq("buyer_address", buyer_address)
        
        if experiment_id:
            query = query.eq("experiment_id", experiment_id)
        
        query = query.order("created_at", desc=True).limit(limit)
        
        result = query.execute()
        return result.data if result.data else []

    async def get_model(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Get model by ID"""
        result = self.client.table("models").select("*").eq("id", model_id).execute()
        return result.data[0] if result.data else None


# Singleton instance
_db_client: Optional[DatabaseClient] = None


def get_db_client() -> DatabaseClient:
    """
    Get or create singleton database client
    Reads configuration from environment variables
    """
    global _db_client

    if _db_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment. "
                "See FREE_TIER_SETUP.md for configuration instructions."
            )

        _db_client = DatabaseClient(supabase_url, supabase_key)

    return _db_client
