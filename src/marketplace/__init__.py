"""
Marketplace module for ComputeSwarm
Provides the FastAPI server and WebSocket log streaming
"""

from src.marketplace.websocket import WebSocketManager, get_websocket_manager

__all__ = ["WebSocketManager", "get_websocket_manager"]
