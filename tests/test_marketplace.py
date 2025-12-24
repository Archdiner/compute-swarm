"""
Unit and integration tests for marketplace API
"""

import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient

from tests.factories import ComputeNodeFactory, CUDANodeFactory, MPSNodeFactory, JobRequestFactory
from src.marketplace.models import NodeStatus, GPUType


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
        assert "active_nodes" in data
        assert "total_nodes" in data

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
        assert data["status"] == "available"
        assert "node_id" in data

    def test_register_node_validation(self, client: TestClient):
        """Test node registration with invalid data fails"""
        invalid_registration = {
            "seller_address": "invalid_address",  # Invalid format
            "price_per_hour": -1.0  # Negative price
        }

        response = client.post("/api/v1/nodes/register", json=invalid_registration)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_list_nodes(self, async_client: AsyncClient, test_seller_account, sample_gpu_info):
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
        nodes = response.json()
        assert len(nodes) == 1
        assert nodes[0]["seller_address"] == test_seller_account.address

    @pytest.mark.asyncio
    async def test_filter_nodes_by_gpu_type(self, async_client: AsyncClient):
        """Test filtering nodes by GPU type"""
        from src.marketplace.server import nodes_db

        # Add nodes with different GPU types
        cuda_node = CUDANodeFactory()
        mps_node = MPSNodeFactory()
        nodes_db[cuda_node.node_id] = cuda_node
        nodes_db[mps_node.node_id] = mps_node

        # Filter by CUDA
        response = await async_client.get("/api/v1/nodes", params={"gpu_type": "cuda"})
        assert response.status_code == 200
        nodes = response.json()
        assert len(nodes) == 1
        assert nodes[0]["gpu_info"]["gpu_type"] == "cuda"

        # Filter by MPS
        response = await async_client.get("/api/v1/nodes", params={"gpu_type": "mps"})
        assert response.status_code == 200
        nodes = response.json()
        assert len(nodes) == 1
        assert nodes[0]["gpu_info"]["gpu_type"] == "mps"

    def test_node_heartbeat(self, client: TestClient, sample_compute_node):
        """Test node heartbeat updates"""
        from src.marketplace.server import nodes_db

        # Add node to registry
        nodes_db[sample_compute_node.node_id] = sample_compute_node

        # Send heartbeat
        response = client.post(
            f"/api/v1/nodes/{sample_compute_node.node_id}/heartbeat",
            params={"node_status": "available"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify heartbeat was updated
        node = nodes_db[sample_compute_node.node_id]
        assert node.last_heartbeat is not None

    def test_unregister_node(self, client: TestClient, sample_compute_node):
        """Test node unregistration"""
        from src.marketplace.server import nodes_db

        # Add node
        nodes_db[sample_compute_node.node_id] = sample_compute_node

        # Unregister
        response = client.delete(f"/api/v1/nodes/{sample_compute_node.node_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "unregistered"

        # Verify node was removed
        assert sample_compute_node.node_id not in nodes_db


class TestJobSubmission:
    """Test job submission and management"""

    def test_submit_job_to_available_node(self, client: TestClient, sample_compute_node, test_buyer_account):
        """Test submitting a job to an available node"""
        from src.marketplace.server import nodes_db

        # Register node
        nodes_db[sample_compute_node.node_id] = sample_compute_node

        # Submit job
        job_request = JobRequestFactory()
        response = client.post(
            "/api/v1/jobs/submit",
            params={
                "node_id": sample_compute_node.node_id,
                "buyer_address": test_buyer_account.address
            },
            json=job_request.model_dump()
        )

        assert response.status_code == 201
        job = response.json()
        assert job["buyer_address"] == test_buyer_account.address
        assert job["node_id"] == sample_compute_node.node_id
        assert job["status"] == "pending"

    def test_submit_job_to_nonexistent_node(self, client: TestClient, test_buyer_account):
        """Test submitting a job to a non-existent node fails"""
        job_request = JobRequestFactory()
        response = client.post(
            "/api/v1/jobs/submit",
            params={
                "node_id": "nonexistent_node",
                "buyer_address": test_buyer_account.address
            },
            json=job_request.model_dump()
        )

        assert response.status_code == 404

    def test_submit_job_to_busy_node(self, client: TestClient, sample_compute_node, test_buyer_account):
        """Test submitting a job to a busy node fails"""
        from src.marketplace.server import nodes_db

        # Register node and mark as busy
        sample_compute_node.status = NodeStatus.BUSY
        nodes_db[sample_compute_node.node_id] = sample_compute_node

        # Attempt to submit job
        job_request = JobRequestFactory()
        response = client.post(
            "/api/v1/jobs/submit",
            params={
                "node_id": sample_compute_node.node_id,
                "buyer_address": test_buyer_account.address
            },
            json=job_request.model_dump()
        )

        assert response.status_code == 400
        assert "not available" in response.json()["detail"]

    def test_get_job_status(self, client: TestClient):
        """Test retrieving job status"""
        from src.marketplace.server import jobs_db
        from tests.factories import JobFactory

        # Create a job
        job = JobFactory()
        jobs_db[job.job_id] = job

        # Get status
        response = client.get(f"/api/v1/jobs/{job.job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job.job_id
        assert data["status"] == "pending"


class TestMarketplaceStats:
    """Test marketplace statistics endpoint"""

    def test_marketplace_stats(self, client: TestClient):
        """Test marketplace statistics"""
        from src.marketplace.server import nodes_db, jobs_db
        from tests.factories import JobFactory

        # Add some test data
        cuda_node = CUDANodeFactory()
        mps_node = MPSNodeFactory()
        nodes_db[cuda_node.node_id] = cuda_node
        nodes_db[mps_node.node_id] = mps_node

        job = JobFactory(status="completed")
        jobs_db[job.job_id] = job

        # Get stats
        response = client.get("/api/v1/stats")
        assert response.status_code == 200
        stats = response.json()

        assert stats["nodes"]["total"] == 2
        assert stats["nodes"]["available"] == 2
        assert stats["jobs"]["total"] == 1
        assert stats["jobs"]["completed"] == 1
