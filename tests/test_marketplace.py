"""
Unit and integration tests for marketplace API
Uses MockDatabaseClient from conftest.py
"""

import pytest
from decimal import Decimal
from httpx import AsyncClient
from fastapi.testclient import TestClient

from tests.factories import (
    ComputeNodeFactory,
    ComputeJobFactory,
    CUDANodeFactory,
    MPSNodeFactory,
    JobRequestFactory,
)
from src.marketplace.models import GPUType, GPUInfo
from src.models import ComputeNode, ComputeJob, JobStatus


class TestMarketplaceEndpoints:
    """Test marketplace API endpoints"""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns basic info"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "ComputeSwarm Marketplace"
        assert "x402_manifest" in data

    def test_health_check(self, client: TestClient):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "database" in data

    def test_x402_manifest(self, client: TestClient):
        """Test x402 manifest endpoint returns correct structure"""
        response = client.get("/x402.json")
        assert response.status_code == 200
        manifest = response.json()
        assert manifest["version"] == "1.0"
        assert manifest["name"] == "ComputeSwarm"
        assert "x402-usdc-base" in manifest["payment_methods"]
        assert "endpoints" in manifest


class TestNodeRegistration:
    """Test node registration and management"""

    def test_register_node(self, client: TestClient, test_seller_account, sample_gpu_info):
        """Test successful node registration"""
        registration = {
            "seller_address": test_seller_account.address,
            "gpu_info": sample_gpu_info.model_dump(),
            "price_per_hour": 0.50,
            "endpoint": "http://localhost:8001"
        }

        response = client.post("/api/v1/nodes/register", json=registration)
        assert response.status_code == 201
        data = response.json()
        assert data["seller_address"] == test_seller_account.address
        assert "node_id" in data
        assert data["is_available"] == True

    def test_register_node_cuda(self, client: TestClient, test_seller_account):
        """Test registering a CUDA node"""
        gpu_info = {
            "gpu_type": "cuda",
            "device_name": "NVIDIA RTX 4090",
            "vram_gb": 24.0,
            "compute_capability": "8.9",
            "cuda_version": "12.1"
        }
        registration = {
            "seller_address": test_seller_account.address,
            "gpu_info": gpu_info,
            "price_per_hour": 2.00,
            "endpoint": "http://localhost:8001"
        }

        response = client.post("/api/v1/nodes/register", json=registration)
        assert response.status_code == 201
        data = response.json()
        assert data["gpu_info"]["gpu_type"] == "cuda"

    @pytest.mark.asyncio
    async def test_list_nodes(self, async_client: AsyncClient, test_seller_account, sample_gpu_info, mock_db):
        """Test listing available nodes"""
        # Register a node first
        registration = {
            "seller_address": test_seller_account.address,
            "gpu_info": sample_gpu_info.model_dump(),
            "price_per_hour": 0.50,
            "endpoint": "http://localhost:8001"
        }
        await async_client.post("/api/v1/nodes/register", json=registration)

        # List nodes
        response = await async_client.get("/api/v1/nodes")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_filter_nodes_by_gpu_type(self, async_client: AsyncClient, mock_db):
        """Test filtering nodes by GPU type"""
        # Register CUDA node
        cuda_reg = {
            "seller_address": "0x1234567890123456789012345678901234567890",
            "gpu_info": {
                "gpu_type": "cuda",
                "device_name": "NVIDIA RTX 4090",
                "vram_gb": 24.0
            },
            "price_per_hour": 2.00,
            "endpoint": "http://localhost:8001"
        }
        await async_client.post("/api/v1/nodes/register", json=cuda_reg)

        # Register MPS node
        mps_reg = {
            "seller_address": "0x0987654321098765432109876543210987654321",
            "gpu_info": {
                "gpu_type": "mps",
                "device_name": "Apple M4 Max",
                "vram_gb": 64.0
            },
            "price_per_hour": 0.50,
            "endpoint": "http://localhost:8002"
        }
        await async_client.post("/api/v1/nodes/register", json=mps_reg)

        # Filter by CUDA
        response = await async_client.get("/api/v1/nodes", params={"gpu_type": "cuda"})
        assert response.status_code == 200
        data = response.json()
        # Should only return CUDA nodes
        for node in data["nodes"]:
            assert node["gpu_type"] == "cuda"

    def test_node_heartbeat(self, client: TestClient, test_seller_account, sample_gpu_info, mock_db):
        """Test node heartbeat updates"""
        # Register node first
        registration = {
            "seller_address": test_seller_account.address,
            "gpu_info": sample_gpu_info.model_dump(),
            "price_per_hour": 0.50,
            "endpoint": "http://localhost:8001"
        }
        reg_response = client.post("/api/v1/nodes/register", json=registration)
        node_id = reg_response.json()["node_id"]

        # Send heartbeat
        response = client.post(
            f"/api/v1/nodes/{node_id}/heartbeat",
            params={"available": True}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestJobSubmission:
    """Test job submission and management"""

    @pytest.mark.asyncio
    async def test_submit_job(self, async_client: AsyncClient, test_buyer_account, mock_db):
        """Test submitting a job to the queue"""
        response = await async_client.post(
            "/api/v1/jobs/submit",
            params={
                "buyer_address": test_buyer_account.address,
                "script": "print('Hello')",
                "max_price_per_hour": 10.0,
                "timeout_seconds": 300
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "PENDING"
        assert "job_id" in data
        assert data["buyer_address"] == test_buyer_account.address

    @pytest.mark.asyncio
    async def test_submit_job_with_gpu_requirement(self, async_client: AsyncClient, test_buyer_account, mock_db):
        """Test submitting a job with GPU requirements"""
        response = await async_client.post(
            "/api/v1/jobs/submit",
            params={
                "buyer_address": test_buyer_account.address,
                "script": "import torch; print(torch.cuda.is_available())",
                "max_price_per_hour": 5.0,
                "timeout_seconds": 600,
                "required_gpu_type": "cuda",
                "min_vram_gb": 8.0
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_claim_job(self, async_client: AsyncClient, test_buyer_account, test_seller_account, mock_db):
        """Test seller claiming a job from the queue"""
        # Submit a job first
        submit_response = await async_client.post(
            "/api/v1/jobs/submit",
            params={
                "buyer_address": test_buyer_account.address,
                "script": "print('test')",
                "max_price_per_hour": 10.0,
                "timeout_seconds": 300
            }
        )
        job_id = submit_response.json()["job_id"]

        # Claim the job
        claim_response = await async_client.post(
            "/api/v1/jobs/claim",
            params={
                "node_id": "test_node_1",
                "seller_address": test_seller_account.address,
                "gpu_type": "mps",
                "price_per_hour": 0.50,
                "vram_gb": 64.0
            }
        )

        assert claim_response.status_code == 200
        data = claim_response.json()
        assert data["claimed"] == True
        assert data["job_id"] == job_id

    @pytest.mark.asyncio
    async def test_claim_no_matching_job(self, async_client: AsyncClient, test_seller_account, mock_db):
        """Test claiming when no matching job exists"""
        # Don't submit any jobs, just try to claim
        response = await async_client.post(
            "/api/v1/jobs/claim",
            params={
                "node_id": "test_node_1",
                "seller_address": test_seller_account.address,
                "gpu_type": "cuda",
                "price_per_hour": 100.0,  # Very high price, no jobs will match
                "vram_gb": 24.0
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["claimed"] == False

    @pytest.mark.asyncio
    async def test_get_job_status(self, async_client: AsyncClient, test_buyer_account, mock_db):
        """Test retrieving job status"""
        # Submit a job
        submit_response = await async_client.post(
            "/api/v1/jobs/submit",
            params={
                "buyer_address": test_buyer_account.address,
                "script": "print('test')",
                "max_price_per_hour": 10.0,
                "timeout_seconds": 300
            }
        )
        job_id = submit_response.json()["job_id"]

        # Get status
        response = await async_client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "PENDING"

    @pytest.mark.asyncio
    async def test_cancel_job(self, async_client: AsyncClient, test_buyer_account, mock_db):
        """Test cancelling a pending job"""
        # Submit a job
        submit_response = await async_client.post(
            "/api/v1/jobs/submit",
            params={
                "buyer_address": test_buyer_account.address,
                "script": "print('test')",
                "max_price_per_hour": 10.0,
                "timeout_seconds": 300
            }
        )
        job_id = submit_response.json()["job_id"]

        # Cancel the job
        response = await async_client.post(
            f"/api/v1/jobs/{job_id}/cancel",
            params={"buyer_address": test_buyer_account.address}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "CANCELLED"


class TestJobLifecycle:
    """Test complete job lifecycle"""

    @pytest.mark.asyncio
    async def test_complete_job_lifecycle(self, async_client: AsyncClient, test_buyer_account, test_seller_account, mock_db):
        """Test full job lifecycle: submit -> claim -> start -> complete"""
        # 1. Submit job
        submit_response = await async_client.post(
            "/api/v1/jobs/submit",
            params={
                "buyer_address": test_buyer_account.address,
                "script": "print('Hello World')",
                "max_price_per_hour": 10.0,
                "timeout_seconds": 300
            }
        )
        assert submit_response.status_code == 201
        job_id = submit_response.json()["job_id"]

        # 2. Claim job
        claim_response = await async_client.post(
            "/api/v1/jobs/claim",
            params={
                "node_id": "test_node_1",
                "seller_address": test_seller_account.address,
                "gpu_type": "mps",
                "price_per_hour": 0.50,
                "vram_gb": 64.0
            }
        )
        assert claim_response.json()["claimed"] == True

        # 3. Start execution
        start_response = await async_client.post(f"/api/v1/jobs/{job_id}/start")
        assert start_response.status_code == 200
        assert start_response.json()["status"] == "EXECUTING"

        # 4. Complete job
        complete_response = await async_client.post(
            f"/api/v1/jobs/{job_id}/complete",
            params={
                "output": "Hello World",
                "exit_code": 0,
                "execution_duration": 5.5,
                "total_cost": 0.0008
            }
        )
        assert complete_response.status_code == 200
        assert complete_response.json()["status"] == "COMPLETED"

        # 5. Verify final status
        status_response = await async_client.get(f"/api/v1/jobs/{job_id}")
        data = status_response.json()
        assert data["status"] == "COMPLETED"
        assert data["result_output"] == "Hello World"
        assert data["exit_code"] == 0


class TestMarketplaceStats:
    """Test marketplace statistics endpoint"""

    @pytest.mark.asyncio
    async def test_marketplace_stats(self, async_client: AsyncClient, test_buyer_account, mock_db):
        """Test marketplace statistics"""
        # Register a node
        await async_client.post(
            "/api/v1/nodes/register",
            json={
                "seller_address": "0x1234567890123456789012345678901234567890",
                "gpu_info": {
                    "gpu_type": "mps",
                    "device_name": "Apple M4 Max",
                    "vram_gb": 64.0
                },
                "price_per_hour": 0.50,
                "endpoint": "http://localhost:8001"
            }
        )

        # Submit a job
        await async_client.post(
            "/api/v1/jobs/submit",
            params={
                "buyer_address": test_buyer_account.address,
                "script": "print('test')",
                "max_price_per_hour": 10.0,
                "timeout_seconds": 300
            }
        )

        # Get stats
        response = await async_client.get("/api/v1/stats")
        assert response.status_code == 200
        stats = response.json()

        assert "nodes" in stats
        assert "jobs" in stats
        assert stats["nodes"]["total_active"] >= 1
        assert stats["jobs"]["pending"] >= 1


class TestPendingJobs:
    """Test pending jobs queue endpoint"""

    @pytest.mark.asyncio
    async def test_get_pending_jobs(self, async_client: AsyncClient, test_buyer_account, mock_db):
        """Test getting pending jobs"""
        # Submit multiple jobs
        for i in range(3):
            await async_client.post(
                "/api/v1/jobs/submit",
                params={
                    "buyer_address": test_buyer_account.address,
                    "script": f"print('job {i}')",
                    "max_price_per_hour": 10.0,
                    "timeout_seconds": 300
                }
            )

        # Get pending jobs
        response = await async_client.get("/api/v1/jobs/queue/pending")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] >= 3
