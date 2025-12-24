"""
Unit tests for GPU detection
"""

import pytest
from unittest.mock import Mock, patch

from src.compute.gpu_detector import GPUDetector
from src.marketplace.models import GPUType


class TestGPUDetection:
    """Test GPU detection functionality"""

    def test_detect_gpu_returns_valid_info(self):
        """Test that GPU detection returns valid GPUInfo"""
        detector = GPUDetector()
        gpu_info = detector.detect_gpu()

        assert gpu_info is not None
        assert isinstance(gpu_info.gpu_type, GPUType)
        assert gpu_info.device_name is not None
        assert gpu_info.vram_gb >= 0.0

    def test_get_torch_device_returns_valid_device(self):
        """Test that torch device string is valid"""
        device = GPUDetector.get_torch_device()
        assert device in ["cuda", "mps", "cpu"]

    @patch('torch.cuda.is_available')
    @patch('torch.cuda.get_device_name')
    @patch('torch.cuda.get_device_properties')
    def test_detect_cuda_when_available(self, mock_props, mock_name, mock_available):
        """Test CUDA detection when CUDA is available"""
        mock_available.return_value = True
        mock_name.return_value = "NVIDIA RTX 4090"

        mock_properties = Mock()
        mock_properties.total_memory = 24 * 1024**3  # 24 GB
        mock_props.return_value = mock_properties

        gpu_info = GPUDetector._detect_cuda()

        assert gpu_info is not None
        assert gpu_info.gpu_type == GPUType.CUDA
        assert gpu_info.device_name == "NVIDIA RTX 4090"
        assert gpu_info.vram_gb == 24.0

    @patch('platform.system')
    @patch('torch.backends.mps.is_available')
    def test_detect_mps_when_available(self, mock_mps_available, mock_system):
        """Test MPS detection when on macOS with MPS support"""
        mock_system.return_value = "Darwin"
        mock_mps_available.return_value = True

        gpu_info = GPUDetector._detect_mps()

        assert gpu_info is not None
        assert gpu_info.gpu_type == GPUType.MPS
        assert "Apple" in gpu_info.device_name
        assert gpu_info.vram_gb > 0

    @patch('platform.system')
    def test_detect_mps_returns_none_on_non_macos(self, mock_system):
        """Test MPS detection returns None on non-macOS systems"""
        mock_system.return_value = "Linux"

        gpu_info = GPUDetector._detect_mps()

        assert gpu_info is None

    def test_gpu_test_runs_without_error(self):
        """Test that GPU test runs without raising exceptions"""
        result = GPUDetector.test_gpu()
        assert isinstance(result, bool)

    @patch('torch.cuda.is_available')
    @patch('torch.randn')
    @patch('torch.matmul')
    def test_gpu_test_success(self, mock_matmul, mock_randn, mock_cuda):
        """Test GPU test returns True on successful computation"""
        mock_cuda.return_value = True

        # Mock tensor creation and matmul
        mock_tensor = Mock()
        mock_tensor.shape = (1000, 1000)
        mock_randn.return_value = mock_tensor
        mock_matmul.return_value = mock_tensor

        result = GPUDetector.test_gpu()
        assert result is True

    def test_detect_gpu_fallback_to_cpu(self):
        """Test that detect_gpu falls back to CPU when no GPU available"""
        with patch.object(GPUDetector, '_detect_cuda', return_value=None), \
             patch.object(GPUDetector, '_detect_mps', return_value=None), \
             patch.object(GPUDetector, '_detect_rocm', return_value=None):

            gpu_info = GPUDetector.detect_gpu()

            assert gpu_info.gpu_type == GPUType.UNKNOWN
            assert gpu_info.device_name == "CPU"
            assert gpu_info.vram_gb == 0.0
