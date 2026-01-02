"""
Factory Boy factories for generating test data
Uses models from src/models.py for consistency
"""

import factory
from datetime import datetime
from decimal import Decimal
from eth_account import Account

from src.models import (
    GPUType,
    GPUInfo,
    ComputeNode,
    ComputeJob,
    JobStatus,
)
from src.marketplace.models import (
    JobRequest,
    Job,
    NodeStatus,
)


class GPUInfoFactory(factory.Factory):
    """Factory for GPUInfo"""
    class Meta:
        model = GPUInfo

    gpu_type = GPUType.MPS
    device_name = "Apple M4 Max"
    vram_gb = Decimal("64.0")
    compute_capability = None
    cuda_version = None
    driver_version = None


class ComputeNodeFactory(factory.Factory):
    """Factory for ComputeNode (from src/models.py)"""
    class Meta:
        model = ComputeNode

    node_id = factory.Sequence(lambda n: f"node_{n}")
    seller_address = factory.LazyFunction(lambda: Account.create().address)
    gpu_info = factory.SubFactory(GPUInfoFactory)
    price_per_hour = Decimal("0.50")
    is_available = True
    last_heartbeat = factory.LazyFunction(datetime.utcnow)
    created_at = factory.LazyFunction(datetime.utcnow)


class ComputeJobFactory(factory.Factory):
    """Factory for ComputeJob (from src/models.py)"""
    class Meta:
        model = ComputeJob

    job_id = factory.Sequence(lambda n: f"job_{n}")
    buyer_address = factory.LazyFunction(lambda: Account.create().address)
    script = "import torch\nprint('Hello GPU')"
    requirements = None
    max_price_per_hour = Decimal("10.0")
    timeout_seconds = 3600
    required_gpu_type = None
    min_vram_gb = None
    status = JobStatus.PENDING
    created_at = factory.LazyFunction(datetime.utcnow)


class JobRequestFactory(factory.Factory):
    """Factory for JobRequest (marketplace model for API)"""
    class Meta:
        model = JobRequest

    job_type = "train"
    script = "import torch\nprint('Hello GPU')"
    requirements = None
    max_duration_seconds = 300
    estimated_duration_seconds = None


class JobFactory(factory.Factory):
    """Factory for Job (marketplace model for API)"""
    class Meta:
        model = Job

    job_id = factory.Sequence(lambda n: f"job_{n}")
    buyer_address = factory.LazyFunction(lambda: Account.create().address)
    node_id = "node_123"
    job_request = factory.SubFactory(JobRequestFactory)
    status = "PENDING"
    created_at = factory.LazyFunction(datetime.utcnow)
    started_at = None
    completed_at = None
    output = None
    error = None
    total_cost_usd = None
    payment_tx_hash = None


# Convenience factories with specific GPU types
class CUDANodeFactory(ComputeNodeFactory):
    """Factory for CUDA GPU node"""
    gpu_info = factory.SubFactory(
        GPUInfoFactory,
        gpu_type=GPUType.CUDA,
        device_name="NVIDIA RTX 4090",
        vram_gb=Decimal("24.0"),
        compute_capability="8.9",
        cuda_version="12.1"
    )
    price_per_hour = Decimal("2.00")


class MPSNodeFactory(ComputeNodeFactory):
    """Factory for Apple Silicon MPS node"""
    gpu_info = factory.SubFactory(
        GPUInfoFactory,
        gpu_type=GPUType.MPS,
        device_name="Apple M4 Max",
        vram_gb=Decimal("64.0")
    )
    price_per_hour = Decimal("0.50")
