"""
Pytest configuration and shared fixtures
Includes MockDatabaseClient for testing without Supabase
"""

import pytest
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, MagicMock

from httpx import AsyncClient
from fastapi.testclient import TestClient
from eth_account import Account

from src.marketplace.server import app
from src.marketplace.models import GPUType, GPUInfo
from src.models import ComputeNode, ComputeJob, JobStatus


class MockDatabaseClient:
    """
    In-memory mock of DatabaseClient for testing.
    Mimics the interface of src/database/client.DatabaseClient
    """

    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self._job_counter = 0

    # ===== NODE OPERATIONS =====

    async def register_node(self, node: ComputeNode) -> ComputeNode:
        """Register or update a compute node"""
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
            "created_at": datetime.utcnow().isoformat(),
        }
        self.nodes[node.node_id] = node_data
        return node

    async def update_node_heartbeat(self, node_id: str) -> None:
        """Update node's last heartbeat timestamp"""
        if node_id in self.nodes:
            self.nodes[node_id]["last_heartbeat"] = datetime.utcnow().isoformat()
            self.nodes[node_id]["is_available"] = True

    async def set_node_availability(self, node_id: str, available: bool) -> None:
        """Set node availability status"""
        if node_id in self.nodes:
            self.nodes[node_id]["is_available"] = available
            self.nodes[node_id]["last_heartbeat"] = datetime.utcnow().isoformat()

    async def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by ID"""
        return self.nodes.get(node_id)

    async def get_active_nodes(
        self,
        gpu_type: Optional[GPUType] = None,
        max_price: Optional[Decimal] = None,
        min_vram: Optional[Decimal] = None
    ) -> List[Dict[str, Any]]:
        """Get all active nodes with optional filters"""
        result = []
        for node in self.nodes.values():
            if not node.get("is_available", False):
                continue
            if gpu_type and node.get("gpu_type") != gpu_type.value:
                continue
            if max_price and float(node.get("price_per_hour", 0)) > float(max_price):
                continue
            if min_vram and (node.get("vram_gb") or 0) < float(min_vram):
                continue
            result.append(node)
        return sorted(result, key=lambda x: x.get("price_per_hour", 0))

    # ===== JOB OPERATIONS =====

    async def submit_job(self, job: ComputeJob) -> str:
        """Submit a new job to the queue"""
        job_id = str(uuid.uuid4())
        job_data = {
            "job_id": job_id,
            "buyer_address": job.buyer_address,
            "script": job.script,
            "requirements": job.requirements,
            "max_price_per_hour": float(job.max_price_per_hour),
            "timeout_seconds": job.timeout_seconds,
            "required_gpu_type": job.required_gpu_type.value if job.required_gpu_type else None,
            "min_vram_gb": float(job.min_vram_gb) if job.min_vram_gb else None,
            "status": "PENDING",
            "created_at": datetime.utcnow().isoformat(),
            "node_id": None,
            "seller_address": None,
        }
        self.jobs[job_id] = job_data
        return job_id

    async def claim_job(
        self,
        node_id: str,
        seller_address: str,
        gpu_type: GPUType,
        price_per_hour: Decimal,
        vram_gb: Decimal
    ) -> Optional[Dict[str, Any]]:
        """Atomically claim the next available job"""
        for job_id, job in self.jobs.items():
            if job["status"] != "PENDING":
                continue
            if job.get("max_price_per_hour", 0) < float(price_per_hour):
                continue
            req_gpu = job.get("required_gpu_type")
            if req_gpu and req_gpu != gpu_type.value:
                continue
            min_vram = job.get("min_vram_gb")
            if min_vram and float(min_vram) > float(vram_gb):
                continue

            # Claim the job
            job["status"] = "CLAIMED"
            job["node_id"] = node_id
            job["seller_address"] = seller_address
            job["claimed_at"] = datetime.utcnow().isoformat()

            return {
                "job_id": job_id,
                "script": job["script"],
                "requirements": job.get("requirements"),
                "timeout_seconds": job["timeout_seconds"],
                "max_price_per_hour": job["max_price_per_hour"],
                "buyer_address": job["buyer_address"],
            }

        return None

    async def start_job_execution(self, job_id: str) -> None:
        """Mark job as executing"""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "EXECUTING"
            self.jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

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
        if job_id in self.jobs:
            self.jobs[job_id].update({
                "status": "COMPLETED",
                "result_output": output,
                "exit_code": exit_code,
                "execution_duration_seconds": float(execution_duration),
                "total_cost_usd": float(total_cost),
                "payment_tx_hash": payment_tx_hash,
                "completed_at": datetime.utcnow().isoformat(),
            })

    async def fail_job(
        self,
        job_id: str,
        error: str,
        exit_code: Optional[int] = None,
        execution_duration: Optional[Decimal] = None
    ) -> None:
        """Mark job as failed with error details"""
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "FAILED"
            self.jobs[job_id]["result_error"] = error
            self.jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
            if exit_code is not None:
                self.jobs[job_id]["exit_code"] = exit_code
            if execution_duration is not None:
                self.jobs[job_id]["execution_duration_seconds"] = float(execution_duration)

    async def cancel_job(self, job_id: str, buyer_address: str) -> bool:
        """Cancel a pending job (buyer only)"""
        job = self.jobs.get(job_id)
        if not job:
            return False
        if job["buyer_address"] != buyer_address:
            return False
        if job["status"] not in ["PENDING", "CLAIMED"]:
            return False

        job["status"] = "CANCELLED"
        job["completed_at"] = datetime.utcnow().isoformat()
        return True

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    async def get_jobs_by_buyer(
        self,
        buyer_address: str,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get jobs submitted by a buyer"""
        result = []
        for job in self.jobs.values():
            if job["buyer_address"] != buyer_address:
                continue
            if status and job["status"] != status.value:
                continue
            result.append(job)
        return sorted(result, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]

    async def get_jobs_by_seller(
        self,
        seller_address: str,
        status: Optional[JobStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get jobs assigned to a seller"""
        result = []
        for job in self.jobs.values():
            if job.get("seller_address") != seller_address:
                continue
            if status and job["status"] != status.value:
                continue
            result.append(job)
        return sorted(result, key=lambda x: x.get("claimed_at", ""), reverse=True)[:limit]

    async def get_pending_jobs(
        self,
        gpu_type: Optional[GPUType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pending jobs in queue"""
        result = []
        for job in self.jobs.values():
            if job["status"] != "PENDING":
                continue
            if gpu_type:
                req_gpu = job.get("required_gpu_type")
                if req_gpu and req_gpu != gpu_type.value:
                    continue
            result.append(job)
        return sorted(result, key=lambda x: x.get("created_at", ""))[:limit]

    # ===== MAINTENANCE OPERATIONS =====

    async def release_stale_claims(self, stale_minutes: int = 5) -> int:
        """Release jobs that were claimed but never started"""
        count = 0
        cutoff = datetime.utcnow() - timedelta(minutes=stale_minutes)
        for job in self.jobs.values():
            if job["status"] == "CLAIMED":
                claimed_at = datetime.fromisoformat(job.get("claimed_at", datetime.utcnow().isoformat()))
                if claimed_at < cutoff:
                    job["status"] = "PENDING"
                    job["node_id"] = None
                    job["seller_address"] = None
                    job["claimed_at"] = None
                    count += 1
        return count

    async def mark_stale_executions_failed(self, timeout_multiplier: float = 2.0) -> int:
        """Mark executing jobs as failed if they've exceeded timeout"""
        count = 0
        for job in self.jobs.values():
            if job["status"] == "EXECUTING":
                started_at = datetime.fromisoformat(job.get("started_at", datetime.utcnow().isoformat()))
                max_time = job.get("timeout_seconds", 3600) * timeout_multiplier
                if (datetime.utcnow() - started_at).total_seconds() > max_time:
                    job["status"] = "FAILED"
                    job["result_error"] = "Job execution timed out"
                    job["completed_at"] = datetime.utcnow().isoformat()
                    count += 1
        return count

    # ===== STATISTICS =====

    async def get_queue_stats(self) -> List[Dict[str, Any]]:
        """Get queue statistics by status"""
        stats = {}
        for job in self.jobs.values():
            status = job["status"]
            if status not in stats:
                stats[status] = {"status": status, "job_count": 0}
            stats[status]["job_count"] += 1
        return list(stats.values())

    async def get_active_sellers_view(self) -> List[Dict[str, Any]]:
        """Get active sellers view"""
        return [
            {
                "node_id": n["node_id"],
                "seller_address": n["seller_address"],
                "gpu_type": n["gpu_type"],
                "device_name": n["device_name"],
                "price_per_hour": n["price_per_hour"],
                "is_available": n["is_available"],
            }
            for n in self.nodes.values()
            if n.get("is_available", False)
        ]

    async def get_job_state_transitions(self, job_id: str) -> List[Dict[str, Any]]:
        """Get state transition history for a job"""
        return []  # Simplified for tests


# Global mock client instance
_mock_db_client: Optional[MockDatabaseClient] = None


def get_mock_db_client() -> MockDatabaseClient:
    """Get or create singleton mock database client"""
    global _mock_db_client
    if _mock_db_client is None:
        _mock_db_client = MockDatabaseClient()
    return _mock_db_client


def reset_mock_db_client():
    """Reset the mock database client"""
    global _mock_db_client
    _mock_db_client = MockDatabaseClient()
    return _mock_db_client


# ===== FIXTURES =====

@pytest.fixture
def test_account():
    """Create a test Ethereum account"""
    return Account.create()


@pytest.fixture
def test_seller_account():
    """Create a test seller account"""
    return Account.from_key("0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef")


@pytest.fixture
def test_buyer_account():
    """Create a test buyer account"""
    return Account.from_key("0xabcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890")


@pytest.fixture
def sample_gpu_info() -> GPUInfo:
    """Create sample GPU info for testing"""
    return GPUInfo(
        gpu_type=GPUType.MPS,
        device_name="Apple M4 Max",
        vram_gb=64.0,
        compute_capability=None,
        cuda_version=None,
        driver_version=None
    )


@pytest.fixture
def sample_compute_node(test_seller_account, sample_gpu_info) -> ComputeNode:
    """Create sample compute node for testing"""
    return ComputeNode(
        node_id="test_node_123",
        seller_address=test_seller_account.address,
        gpu_info=sample_gpu_info,
        price_per_hour=Decimal("0.50"),
        is_available=True
    )


@pytest.fixture
def mock_db():
    """Create and reset mock database client for each test"""
    return reset_mock_db_client()


@pytest.fixture(autouse=True)
def patch_database(mock_db):
    """Automatically patch get_db_client for all tests"""
    with patch('src.database.get_db_client', return_value=mock_db):
        with patch('src.database.client.get_db_client', return_value=mock_db):
            yield mock_db


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client (sync)"""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncClient:
    """Create async HTTP client for testing"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_web3_provider():
    """Mock Web3 provider for testing blockchain interactions"""
    from web3 import Web3
    # Simple mock without eth_tester to avoid import issues
    mock_provider = MagicMock()
    w3 = Web3(mock_provider)
    return w3
