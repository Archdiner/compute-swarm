"""
ComputeSwarm Configuration Management
Uses pydantic-settings for type-safe environment variable loading
"""

from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketplaceConfig(BaseSettings):
    """Configuration for the Marketplace FastAPI server"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Server Configuration
    marketplace_host: str = Field(default="0.0.0.0", description="Host to bind the server to")
    marketplace_port: int = Field(default=8000, description="Port to bind the server to")
    marketplace_workers: int = Field(default=4, description="Number of worker processes")

    # Network Configuration
    network: Literal["base-sepolia", "base-mainnet"] = Field(default="base-sepolia")
    rpc_url: str = Field(default="https://sepolia.base.org")

    # Payment Configuration
    usdc_contract_address: str = Field(
        default="0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        description="USDC contract address on Base"
    )
    payment_token: str = Field(default="USDC")
    min_balance_warning: float = Field(default=10.0)

    # x402 Protocol
    x402_enabled: bool = Field(default=True)
    payment_challenge_timeout: int = Field(default=300, description="Timeout in seconds")
    payment_verification_retries: int = Field(default=3)

    # CORS Configuration
    cors_origins: list[str] = Field(
        default=["http://localhost:3000"],
        description="Allowed CORS origins"
    )

    # Logging
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")
    log_format: Literal["json", "text"] = Field(default="json")

    # Development
    debug: bool = Field(default=False)
    reload: bool = Field(default=False)

    # Ngrok
    ngrok_enabled: bool = Field(default=False)
    ngrok_auth_token: str = Field(default="")

    # Coinbase Developer Platform
    cdp_api_key: str = Field(default="")
    cdp_api_secret: str = Field(default="")


class SellerConfig(BaseSettings):
    """Configuration for Seller Agent"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Wallet Configuration
    seller_private_key: str = Field(default="", description="Private key for payment receipt")
    seller_address: str = Field(default="", description="Seller wallet address")

    # Pricing Configuration
    default_price_per_hour_mps: float = Field(default=0.50, description="Price for Apple Silicon MPS")
    default_price_per_hour_cuda: float = Field(default=2.00, description="Price for NVIDIA CUDA")

    # Marketplace Connection
    marketplace_url: str = Field(default="http://localhost:8000", description="URL of marketplace server")

    # Compute Configuration
    max_concurrent_jobs: int = Field(default=1, description="Max simultaneous compute jobs")
    job_timeout: int = Field(default=3600, description="Max job duration in seconds")

    # Network Configuration
    network: Literal["base-sepolia", "base-mainnet"] = Field(default="base-sepolia")
    rpc_url: str = Field(default="https://sepolia.base.org")
    usdc_contract_address: str = Field(default="0x036CbD53842c5426634e7929541eC2318f3dCF7e")

    @field_validator("seller_private_key")
    @classmethod
    def validate_private_key(cls, v):
        if v and not v.startswith("0x"):
            return f"0x{v}"
        return v


class BuyerConfig(BaseSettings):
    """Configuration for Buyer Agent"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Wallet Configuration
    buyer_private_key: str = Field(default="", description="Private key for payments")
    buyer_address: str = Field(default="", description="Buyer wallet address")

    # Marketplace Connection
    marketplace_url: str = Field(default="http://localhost:8000", description="URL of marketplace server")

    # Payment Configuration
    max_hourly_budget: float = Field(default=10.0, description="Maximum spend per hour in USD")
    auto_approve_threshold: float = Field(default=1.0, description="Auto-approve jobs under this cost")

    # Network Configuration
    network: Literal["base-sepolia", "base-mainnet"] = Field(default="base-sepolia")
    rpc_url: str = Field(default="https://sepolia.base.org")
    usdc_contract_address: str = Field(default="0x036CbD53842c5426634e7929541eC2318f3dCF7e")

    @field_validator("buyer_private_key")
    @classmethod
    def validate_private_key(cls, v):
        if v and not v.startswith("0x"):
            return f"0x{v}"
        return v


# Singleton instances
_marketplace_config: MarketplaceConfig | None = None
_seller_config: SellerConfig | None = None
_buyer_config: BuyerConfig | None = None


def get_marketplace_config() -> MarketplaceConfig:
    """Get or create marketplace configuration singleton"""
    global _marketplace_config
    if _marketplace_config is None:
        _marketplace_config = MarketplaceConfig()
    return _marketplace_config


def get_seller_config() -> SellerConfig:
    """Get or create seller configuration singleton"""
    global _seller_config
    if _seller_config is None:
        _seller_config = SellerConfig()
    return _seller_config


def get_buyer_config() -> BuyerConfig:
    """Get or create buyer configuration singleton"""
    global _buyer_config
    if _buyer_config is None:
        _buyer_config = BuyerConfig()
    return _buyer_config
