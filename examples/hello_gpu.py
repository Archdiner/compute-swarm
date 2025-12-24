"""
Simple GPU test script for ComputeSwarm
Tests GPU availability and prints device info
"""

import torch
import platform

def main():
    print("ComputeSwarm GPU Test")
    print("=" * 50)

    # System info
    print(f"\nPlatform: {platform.system()} {platform.machine()}")
    print(f"Python: {platform.python_version()}")
    print(f"PyTorch: {torch.__version__}")

    # CUDA check
    if torch.cuda.is_available():
        print(f"\n✓ CUDA Available")
        print(f"CUDA Version: {torch.version.cuda}")
        print(f"Device Count: {torch.cuda.device_count()}")
        print(f"Device Name: {torch.cuda.get_device_name(0)}")
        print(f"Device Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.2f} GB")

        # Simple CUDA operation
        x = torch.randn(1000, 1000, device='cuda')
        y = torch.randn(1000, 1000, device='cuda')
        z = torch.matmul(x, y)
        print(f"\nCUDA matmul test: {z.shape} tensor computed successfully")

    # MPS check (Apple Silicon)
    elif torch.backends.mps.is_available():
        print(f"\n✓ MPS (Apple Silicon) Available")

        # Simple MPS operation
        x = torch.randn(1000, 1000, device='mps')
        y = torch.randn(1000, 1000, device='mps')
        z = torch.matmul(x, y)
        print(f"MPS matmul test: {z.shape} tensor computed successfully")

    else:
        print(f"\n⚠ No GPU available, using CPU")
        x = torch.randn(1000, 1000)
        y = torch.randn(1000, 1000)
        z = torch.matmul(x, y)
        print(f"CPU matmul test: {z.shape} tensor computed successfully")

    print("\n✓ Job completed successfully!")

if __name__ == "__main__":
    main()
