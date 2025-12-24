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

from src.models import ComputeNode, ComputeJob, JobStatus, GPUType


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
        node_data = {
            "node_id": node.node_id,
            "seller_address": node.seller_address,
            "gpu_type": node.gpu_info.gpu_type.value,
            "device_name": node.gpu_info.device_name,
            "vram_gb": float(node.gpu_info.vram_gb) if node.gpu_info.vram_gb else None,
            "compute_capability": node.gpu_info.compute_capability,
            "price_per_hour": float(node.price_per_hour),
            "is_available": node.is_available,
            "last_heartbeat": datetime.utcnow().isoformat(),
        }

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
            "required_gpu_type": job.required_gpu_type.value if job.required_gpu_type else None,
            "min_vram_gb": float(job.min_vram_gb) if job.min_vram_gb else None,
            "status": "PENDING"
        }

        result = self.client.table("jobs").insert(job_data).execute()
        return result.data[0]["job_id"]

    async def claim_job(
        self,
        node_id: str,
        seller_address: str,
        gpu_type: GPUType,
        price_per_hour: Decimal,
        vram_gb: Decimal
    ) -> Optional[Dict[str, Any]]:
        """
        Atomically claim the next available job that matches seller's capabilities
        Uses Supabase RPC to call the claim_job PostgreSQL function
        """
        result = self.client.rpc(
            "claim_job",
            {
                "p_node_id": node_id,
                "p_seller_address": seller_address,
                "p_gpu_type": gpu_type.value,
                "p_price_per_hour": float(price_per_hour),
                "p_vram_gb": float(vram_gb)
            }
        ).execute()

        return result.data[0] if result.data else None

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
