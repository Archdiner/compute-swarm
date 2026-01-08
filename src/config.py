"""
ComputeSwarm Configuration Management
Uses pydantic-settings for type-safe environment variable loading
"""

import os
from dotenv import load_dotenv
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env file globally so os.getenv() works everywhere
load_dotenv()


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
    
    # Testnet Mode - When True, payments are simulated; when False, real USDC transfers
    testnet_mode: bool = Field(
        default=False, 
        description="Use simulated payments (testnet) or real transfers (production)"
    )

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

    # GitHub OAuth Configuration (for seller verification)
    github_client_id: str = Field(default="", description="GitHub OAuth App client ID")
    github_client_secret: str = Field(default="", description="GitHub OAuth App client secret")
    github_callback_url: str = Field(
        default="http://localhost:8000/auth/github/callback",
        description="GitHub OAuth callback URL"
    )

    # Supabase Configuration
    supabase_url: str = Field(default="", description="Supabase project URL")
    supabase_anon_key: str = Field(default="", description="Supabase anonymous key")

    # Supabase Storage Configuration
    supabase_storage_bucket: str = Field(
        default="job-files",
        description="Supabase storage bucket for job files"
    )
    file_expiry_hours: int = Field(
        default=24,
        description="Hours before uploaded files expire"
    )
    max_file_size_mb: int = Field(
        default=100,
        description="Maximum file size in MB"
    )

    # Session Configuration
    default_session_duration_minutes: int = Field(
        default=60,
        description="Default notebook/container session duration"
    )
    max_session_duration_minutes: int = Field(
        default=480,
        description="Maximum session duration (8 hours)"
    )
    session_heartbeat_interval: int = Field(
        default=60,
        description="Session heartbeat interval in seconds"
    )


class SellerConfig(BaseSettings):
    """Configuration for Seller Agent"""

    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
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
    job_timeout: int = Field(default=3600, description="Max job duration in seconds (batch jobs)")
    notebook_timeout: int = Field(default=7200, description="Max notebook session duration in seconds (2 hours)")
    container_timeout: int = Field(default=10800, description="Max container session duration in seconds (3 hours)")
    
    # Docker Sandboxing Configuration
    docker_enabled: bool = Field(default=True, description="Enable Docker sandboxing for job execution")
    docker_image: str = Field(default="computeswarm-sandbox:latest", description="Docker image for CPU sandboxed execution")
    docker_image_gpu: str = Field(default="computeswarm-sandbox-gpu:latest", description="Docker image for GPU (CUDA) sandboxed execution")
    docker_memory_limit: str = Field(default="4g", description="Memory limit for Docker containers")
    docker_cpu_limit: float = Field(default=2.0, description="CPU limit for Docker containers")
    docker_pids_limit: int = Field(default=100, description="Process limit for Docker containers")
    docker_tmpfs_size: str = Field(default="1g", description="Size of tmpfs mount in containers")
    
    # Model Cache Configuration (for persistent HuggingFace/PyTorch model caching)
    model_cache_dir: str = Field(
        default="~/.cache/computeswarm",
        description="Directory for persistent model cache (HuggingFace, PyTorch, etc.)"
    )
    model_cache_enabled: bool = Field(
        default=True,
        description="Enable persistent model caching across jobs"
    )
    
    # Network Access Configuration (for controlled network access during setup)
    docker_network_enabled: bool = Field(
        default=True,
        description="Enable controlled network access during setup phase (installs packages, downloads models)"
    )
    docker_setup_timeout: int = Field(
        default=300,
        description="Maximum time for network-enabled setup phase in seconds (5 minutes default)"
    )
    docker_network_whitelist: list[str] = Field(
        default=[
            "pypi.org",
            "files.pythonhosted.org",
            "huggingface.co",
            "github.com",
            "raw.githubusercontent.com",
            "cdn-lfs.huggingface.co",
            "download.pytorch.org",
            "s3.amazonaws.com"
        ],
        description="Whitelisted domains for network access during setup (DNS-based filtering not implemented, but documented)"
    )

    # Network Configuration
    network: Literal["base-sepolia", "base-mainnet"] = Field(default="base-sepolia")
    rpc_url: str = Field(default="https://sepolia.base.org")
    usdc_contract_address: str = Field(default="0x036CbD53842c5426634e7929541eC2318f3dCF7e")
    
    # Testnet Mode - When True, payments are simulated; when False, real USDC transfers
    testnet_mode: bool = Field(
        default=False, 
        description="Use simulated payments (testnet) or real transfers (production)"
    )

    # Session Configuration
    jupyter_docker_image: str = Field(
        default="jupyter/scipy-notebook:latest",
        description="Docker image for Jupyter notebook sessions"
    )
    jupyter_port_range_start: int = Field(
        default=8888,
        description="Starting port for Jupyter sessions"
    )
    jupyter_port_range_end: int = Field(
        default=8988,
        description="Ending port for Jupyter sessions"
    )
    allowed_docker_registries: list[str] = Field(
        default=["docker.io", "ghcr.io", "computeswarm"],
        description="Allowed Docker registries for custom containers"
    )

    # Public URL for session access (set to ngrok URL if using tunneling)
    public_host: str = Field(
        default="localhost",
        description="Public hostname for session URLs"
    )

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
