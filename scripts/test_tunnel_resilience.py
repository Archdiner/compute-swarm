
import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock

# Create scripts directory if it doesn't exist to ensure imports work if run from root
sys.path.append(os.getcwd())

from src.networking.tunnel import TunnelManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_resilience():
    print("Testing TunnelManager Resilience...")
    
    # 1. Initialize
    manager = TunnelManager(port=8000)
    
    # Mock ngrok for testing
    import src.networking.tunnel
    src.networking.tunnel.ngrok = MagicMock()
    
    mock_tunnel = MagicMock()
    mock_tunnel.public_url = "http://initial-url.ngrok.io"
    src.networking.tunnel.ngrok.connect.return_value = mock_tunnel

    # 2. Start
    print("Starting tunnel...")
    await manager.start()
    print(f"Initial URL: {manager.get_url()}")
    
    # 3. Trigger Reconnect
    print("Simulating failure and reconnect...")
    # Manually trigger reconnect for test speed (instead of waiting for monitor)
    # But let's test the reconnect logic specifically
    await manager._reconnect()
    
    # Verify connect was called again
    print(f"Reconnect called. Check logs for 'tunnel_reconnected'")
    
    # 4. Stop
    manager.stop()
    print("Test Complete")

if __name__ == "__main__":
    asyncio.run(test_resilience())
