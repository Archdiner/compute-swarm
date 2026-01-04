"""
ComputeSwarm Core Data Models
Shared models for database operations and API
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class GPUType(str, Enum):
    """Supported GPU types"""
    CUDA = "cuda"
    MPS = "mps"
    ROCM = "rocm"
    CPU = "cpu"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    """Job lifecycle states"""
    PENDING = "PENDING"
    CLAIMED = "CLAIMED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class VerificationStatus(str, Enum):
    """Seller verification status"""
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"


class GPUInfo(BaseModel):
    """GPU hardware information"""
    gpu_type: GPUType
    device_name: str
    vram_gb: Optional[Decimal] = None
    num_gpus: int = Field(default=1, ge=1, description="Number of GPUs available")
    compute_capability: Optional[str] = None
    cuda_version: Optional[str] = None
    driver_version: Optional[str] = None


class ComputeNode(BaseModel):
    """Represents a seller's compute node"""
    node_id: str
    seller_address: str
    gpu_info: GPUInfo
    price_per_hour: Decimal
    is_available: bool = True
    last_heartbeat: Optional[datetime] = None
    created_at: Optional[datetime] = None
    seller_profile_id: Optional[str] = None

    class Config:
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat() if v else None
        }


class ComputeJob(BaseModel):
    """Represents a compute job in the queue"""
    job_id: Optional[str] = None
    buyer_address: str
    script: str
    requirements: Optional[str] = None
    max_price_per_hour: Decimal
    timeout_seconds: int = 3600
    required_gpu_type: Optional[GPUType] = None
    min_vram_gb: Optional[Decimal] = None
    num_gpus: int = Field(default=1, ge=1, le=8, description="Number of GPUs required (1-8)")
    
    # Assignment fields (filled when claimed)
    node_id: Optional[str] = None
    seller_address: Optional[str] = None
    
    # Status tracking
    status: JobStatus = JobStatus.PENDING
    claimed_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Results
    result_output: Optional[str] = None
    result_error: Optional[str] = None
    exit_code: Optional[int] = None
    execution_duration_seconds: Optional[Decimal] = None
    total_cost_usd: Optional[Decimal] = None
    payment_tx_hash: Optional[str] = None
    
    # Metadata
    created_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat() if v else None
        }


class SellerProfile(BaseModel):
    """Seller profile with verification and reputation"""
    id: Optional[str] = None
    seller_address: str
    
    # GitHub OAuth fields
    github_id: Optional[int] = None
    github_username: Optional[str] = None
    github_avatar_url: Optional[str] = None
    github_profile_url: Optional[str] = None
    
    # Verification
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    verified_at: Optional[datetime] = None
    
    # Reputation
    reputation_score: Decimal = Decimal("0.00")
    total_ratings: int = 0
    total_jobs_completed: int = 0
    total_earnings_usd: Decimal = Decimal("0.00")
    
    # Profile
    display_name: Optional[str] = None
    bio: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @field_validator('seller_address')
    @classmethod
    def validate_address(cls, v):
        if not v.startswith('0x') or len(v) != 42:
            raise ValueError('Invalid Ethereum address format')
        return v.lower()

    class Config:
        json_encoders = {
            Decimal: float,
            datetime: lambda v: v.isoformat() if v else None
        }


class SellerRating(BaseModel):
    """Rating for a seller from a buyer"""
    id: Optional[str] = None
    job_id: str
    buyer_address: str
    seller_address: str
    
    # Rating details
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    
    # Timestamps
    created_at: Optional[datetime] = None

    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('Rating must be between 1 and 5')
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class RatingRequest(BaseModel):
    """Request to rate a seller"""
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
