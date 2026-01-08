"""
ComputeSwarm Marketplace Server
Queue-based job marketplace with Supabase database
"""

import os
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
import structlog

from src.config import get_marketplace_config
from src.database import get_db_client
from src.marketplace.dependencies import limiter, logger

# Import routers
from src.marketplace.routers import (
    nodes,
    jobs,
    stats,
    experiments,
    artifacts,
    general,
)
from src.marketplace.tasks import run_maintenance_tasks


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app"""
    config = get_marketplace_config()
    logger.info(
        "marketplace_starting",
        host=config.marketplace_host,
        port=config.marketplace_port,
        network=config.network
    )

    # Initialize database client (optional for health checks)
    try:
        db = get_db_client()
        logger.info("database_connected", database="supabase")
    except Exception as e:
        logger.warning("database_connection_failed", error=str(e))
        logger.warning("app_starting_without_database", message="Some endpoints may not work")
        db = None

    # Start background maintenance tasks
    maintenance_task = asyncio.create_task(run_maintenance_tasks())

    yield

    # Cleanup
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass

    logger.info("marketplace_shutting_down")


# Initialize FastAPI app with enhanced documentation
app = FastAPI(
    title="ComputeSwarm Marketplace",
    description="""
    **Decentralized P2P GPU Marketplace with x402 Micropayments**
    
    ComputeSwarm connects GPU sellers with buyers through trustless, per-second USDC payments on Base L2.
    
    ### Features
    - Queue-based job submission and matching
    - x402 protocol for trustless payments
    - Multi-GPU support (NVIDIA CUDA, Apple Silicon MPS)
    - Real-time job monitoring and cost estimation
    - Seller earnings tracking
    
    ### Quick Start
    - Submit jobs: `POST /api/v1/jobs/submit`
    - Check status: `GET /api/v1/jobs/{job_id}`
    - View marketplace: `GET /api/v1/stats`
    
    Built for the x402 Hackathon.
    """,
    version="0.1.0",
    contact={
        "name": "ComputeSwarm",
        "url": "https://github.com/Archdiner/compute-swarm",
    },
    license_info={
        "name": "MIT",
    },
    lifespan=lifespan
)

# Attach limiter to app state and add exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware with configurable origins
config = get_marketplace_config()
# Default frontend origins for development
default_origins = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"]
cors_origins = config.cors_origins if config.cors_origins else default_origins

# Add frontend URL from environment if provided
frontend_url = os.getenv("FRONTEND_URL")
if frontend_url and frontend_url not in cors_origins:
    cors_origins.append(frontend_url)

logger.info("cors_origins_configured", origins=cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(general.router)
app.include_router(nodes.router)
app.include_router(jobs.router)
app.include_router(stats.router)
app.include_router(experiments.router)
app.include_router(artifacts.router)

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.marketplace.server:app",
        host=config.marketplace_host,
        port=config.marketplace_port,
        reload=config.reload,
        log_level=config.log_level.lower()
    )
