"""
Data models for ComputeSwarm Marketplace
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class GPUType(str, Enum):
    """Supported GPU types"""
    CUDA = "cuda"
    MPS = "mps"  # Apple Silicon Metal Performance Shaders
    ROCM = "rocm"  # AMD ROCm (future support)
    CPU = "cpu"  # CPU-only fallback
    UNKNOWN = "unknown"


class NodeStatus(str, Enum):
    """Status of a compute node"""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class JobStatus(str, Enum):
    """Status of a compute job"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class GPUInfo(BaseModel):
    """GPU hardware information"""
    gpu_type: GPUType
    device_name: str
    vram_gb: float
    compute_capability: Optional[str] = None
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None


class ComputeNode(BaseModel):
    """Represents a seller's compute node in the marketplace"""
    node_id: str = Field(description="Unique identifier for the node")
    seller_address: str = Field(description="Wallet address of the seller")
    gpu_info: GPUInfo
    price_per_hour: float = Field(description="Price in USD per hour")
    status: NodeStatus = Field(default=NodeStatus.AVAILABLE)
    endpoint: str = Field(description="HTTP endpoint for job submission")
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)
    total_jobs_completed: int = Field(default=0)
    total_compute_hours: float = Field(default=0.0)

    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "node_550e8400-e29b-41d4-a716-446655440000",
                "seller_address": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb",
                "gpu_info": {
                    "gpu_type": "mps",
                    "device_name": "Apple M4 Max",
                    "vram_gb": 64.0,
                    "compute_capability": None,
                    "cuda_version": None,
                    "driver_version": None
                },
                "price_per_hour": 0.50,
                "status": "available",
                "endpoint": "http://192.168.1.100:8001"
            }
        }


class NodeRegistration(BaseModel):
    """Request model for registering a new compute node"""
    seller_address: str
    gpu_info: GPUInfo
    price_per_hour: float
    endpoint: str


class JobRequest(BaseModel):
    """Request to execute a compute job"""
    job_type: str = Field(description="Type of job: 'train', 'inference', 'benchmark'")
    script: str = Field(description="Python script to execute")
    requirements: Optional[list[str]] = Field(default=None, description="Additional pip packages")
    max_duration_seconds: int = Field(default=3600, description="Maximum job duration")
    estimated_duration_seconds: Optional[int] = Field(default=None)

    class Config:
        json_schema_extra = {
            "example": {
                "job_type": "train",
                "script": "import torch\nprint(torch.cuda.is_available())",
                "requirements": ["transformers==4.30.0"],
                "max_duration_seconds": 600
            }
        }


class Job(BaseModel):
    """Represents a compute job"""
    job_id: str
    buyer_address: str
    node_id: str
    job_request: JobRequest
    status: JobStatus = Field(default=JobStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None
    total_cost_usd: Optional[float] = None
    payment_tx_hash: Optional[str] = None


class PaymentChallenge(BaseModel):
    """x402 Payment challenge issued by seller"""
    challenge_id: str
    amount_usd: float
    amount_usdc: str  # Wei amount in string format
    seller_address: str
    buyer_address: str
    job_id: str
    expires_at: datetime
    payment_details: Dict[str, Any] = Field(
        description="x402 protocol payment details"
    )


class PaymentProof(BaseModel):
    """x402 Payment proof submitted by buyer"""
    challenge_id: str
    signature: str
    transaction_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class X402Manifest(BaseModel):
    """x402 protocol manifest"""
    version: str = "1.0"
    name: str = "ComputeSwarm"
    description: str = "Decentralized P2P GPU Marketplace"
    payment_methods: list[str] = ["x402-usdc"]
    supported_networks: list[str] = ["base-sepolia", "base-mainnet"]
    endpoints: Dict[str, str]

    class Config:
        json_schema_extra = {
            "example": {
                "version": "1.0",
                "name": "ComputeSwarm",
                "description": "Decentralized P2P GPU Marketplace",
                "payment_methods": ["x402-usdc"],
                "supported_networks": ["base-sepolia", "base-mainnet"],
                "endpoints": {
                    "discovery": "/api/v1/nodes",
                    "register": "/api/v1/nodes/register",
                    "submit_job": "/api/v1/jobs/submit"
                }
            }
        }
