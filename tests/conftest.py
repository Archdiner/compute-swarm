"""
Pytest configuration and shared fixtures
"""

import pytest
from typing import AsyncGenerator
from httpx import AsyncClient
from fastapi.testclient import TestClient
from eth_account import Account

from src.marketplace.server import app
from src.marketplace.models import GPUType, GPUInfo, ComputeNode
from src.config import get_marketplace_config


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
        price_per_hour=0.50,
        endpoint="http://localhost:8001",
        status="available"
    )


@pytest.fixture
def client() -> TestClient:
    """Create FastAPI test client (sync)"""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def clear_marketplace_state():
    """Clear marketplace state before each test"""
    from src.marketplace.server import nodes_db, jobs_db
    nodes_db.clear()
    jobs_db.clear()
    yield
    nodes_db.clear()
    jobs_db.clear()


@pytest.fixture
def mock_web3_provider():
    """Mock Web3 provider for testing blockchain interactions"""
    from web3 import Web3
    from eth_tester import EthereumTester

    tester = EthereumTester()
    return Web3(Web3.EthereumTesterProvider(tester))
