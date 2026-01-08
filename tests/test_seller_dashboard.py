
import asyncio
import os
from fastapi.testclient import TestClient
from src.seller.agent import SellerAgent
from pathlib import Path
from unittest.mock import MagicMock, patch

# Mock GPU Detector to avoid real hardware checks
@patch('src.seller.agent.GPUDetector')
@patch('src.seller.agent.get_seller_config')
def test_dashboard_api(mock_config, mock_gpu):
    # Setup Mocks
    mock_gpu.detect_gpu.return_value = MagicMock(
        gpu_type=MagicMock(value="cuda"),
        device_name="Test GPU",
        vram_gb=24.0,
        num_gpus=1
    )
    mock_gpu.test_gpu.return_value = True
    
    mock_config.return_value = MagicMock(
        seller_private_key="0x123",
        seller_address="0xABC",
        default_price_per_hour_cuda=2.0
    )

    # Initialize Agent (partial)
    agent = SellerAgent()
    # Manually populate fields usually set in initialize()
    agent.gpu_info = mock_gpu.detect_gpu.return_value
    agent.price_per_hour = 2.0
    agent.session_start_time = None
    
    client = TestClient(agent.app)

    # Test Status Endpoint
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert "running" in data
    assert data["gpu"]["name"] == "Test GPU"
    
    # Test Control Endpoints
    response = client.post("/api/control/start")
    assert response.status_code == 200
    assert agent.agent_loop_running == True
    
    response = client.post("/api/control/stop")
    assert response.status_code == 200
    assert agent.agent_loop_running == False

def test_wallet_generation():
    # Test One-Click Start
    with patch('src.seller.agent.get_seller_config') as mock_config_getter:
        # Mock config with NO key
        mock_conf = MagicMock()
        mock_conf.seller_private_key = ""
        mock_conf.seller_address = ""
        mock_config_getter.return_value = mock_conf
        
        # Mock Path.exists to return False (simulate new user)
        with patch('pathlib.Path.exists', return_value=False):
            agent = SellerAgent()
            
            # Mock file operations
            with patch('builtins.open', new_callable=MagicMock) as mock_open:
                with patch('eth_account.Account.create') as mock_account:
                    mock_account.return_value.key.hex.return_value = "0xNEWKEY"
                    mock_account.return_value.address = "0xNEWADDR"
                    
                    agent.check_or_create_wallet()
                    
                    # Check if it tried to write to file with 'w' (create)
                    mock_open.assert_called_with(Path(".env.local"), "w")
                    assert agent.config.seller_private_key == "0xNEWKEY"
                    assert agent.config.seller_address == "0xNEWADDR"
                    assert agent.generated_wallet == True

if __name__ == "__main__":
    test_dashboard_api()
    test_wallet_generation()
    print("All tests passed!")
