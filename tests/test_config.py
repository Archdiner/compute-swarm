"""
Tests for configuration management
"""

import pytest
import os
from src.config import MarketplaceConfig, SellerConfig, BuyerConfig


class TestConfigurationLoading:
    """Test configuration loading and validation"""

    def test_marketplace_config_defaults(self):
        """Test marketplace config loads with defaults"""
        config = MarketplaceConfig()

        assert config.marketplace_host == "0.0.0.0"
        assert config.marketplace_port == 8000
        assert config.network == "base-sepolia"
        assert config.x402_enabled is True

    def test_seller_config_defaults(self):
        """Test seller config loads with defaults"""
        config = SellerConfig()

        assert config.default_price_per_hour_mps == 0.50
        assert config.default_price_per_hour_cuda == 2.00
        assert config.max_concurrent_jobs == 1

    def test_buyer_config_defaults(self):
        """Test buyer config loads with defaults"""
        config = BuyerConfig()

        assert config.max_hourly_budget == 10.0
        assert config.auto_approve_threshold == 1.0

    def test_config_validates_private_key_format(self):
        """Test that private keys are validated and formatted"""
        # Without 0x prefix
        config = SellerConfig(seller_private_key="1234abcd")
        assert config.seller_private_key.startswith("0x")

        # With 0x prefix
        config = SellerConfig(seller_private_key="0x1234abcd")
        assert config.seller_private_key == "0x1234abcd"

    def test_config_environment_variables(self, monkeypatch):
        """Test that config loads from environment variables"""
        monkeypatch.setenv("MARKETPLACE_PORT", "9000")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        config = MarketplaceConfig()

        assert config.marketplace_port == 9000
        assert config.log_level == "DEBUG"
