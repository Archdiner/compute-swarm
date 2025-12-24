"""
GPU Detection and Compute Engine
Detects available GPU hardware (CUDA, MPS, ROCm)
"""

import platform
import subprocess
from typing import Optional
import structlog

from src.marketplace.models import GPUType, GPUInfo

logger = structlog.get_logger()


class GPUDetector:
    """Detects and provides information about available GPU hardware"""

    @staticmethod
    def detect_gpu() -> GPUInfo:
        """
        Detect available GPU and return hardware information
        Priority: CUDA > MPS > ROCm > CPU
        """
        # Try CUDA first
        cuda_info = GPUDetector._detect_cuda()
        if cuda_info:
            return cuda_info

        # Try Apple Silicon MPS
        mps_info = GPUDetector._detect_mps()
        if mps_info:
            return mps_info

        # Try AMD ROCm (future support)
        rocm_info = GPUDetector._detect_rocm()
        if rocm_info:
            return rocm_info

        # Fallback to CPU
        logger.warning("no_gpu_detected", message="Falling back to CPU")
        return GPUInfo(
            gpu_type=GPUType.UNKNOWN,
            device_name="CPU",
            vram_gb=0.0
        )

    @staticmethod
    def _detect_cuda() -> Optional[GPUInfo]:
        """Detect NVIDIA CUDA GPU"""
        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                vram_bytes = torch.cuda.get_device_properties(0).total_memory
                vram_gb = vram_bytes / (1024 ** 3)

                # Get CUDA version
                cuda_version = torch.version.cuda

                # Get compute capability
                capability = torch.cuda.get_device_capability(0)
                compute_capability = f"{capability[0]}.{capability[1]}"

                # Try to get driver version
                driver_version = None
                try:
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        driver_version = result.stdout.strip()
                except Exception:
                    pass

                logger.info(
                    "cuda_detected",
                    device=device_name,
                    vram_gb=vram_gb,
                    cuda_version=cuda_version,
                    compute_capability=compute_capability
                )

                return GPUInfo(
                    gpu_type=GPUType.CUDA,
                    device_name=device_name,
                    vram_gb=round(vram_gb, 2),
                    compute_capability=compute_capability,
                    cuda_version=cuda_version,
                    driver_version=driver_version
                )
        except ImportError:
            logger.debug("torch_not_available", message="PyTorch not installed")
        except Exception as e:
            logger.warning("cuda_detection_failed", error=str(e))

        return None

    @staticmethod
    def _detect_mps() -> Optional[GPUInfo]:
        """Detect Apple Silicon MPS (Metal Performance Shaders)"""
        try:
            import torch

            # Check if running on macOS
            if platform.system() != "Darwin":
                return None

            # Check if MPS is available
            if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                # Get system info
                try:
                    # Run system_profiler to get detailed info
                    result = subprocess.run(
                        ["system_profiler", "SPHardwareDataType"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    chip_name = "Apple Silicon"
                    if result.returncode == 0:
                        for line in result.stdout.split("\n"):
                            if "Chip:" in line:
                                chip_name = line.split("Chip:")[1].strip()
                                break

                    # Get memory info
                    result = subprocess.run(
                        ["sysctl", "hw.memsize"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    total_memory_gb = 16.0  # Default
                    if result.returncode == 0:
                        memory_bytes = int(result.stdout.split(":")[1].strip())
                        total_memory_gb = memory_bytes / (1024 ** 3)

                    # MPS shares system memory; estimate 75% available for GPU
                    vram_gb = round(total_memory_gb * 0.75, 2)

                except Exception as e:
                    logger.warning("mps_sysinfo_failed", error=str(e))
                    chip_name = "Apple Silicon"
                    vram_gb = 16.0

                logger.info(
                    "mps_detected",
                    device=chip_name,
                    vram_gb=vram_gb
                )

                return GPUInfo(
                    gpu_type=GPUType.MPS,
                    device_name=chip_name,
                    vram_gb=vram_gb
                )

        except ImportError:
            logger.debug("torch_not_available", message="PyTorch not installed")
        except Exception as e:
            logger.warning("mps_detection_failed", error=str(e))

        return None

    @staticmethod
    def _detect_rocm() -> Optional[GPUInfo]:
        """Detect AMD ROCm GPU (future implementation)"""
        # TODO: Implement ROCm detection
        return None

    @staticmethod
    def get_torch_device() -> str:
        """
        Get the appropriate torch device string
        Returns: "cuda", "mps", or "cpu"
        """
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
            else:
                return "cpu"
        except ImportError:
            return "cpu"

    @staticmethod
    def test_gpu() -> bool:
        """
        Run a simple test to verify GPU is working
        Returns True if GPU compute works, False otherwise
        """
        try:
            import torch

            device = GPUDetector.get_torch_device()
            logger.info("testing_gpu", device=device)

            # Create a simple tensor operation
            x = torch.randn(1000, 1000, device=device)
            y = torch.randn(1000, 1000, device=device)
            z = torch.matmul(x, y)

            # Verify result
            assert z.shape == (1000, 1000)

            logger.info("gpu_test_passed", device=device)
            return True

        except Exception as e:
            logger.error("gpu_test_failed", error=str(e))
            return False


if __name__ == "__main__":
    """Test GPU detection"""
    import structlog
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.dev.ConsoleRenderer()
        ]
    )

    detector = GPUDetector()

    print("\n=== GPU Detection Test ===\n")

    gpu_info = detector.detect_gpu()
    print(f"GPU Type: {gpu_info.gpu_type}")
    print(f"Device Name: {gpu_info.device_name}")
    print(f"VRAM: {gpu_info.vram_gb} GB")

    if gpu_info.compute_capability:
        print(f"Compute Capability: {gpu_info.compute_capability}")
    if gpu_info.cuda_version:
        print(f"CUDA Version: {gpu_info.cuda_version}")
    if gpu_info.driver_version:
        print(f"Driver Version: {gpu_info.driver_version}")

    print(f"\nTorch Device: {detector.get_torch_device()}")

    print("\n=== Running GPU Test ===\n")
    test_result = detector.test_gpu()
    print(f"Test Result: {'PASSED' if test_result else 'FAILED'}")
