"""
Factory Boy factories for generating test data
"""

import factory
from datetime import datetime
from eth_account import Account

from src.marketplace.models import (
    GPUType,
    GPUInfo,
    ComputeNode,
    NodeStatus,
    Job,
    JobRequest,
    JobStatus
)


class GPUInfoFactory(factory.Factory):
    """Factory for GPUInfo"""
    class Meta:
        model = GPUInfo

    gpu_type = GPUType.MPS
    device_name = "Apple M4 Max"
    vram_gb = 64.0
    compute_capability = None
    cuda_version = None
    driver_version = None


class ComputeNodeFactory(factory.Factory):
    """Factory for ComputeNode"""
    class Meta:
        model = ComputeNode

    node_id = factory.Sequence(lambda n: f"node_{n}")
    seller_address = factory.LazyFunction(lambda: Account.create().address)
    gpu_info = factory.SubFactory(GPUInfoFactory)
    price_per_hour = 0.50
    status = NodeStatus.AVAILABLE
    endpoint = factory.Sequence(lambda n: f"http://localhost:{8000 + n}")
    registered_at = factory.LazyFunction(datetime.utcnow)
    last_heartbeat = factory.LazyFunction(datetime.utcnow)
    total_jobs_completed = 0
    total_compute_hours = 0.0


class JobRequestFactory(factory.Factory):
    """Factory for JobRequest"""
    class Meta:
        model = JobRequest

    job_type = "train"
    script = "import torch\nprint('Hello GPU')"
    requirements = None
    max_duration_seconds = 300
    estimated_duration_seconds = None


class JobFactory(factory.Factory):
    """Factory for Job"""
    class Meta:
        model = Job

    job_id = factory.Sequence(lambda n: f"job_{n}")
    buyer_address = factory.LazyFunction(lambda: Account.create().address)
    node_id = "node_123"
    job_request = factory.SubFactory(JobRequestFactory)
    status = JobStatus.PENDING
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
        vram_gb=24.0,
        compute_capability="8.9",
        cuda_version="12.1"
    )
    price_per_hour = 2.00


class MPSNodeFactory(ComputeNodeFactory):
    """Factory for Apple Silicon MPS node"""
    gpu_info = factory.SubFactory(
        GPUInfoFactory,
        gpu_type=GPUType.MPS,
        device_name="Apple M4 Max",
        vram_gb=64.0
    )
    price_per_hour = 0.50
