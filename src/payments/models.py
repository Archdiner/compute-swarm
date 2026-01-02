"""
x402-compliant payment models for ComputeSwarm
Minimal models following the x402 protocol specification
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class PaymentAccepts(BaseModel):
    """Single payment option in x402 format"""
    network: str = Field(default="base-sepolia", description="Blockchain network")
    scheme: str = Field(default="exact", description="Payment scheme")
    recipient: str = Field(description="Seller wallet address")
    amount: str = Field(description="Amount in smallest unit (USDC has 6 decimals)")
    token: str = Field(default="USDC", description="Token symbol")


class PaymentRequired(BaseModel):
    """x402 Payment Required response body (HTTP 402)"""
    x402Version: str = "1"
    accepts: List[PaymentAccepts]
    description: str
    error: Optional[str] = None
    job_id: Optional[str] = None  # Extension for job tracking
    expires_at: Optional[datetime] = None


class PaymentAuthorization(BaseModel):
    """EIP-712 typed data for payment authorization"""
    from_address: str = Field(alias="from")
    to: str
    value: str
    valid_after: int = Field(default=0, alias="validAfter")
    valid_before: int = Field(alias="validBefore")
    nonce: str

    class Config:
        populate_by_name = True


class PaymentPayload(BaseModel):
    """x402 Payment payload submitted by buyer"""
    x402Version: str = "1"
    scheme: str = "exact"
    network: str = "base-sepolia"
    payload: dict = Field(description="Contains signature and authorization")


class PaymentReceipt(BaseModel):
    """Payment confirmation returned after settlement"""
    success: bool
    tx_hash: Optional[str] = None
    amount_usdc: str
    from_address: str
    to_address: str
    job_id: str
    settled_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None

