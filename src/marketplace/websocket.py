"""
WebSocket infrastructure for real-time log streaming
Allows buyers to watch job output in real-time
"""

import asyncio
from typing import Dict, Set, Optional
from datetime import datetime
from dataclasses import dataclass, field
import json

from fastapi import WebSocket, WebSocketDisconnect
import structlog

logger = structlog.get_logger()


@dataclass
class LogEntry:
    """A log entry for a job"""
    timestamp: str
    level: str  # info, warn, error, stdout, stderr
    message: str
    job_id: str


@dataclass
class JobLogBuffer:
    """Buffer for job logs with subscriber management"""
    job_id: str
    logs: list = field(default_factory=list)
    subscribers: Set[WebSocket] = field(default_factory=set)
    max_logs: int = 1000
    created_at: datetime = field(default_factory=datetime.utcnow)


class WebSocketManager:
    """
    Manages WebSocket connections for log streaming
    
    Features:
    - Multiple subscribers per job
    - Log buffering for late joiners
    - Automatic cleanup of stale connections
    - Message broadcasting
    """
    
    def __init__(self, max_buffer_size: int = 1000, buffer_ttl_minutes: int = 60):
        """
        Initialize WebSocket manager
        
        Args:
            max_buffer_size: Maximum log entries to buffer per job
            buffer_ttl_minutes: How long to keep log buffers after last subscriber leaves
        """
        self.max_buffer_size = max_buffer_size
        self.buffer_ttl_minutes = buffer_ttl_minutes
        
        # Job ID -> JobLogBuffer
        self.job_buffers: Dict[str, JobLogBuffer] = {}
        
        # All active connections
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket, job_id: str) -> None:
        """
        Accept a new WebSocket connection for a job
        
        Args:
            websocket: WebSocket connection
            job_id: Job to subscribe to
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        
        # Create or get job buffer
        if job_id not in self.job_buffers:
            self.job_buffers[job_id] = JobLogBuffer(job_id=job_id)
        
        buffer = self.job_buffers[job_id]
        buffer.subscribers.add(websocket)
        
        logger.info(
            "websocket_connected",
            job_id=job_id,
            total_subscribers=len(buffer.subscribers)
        )
        
        # Send buffered logs to new subscriber
        if buffer.logs:
            for log_entry in buffer.logs:
                try:
                    await websocket.send_json({
                        "type": "log",
                        "data": {
                            "timestamp": log_entry.timestamp,
                            "level": log_entry.level,
                            "message": log_entry.message
                        }
                    })
                except Exception:
                    break
    
    def disconnect(self, websocket: WebSocket, job_id: str) -> None:
        """
        Handle WebSocket disconnection
        
        Args:
            websocket: WebSocket connection
            job_id: Job ID they were subscribed to
        """
        self.active_connections.discard(websocket)
        
        if job_id in self.job_buffers:
            self.job_buffers[job_id].subscribers.discard(websocket)
            
            logger.info(
                "websocket_disconnected",
                job_id=job_id,
                remaining_subscribers=len(self.job_buffers[job_id].subscribers)
            )
    
    async def broadcast_log(
        self,
        job_id: str,
        message: str,
        level: str = "info"
    ) -> None:
        """
        Broadcast a log message to all subscribers of a job
        
        Args:
            job_id: Job ID
            message: Log message
            level: Log level (info, warn, error, stdout, stderr)
        """
        # Create log entry
        log_entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level,
            message=message,
            job_id=job_id
        )
        
        # Add to buffer
        if job_id not in self.job_buffers:
            self.job_buffers[job_id] = JobLogBuffer(job_id=job_id)
        
        buffer = self.job_buffers[job_id]
        buffer.logs.append(log_entry)
        
        # Trim buffer if needed
        if len(buffer.logs) > self.max_buffer_size:
            buffer.logs = buffer.logs[-self.max_buffer_size:]
        
        # Broadcast to subscribers
        if buffer.subscribers:
            payload = {
                "type": "log",
                "data": {
                    "timestamp": log_entry.timestamp,
                    "level": level,
                    "message": message
                }
            }
            
            disconnected = set()
            for websocket in buffer.subscribers:
                try:
                    await websocket.send_json(payload)
                except Exception:
                    disconnected.add(websocket)
            
            # Clean up disconnected
            for ws in disconnected:
                self.disconnect(ws, job_id)
    
    async def broadcast_status(
        self,
        job_id: str,
        status: str,
        details: Optional[dict] = None
    ) -> None:
        """
        Broadcast a status update to all subscribers
        
        Args:
            job_id: Job ID
            status: Status string
            details: Optional additional details
        """
        if job_id not in self.job_buffers:
            return
        
        buffer = self.job_buffers[job_id]
        
        payload = {
            "type": "status",
            "data": {
                "job_id": job_id,
                "status": status,
                "timestamp": datetime.utcnow().isoformat(),
                **(details or {})
            }
        }
        
        disconnected = set()
        for websocket in buffer.subscribers:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.add(websocket)
        
        # Clean up
        for ws in disconnected:
            self.disconnect(ws, job_id)
    
    async def broadcast_completion(
        self,
        job_id: str,
        success: bool,
        output: str,
        error: Optional[str] = None,
        exit_code: int = 0,
        execution_time: float = 0.0,
        total_cost: float = 0.0
    ) -> None:
        """
        Broadcast job completion to all subscribers
        
        Args:
            job_id: Job ID
            success: Whether job succeeded
            output: Job output
            error: Error message if failed
            exit_code: Exit code
            execution_time: Execution time in seconds
            total_cost: Total cost in USD
        """
        if job_id not in self.job_buffers:
            return
        
        buffer = self.job_buffers[job_id]
        
        payload = {
            "type": "complete",
            "data": {
                "job_id": job_id,
                "success": success,
                "output": output,
                "error": error,
                "exit_code": exit_code,
                "execution_time": execution_time,
                "total_cost": total_cost,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        disconnected = set()
        for websocket in buffer.subscribers:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.add(websocket)
        
        # Clean up
        for ws in disconnected:
            self.disconnect(ws, job_id)
        
        logger.info(
            "job_completion_broadcast",
            job_id=job_id,
            success=success,
            subscribers=len(buffer.subscribers)
        )
    
    def get_subscriber_count(self, job_id: str) -> int:
        """Get number of subscribers for a job"""
        if job_id in self.job_buffers:
            return len(self.job_buffers[job_id].subscribers)
        return 0
    
    def get_buffered_logs(self, job_id: str) -> list:
        """Get buffered logs for a job"""
        if job_id in self.job_buffers:
            return [
                {
                    "timestamp": log.timestamp,
                    "level": log.level,
                    "message": log.message
                }
                for log in self.job_buffers[job_id].logs
            ]
        return []
    
    async def cleanup_stale_buffers(self) -> int:
        """
        Clean up log buffers with no subscribers and past TTL
        
        Returns:
            Number of buffers cleaned up
        """
        from datetime import timedelta
        
        now = datetime.utcnow()
        ttl = timedelta(minutes=self.buffer_ttl_minutes)
        
        stale_jobs = [
            job_id for job_id, buffer in self.job_buffers.items()
            if not buffer.subscribers and (now - buffer.created_at) > ttl
        ]
        
        for job_id in stale_jobs:
            del self.job_buffers[job_id]
        
        if stale_jobs:
            logger.info("stale_log_buffers_cleaned", count=len(stale_jobs))
        
        return len(stale_jobs)
    
    def close_all(self) -> None:
        """Close all connections and clear buffers"""
        self.active_connections.clear()
        self.job_buffers.clear()


# Singleton instance
_websocket_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get or create WebSocket manager singleton"""
    global _websocket_manager
    
    if _websocket_manager is None:
        _websocket_manager = WebSocketManager()
    
    return _websocket_manager

