import uuid
from decimal import Decimal
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Request, HTTPException, status, Depends
import structlog

from src.marketplace.models import NodeRegistration, GPUType
from src.models import ComputeNode, GPUInfo
from src.database import get_db_client, DatabaseClient
from src.marketplace.dependencies import limiter, logger

router = APIRouter(prefix="/api/v1/nodes", tags=["Nodes"])

@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register_node(request: Request, registration: NodeRegistration):
    """
    Register a new compute node in the marketplace
    Called by Seller Agent on startup
    """
    db = get_db_client()

    # Import locally to avoid circular imports if any, though here it should be fine
    from src.models import GPUType as ModelsGPUType
    
    node_id = f"node_{uuid.uuid4().hex[:12]}"

    # Convert GPUInfo from marketplace.models to src.models format
    # Use model_dump(mode='python') to ensure enums are converted to their values
    gpu_info_dict = registration.gpu_info.model_dump(mode='python')
    # Convert vram_gb from float to Decimal if present
    if 'vram_gb' in gpu_info_dict and gpu_info_dict['vram_gb'] is not None:
        gpu_info_dict['vram_gb'] = Decimal(str(gpu_info_dict['vram_gb']))
    
    # Ensure gpu_type is converted to the correct enum type from src.models
    if 'gpu_type' in gpu_info_dict:
        gpu_info_dict['gpu_type'] = ModelsGPUType(gpu_info_dict['gpu_type'])
    
    gpu_info = GPUInfo(**gpu_info_dict)
    
    node = ComputeNode(
        node_id=node_id,
        seller_address=registration.seller_address,
        gpu_info=gpu_info,
        price_per_hour=Decimal(str(registration.price_per_hour)),
        is_available=True
    )

    await db.register_node(node)

    logger.info(
        "node_registered",
        node_id=node_id,
        seller=registration.seller_address,
        gpu_type=registration.gpu_info.gpu_type.value,
        price=float(registration.price_per_hour)
    )

    return {
        "node_id": node_id,
        "seller_address": node.seller_address,
        "gpu_info": {
            "gpu_type": node.gpu_info.gpu_type.value,
            "device_name": node.gpu_info.device_name,
            "vram_gb": float(node.gpu_info.vram_gb) if node.gpu_info.vram_gb else None,
            "compute_capability": node.gpu_info.compute_capability
        },
        "price_per_hour": float(node.price_per_hour),
        "is_available": node.is_available
    }


@router.get("", tags=["Marketplace"])
@limiter.limit("100/minute")
async def list_nodes(
    request: Request,
    gpu_type: Optional[str] = None,
    max_price: Optional[float] = None,
):
    """
    Discover available compute nodes
    Shows only nodes with recent heartbeat (active)
    """
    db = get_db_client()

    gpu_type_enum = GPUType(gpu_type) if gpu_type else None
    max_price_decimal = Decimal(str(max_price)) if max_price else None

    nodes = await db.get_active_nodes(
        gpu_type=gpu_type_enum,
        max_price=max_price_decimal
    )

    logger.info("nodes_listed", count=len(nodes), filters={
        "gpu_type": gpu_type,
        "max_price": max_price
    })

    return {"nodes": nodes, "count": len(nodes)}


@router.get("/{node_id}")
@limiter.limit("100/minute")
async def get_node(request: Request, node_id: str):
    """Get details for a specific node"""
    db = get_db_client()

    node = await db.get_node(node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} not found"
        )

    return node


@router.post("/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, available: bool = True, p2p_url: Optional[str] = None):
    """
    Update node heartbeat and availability
    Called periodically by Seller Agent (every 30-60 seconds recommended)
    """
    db = get_db_client()

    try:
        await db.update_node_heartbeat(node_id, p2p_url=p2p_url)
        await db.set_node_availability(node_id, available)

        logger.debug("heartbeat_received", node_id=node_id, available=available)

        return {"status": "ok", "node_id": node_id, "timestamp": datetime.utcnow().isoformat()}

    except Exception as e:
        logger.error("heartbeat_failed", node_id=node_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update heartbeat: {str(e)}"
        )


@router.post("/{node_id}/unavailable")
async def mark_node_unavailable(node_id: str):
    """
    Mark node as unavailable (busy with job or going offline)
    Called by Seller Agent before executing job or shutdown
    """
    db = get_db_client()

    await db.set_node_availability(node_id, False)
    logger.info("node_marked_unavailable", node_id=node_id)

    return {"status": "unavailable", "node_id": node_id}
