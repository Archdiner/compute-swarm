"""
Simple GPU test job for ComputeSwarm
Tests that GPU is accessible and performs basic matrix multiplication
"""

import torch
import time

def main():
    print("=" * 50)
    print("ComputeSwarm GPU Test Job")
    print("=" * 50)

    # Detect available device
    if torch.cuda.is_available():
        device = "cuda"
        device_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / (1024**3)
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
        device_name = "Apple Silicon MPS"
        vram = "Shared"
    else:
        device = "cpu"
        device_name = "CPU"
        vram = "N/A"

    print(f"\nDevice: {device}")
    print(f"Device Name: {device_name}")
    print(f"VRAM: {vram}")

    # Perform computation
    print("\nRunning matrix multiplication benchmark...")
    start_time = time.time()

    # Create random matrices
    size = 2000
    x = torch.randn(size, size, device=device)
    y = torch.randn(size, size, device=device)

    # Perform computation
    z = torch.matmul(x, y)

    # Ensure computation is complete (for CUDA)
    if device == "cuda":
        torch.cuda.synchronize()

    elapsed_time = time.time() - start_time

    print(f"✓ Matrix multiplication ({size}x{size}) completed in {elapsed_time:.4f} seconds")
    print(f"Result shape: {z.shape}")
    print(f"Result mean: {z.mean().item():.4f}")
    print(f"Result std: {z.std().item():.4f}")

    print("\n" + "=" * 50)
    print("Test completed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main()
