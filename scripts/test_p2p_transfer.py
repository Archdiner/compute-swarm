
import asyncio
import logging
import sys
import os
import requests
import threading
import time
from unittest.mock import MagicMock

# Create scripts directory if it doesn't exist
sys.path.append(os.getcwd())

from src.networking.tunnel import TunnelManager
from src.storage.transfer import start_file_server_background, FileServer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_p2p_transfer():
    print("Testing Swarm Transfer Protocol (File Server + Tunnel)...")
    
    storage_dir = "./temp_storage"
    os.makedirs(storage_dir, exist_ok=True)
    
    # 1. Create a dummy file
    test_file = "test_model.bin"
    with open(os.path.join(storage_dir, test_file), "w") as f:
        f.write("This is a test model file content.")
        
    # 2. Start File Server (background)
    port = 8005
    server = start_file_server_background(port=port, storage_dir=storage_dir)
    await asyncio.sleep(2) # Wait for startup
    
    # 3. Start Tunnel
    print("Starting tunnel...")
    manager = TunnelManager(port=port)
    
    # Mock ngrok
    import src.networking.tunnel
    src.networking.tunnel.ngrok = MagicMock()
    mock_tunnel = MagicMock()
    # In a real test we would access the local server, but here we just want to prove the logic flow.
    # We will "download" from localhost directly to verify the FileServer works, 
    # and separately verify the tunnel points to the right port.
    mock_tunnel.public_url = "http://mock-ngrok-transfer.ngrok.io"
    src.networking.tunnel.ngrok.connect.return_value = mock_tunnel
    
    public_url = await manager.start()
    print(f"Tunnel Public URL: {public_url}")
    
    # 4. Verify Download (from localhost since tunnel is mocked)
    print("Verifying download from local server...")
    try:
        response = requests.get(f"http://127.0.0.1:{port}/files/{test_file}")
        if response.status_code == 200 and response.text == "This is a test model file content.":
             print("SUCCESS: File downloaded correctly from FileServer.")
        else:
             print(f"FAILED: Status {response.status_code}, Content: {response.text}")
             
    except Exception as e:
        print(f"FAILED: Download exception: {e}")
        
    # 5. Cleanup
    manager.stop()
    server.stop()
    import shutil
    shutil.rmtree(storage_dir)
    print("Test Complete")

if __name__ == "__main__":
    asyncio.run(test_p2p_transfer())
