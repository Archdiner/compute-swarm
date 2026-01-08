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
            logger.error("tunnel_start_failed", error=str(e))
            raise

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
                
                if not self.tunnel:
                    continue
                    
                # specific check for ngrok tunnel health could go here
                # For now, we rely on the fact that if the process dies, pyngrok might not tell us immediately
                # but we can try to hit the local inspection API or check pyngrok state
                
                # Simple check: is the tunnel object still valid?
                # In a real scenario, we might want to curl the public URL or check ngrok API
                
                pass 

            except Exception as e:
                logger.error("tunnel_monitor_error", error=str(e))
                # If critical error, try reconnect
                await self._reconnect()

    async def _reconnect(self):
        """Attempt to reconnect the tunnel"""
        logger.info("tunnel_reconnecting")
        self.stop()
        await asyncio.sleep(5) # Wait before reconnecting
        try:
            self._connect()
            logger.info("tunnel_reconnected", new_url=self.public_url)
        except Exception as e:
            logger.error("tunnel_reconnect_failed", error=str(e))

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
