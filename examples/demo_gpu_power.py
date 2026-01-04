"""
GPU Power Demo for ComputeSwarm
This script clearly demonstrates GPU acceleration vs CPU

Run this on ComputeSwarm to show:
1. GPU is detected and used
2. Massive speedup over CPU
3. Real compute happening
"""

import torch
import time

def main():
    print("=" * 60)
    print("  ComputeSwarm GPU Power Demo")
    print("=" * 60)
    print()
    
    # Detect device
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"GPU Detected: {gpu_name}")
        print(f"GPU Memory: {gpu_memory:.1f} GB")
        print(f"CUDA Version: {torch.version.cuda}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        print("GPU Detected: Apple Silicon (MPS)")
    else:
        device = torch.device("cpu")
        print("WARNING: No GPU detected, running on CPU")
    
    print(f"\nUsing device: {device}")
    print("-" * 60)
    
    # Matrix multiplication benchmark
    sizes = [1000, 2000, 4000]
    
    print("\n[1] MATRIX MULTIPLICATION BENCHMARK")
    print("    (This is what AI/ML models do millions of times)")
    print()
    
    for size in sizes:
        # Create random matrices
        a = torch.randn(size, size, device=device)
        b = torch.randn(size, size, device=device)
        
        # Warmup
        c = torch.matmul(a, b)
        if device.type == "cuda":
            torch.cuda.synchronize()
        
        # Benchmark
        start = time.perf_counter()
        iterations = 10
        for _ in range(iterations):
            c = torch.matmul(a, b)
        if device.type == "cuda":
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        
        # Calculate TFLOPS (2 * N^3 operations for matmul)
        ops = 2 * (size ** 3) * iterations
        tflops = ops / elapsed / 1e12
        
        print(f"    {size}x{size} matrices: {elapsed/iterations*1000:.2f}ms per op | {tflops:.2f} TFLOPS")
    
    # Neural network forward pass
    print("\n[2] NEURAL NETWORK INFERENCE")
    print("    (Simulating AI model prediction)")
    print()
    
    # Create a realistic-sized model
    model = torch.nn.Sequential(
        torch.nn.Linear(1024, 4096),
        torch.nn.ReLU(),
        torch.nn.Linear(4096, 4096),
        torch.nn.ReLU(),
        torch.nn.Linear(4096, 4096),
        torch.nn.ReLU(),
        torch.nn.Linear(4096, 1024),
    ).to(device)
    
    # Count parameters
    params = sum(p.numel() for p in model.parameters())
    print(f"    Model size: {params:,} parameters ({params * 4 / 1e6:.1f} MB)")
    
    # Benchmark inference
    batch_size = 64
    x = torch.randn(batch_size, 1024, device=device)
    
    # Warmup
    with torch.no_grad():
        y = model(x)
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # Time it
    start = time.perf_counter()
    iterations = 100
    with torch.no_grad():
        for _ in range(iterations):
            y = model(x)
    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    
    samples_per_sec = (batch_size * iterations) / elapsed
    print(f"    Batch size: {batch_size}")
    print(f"    Throughput: {samples_per_sec:.0f} samples/second")
    print(f"    Latency: {elapsed/iterations*1000:.2f}ms per batch")
    
    # Training simulation
    print("\n[3] TRAINING SIMULATION")
    print("    (What happens when you train an AI model)")
    print()
    
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    criterion = torch.nn.MSELoss()
    
    start = time.perf_counter()
    for epoch in range(5):
        epoch_start = time.perf_counter()
        
        for step in range(20):
            x = torch.randn(batch_size, 1024, device=device)
            target = torch.randn(batch_size, 1024, device=device)
            
            optimizer.zero_grad()
            output = model(x)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()
        
        if device.type == "cuda":
            torch.cuda.synchronize()
        epoch_time = time.perf_counter() - epoch_start
        
        print(f"    Epoch {epoch+1}/5: Loss={loss.item():.4f} | Time={epoch_time:.2f}s")
    
    total_time = time.perf_counter() - start
    
    print()
    print("=" * 60)
    print(f"  TOTAL COMPUTE TIME: {total_time:.2f} seconds")
    print(f"  DEVICE USED: {device}")
    if device.type == "cuda":
        print(f"  GPU: {gpu_name}")
        # Show memory usage
        allocated = torch.cuda.memory_allocated() / 1e9
        print(f"  GPU MEMORY USED: {allocated:.2f} GB")
    print("=" * 60)
    print()
    print("This compute was paid for with USDC via x402 protocol!")
    print()

if __name__ == "__main__":
    main()

