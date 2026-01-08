from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request
import structlog

logger = structlog.get_logger()

def get_client_key(request: Request) -> str:
    """Get client identifier for rate limiting - uses IP address"""
    return get_remote_address(request)

def get_buyer_key(request: Request) -> str:
    """Get buyer address for rate limiting job submissions"""
    buyer = request.query_params.get("buyer_address", "")
    if buyer:
        return buyer
    return get_remote_address(request)

def get_node_key(request: Request) -> str:
    """Get node_id for rate limiting seller operations"""
    node_id = request.query_params.get("node_id", "")
    if node_id:
        return node_id
    return get_remote_address(request)

limiter = Limiter(key_func=get_client_key)
