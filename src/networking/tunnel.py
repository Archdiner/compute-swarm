"""
Tunneling Module for ComputeSwarm
Manages secure tunnels using ngrok to allow nodes to be accessible from the public internet logic.
"""

import os
import sys
import time
import asyncio
from typing import Optional
import structlog
from pyngrok import ngrok, conf

logger = structlog.get_logger()

class TunnelManager:
    """
    Manages ngrok tunnels for exposing local services.
    """
    
    def __init__(self, port: int = 8000, protocol: str = "http"):
        self.port = port
        self.protocol = protocol
        self.public_url: Optional[str] = None
        self.tunnel = None
        
        # Configure ngrok if token is present
        self.auth_token = os.getenv("NGROK_AUTH_TOKEN")
        if self.auth_token:
            conf.get_default().auth_token = self.auth_token
            logger.info("ngrok_auth_token_configured")
        else:
            logger.warning("ngrok_no_auth_token", message="Session will be capable of short tunnels only")

    async def start(self) -> str:
        """
        Start the tunnel and return the public URL.
        """
        if self.tunnel:
            return self.public_url

        try:
            self._connect()
            
            # Start monitoring in background
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            
            return self.public_url
            
        except Exception as e:
            logger.error("tunnel_start_failed", error=str(e), message="Falling back to local URL")
            self.public_url = f"http://localhost:{self.port}"
            return self.public_url

    def _connect(self):
        """Internal method to establish connection"""
        # Open a tunnel to the local port
        self.tunnel = ngrok.connect(self.port, self.protocol)
        self.public_url = self.tunnel.public_url
        
        logger.info(
            "tunnel_started",
            local_port=self.port,
            public_url=self.public_url,
            protocol=self.protocol
        )

    async def _monitor_loop(self):
        """Monitor tunnel health and reconnect if necessary"""
        logger.info("tunnel_monitor_started")
        while True:
            try:
                await asyncio.sleep(10) # Check every 10 seconds
                
                # Active check: Verify tunnel is still in ngrok's active list
                active_tunnels = ngrok.get_tunnels()
                is_active = any(t.public_url == self.public_url for t in active_tunnels)
                
                if not is_active:
                    logger.warning("tunnel_not_found_active", public_url=self.public_url)
                    await self._reconnect()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("tunnel_monitor_error", error=str(e))
                # If exception occurs, wait a bit and try to reconnect
                await asyncio.sleep(5)
                await self._reconnect()

    async def _reconnect(self):
        """Attempt to reconnect the tunnel with exponential backoff"""
        logger.info("tunnel_reconnecting")
        
        self.stop_monitor() # Stop monitoring while reconnecting
        
        if self.tunnel:
            try:
                ngrok.disconnect(self.public_url)
            except:
                pass
            self.tunnel = None
            self.public_url = None

        max_retries = 5
        base_delay = 2
        
        for i in range(max_retries):
            try:
                delay = base_delay * (2 ** i)
                logger.info("reconnect_attempt", attempt=i+1, delay=delay)
                await asyncio.sleep(delay)
                
                self._connect()
                
                # Restart monitoring
                self._monitor_task = asyncio.create_task(self._monitor_loop())
                
                logger.info("tunnel_reconnected", new_url=self.public_url)
                return
            except Exception as e:
                logger.error("reconnect_attempt_failed", attempt=i+1, error=str(e))
                
        logger.critical("tunnel_reconnection_exhausted")

    def stop_monitor(self):
        """Internal helper to stop monitor loop without stopping tunnel"""
        if hasattr(self, '_monitor_task') and self._monitor_task:
            self._monitor_task.cancel()
            self._monitor_task = None

    def stop(self):
        """
        Stop the tunnel.
        """
        if hasattr(self, '_monitor_task') and self._monitor_task:
            self._monitor_task.cancel()
            
        if self.tunnel:
            try:
                ngrok.disconnect(self.public_url)
                logger.info("tunnel_stopped", public_url=self.public_url)
            except Exception as e:
                logger.error("tunnel_stop_failed", error=str(e))
            finally:
                self.tunnel = None
                self.public_url = None

    def get_url(self) -> Optional[str]:
        """
        Get the current public URL.
        """
        return self.public_url

# Singleton instance for easy access
_tunnel_manager: Optional[TunnelManager] = None

def get_tunnel_manager(port: int = 8000) -> TunnelManager:
    global _tunnel_manager
    if _tunnel_manager is None:
        _tunnel_manager = TunnelManager(port=port)
    return _tunnel_manager
