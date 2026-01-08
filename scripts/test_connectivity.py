
import asyncio
import logging
import sys
import os

# Create scripts directory if it doesn't exist to ensure imports work if run from root
sys.path.append(os.getcwd())

from src.networking.tunnel import TunnelManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_tunnel_manager():
    print("Testing TunnelManager...")
    
    # 1. Initialize
    manager = TunnelManager(port=8000)
    
    # Mock ngrok.connect for CI/no-token environment
    if not os.getenv("NGROK_AUTH_TOKEN"):
        print("No NGROK_AUTH_TOKEN found, mocking ngrok for testing check...")
        from unittest.mock import MagicMock
        manager.tunnel = MagicMock()
        manager.tunnel.public_url = "http://mock-ngrok-url.ngrok.io"
        # We need to monkeypatch the manager's start method or the ngrok module
        # Let's monkeypatch the ngrok module used by the manager
        import src.networking.tunnel
        src.networking.tunnel.ngrok = MagicMock()
        src.networking.tunnel.ngrok.connect.return_value = manager.tunnel

    # 2. Start Tunnel
    try:
        print("Starting tunnel...")
        url = manager.start()
        print(f"Tunnel started successfully at: {url}")
        
        if not url:
            print("FAILED: No URL returned")
            return
            
        if "ngrok" not in url:
             print(f"WARNING: URL {url} does not look like an ngrok URL (might be expected if using custom domain)")

    except Exception as e:
        print(f"FAILED to start tunnel: {e}")
        return

    # 3. Simulate functionality
    await asyncio.sleep(2)
    
    # 4. Stop Tunnel
    print("Stopping tunnel...")
    manager.stop()
    print("Tunnel stopped.")
    
    if manager.get_url() is not None:
        print("FAILED: URL should be None after stop")
    else:
        print("SUCCESS: TunnelManager test passed")

if __name__ == "__main__":
    asyncio.run(test_tunnel_manager())
