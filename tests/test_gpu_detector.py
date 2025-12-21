"""
Tests for GPU detection module
"""

import pytest
from src.compute.gpu_detector import GPUDetector
from src.marketplace.models import GPUType


class TestGPUDetector:
    """Test suite for GPU detection"""

    def test_detect_gpu(self):
        """Test that GPU detection returns valid GPUInfo"""
        detector = GPUDetector()
        gpu_info = detector.detect_gpu()

        assert gpu_info is not None
        assert isinstance(gpu_info.gpu_type, GPUType)
        assert gpu_info.device_name is not None
        assert gpu_info.vram_gb >= 0.0

    def test_get_torch_device(self):
        """Test that torch device string is valid"""
        device = GPUDetector.get_torch_device()

        assert device in ["cuda", "mps", "cpu"]

    def test_gpu_test(self):
        """Test that GPU test runs without error"""
        # This should not raise an exception
        result = GPUDetector.test_gpu()

        assert isinstance(result, bool)
