"""
Quick GPU Benchmark for Demo
Shows GPU power in 30 seconds

Perfect for live demos - fast and impressive output
"""

import torch
import time
import sys

def progress_bar(current, total, width=40):
    """Simple progress bar"""
    filled = int(width * current / total)
    bar = "=" * filled + "-" * (width - filled)
    percent = current / total * 100
    return f"[{bar}] {percent:.0f}%"

def main():
    print()
    print("+" + "=" * 58 + "+")
    print("|" + " " * 15 + "COMPUTESWARM GPU BENCHMARK" + " " * 17 + "|")
    print("+" + "=" * 58 + "+")
    print()
    
    # Detect GPU
    if torch.cuda.is_available():
        device = torch.device("cuda")
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1e9
        print(f"  GPU:  {gpu_name}")
        print(f"  VRAM: {vram:.1f} GB")
        print(f"  CUDA: {torch.version.cuda}")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = torch.device("mps")
        gpu_name = "Apple Silicon"
        print(f"  GPU:  Apple Silicon (MPS)")
    else:
        device = torch.device("cpu")
        gpu_name = "CPU"
        print(f"  Device: CPU (no GPU detected)")
    
    print()
    print("-" * 60)
    print()
    
    # Benchmark 1: Matrix operations
    print("  [1/3] Matrix Multiplication...")
    sys.stdout.flush()
    
    size = 4096
    a = torch.randn(size, size, device=device)
    b = torch.randn(size, size, device=device)
    
    # Warmup
    c = torch.matmul(a, b)
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # Benchmark
    start = time.perf_counter()
    for i in range(10):
        c = torch.matmul(a, b)
        if device.type == "cuda":
            torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    
    tflops = (2 * size**3 * 10) / elapsed / 1e12
    print(f"        {size}x{size} @ {tflops:.1f} TFLOPS")
    
    # Benchmark 2: Neural network
    print("  [2/3] Neural Network Forward Pass...")
    sys.stdout.flush()
    
    model = torch.nn.Sequential(
        torch.nn.Linear(1024, 2048),
        torch.nn.ReLU(),
        torch.nn.Linear(2048, 2048),
        torch.nn.ReLU(),
        torch.nn.Linear(2048, 1024),
    ).to(device)
    
    x = torch.randn(256, 1024, device=device)
    
    # Warmup
    with torch.no_grad():
        y = model(x)
    if device.type == "cuda":
        torch.cuda.synchronize()
    
    # Benchmark
    start = time.perf_counter()
    with torch.no_grad():
        for _ in range(100):
            y = model(x)
    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    
    throughput = (256 * 100) / elapsed
    print(f"        {throughput:.0f} samples/second")
    
    # Benchmark 3: Training step
    print("  [3/3] Training Iteration...")
    sys.stdout.flush()
    
    optimizer = torch.optim.Adam(model.parameters())
    criterion = torch.nn.MSELoss()
    
    start = time.perf_counter()
    for _ in range(50):
        x = torch.randn(128, 1024, device=device)
        target = torch.randn(128, 1024, device=device)
        
        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, target)
        loss.backward()
        optimizer.step()
    
    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start
    
    steps_per_sec = 50 / elapsed
    print(f"        {steps_per_sec:.0f} training steps/second")
    
    # Summary
    print()
    print("-" * 60)
    print()
    
    # Calculate a "score"
    score = int(tflops * 100 + throughput / 10 + steps_per_sec * 10)
    
    print(f"  BENCHMARK SCORE: {score:,}")
    print()
    
    # Visual bar
    max_score = 5000
    bar_width = 40
    filled = min(int(bar_width * score / max_score), bar_width)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"  [{bar}]")
    print()
    
    if score > 2000:
        rating = "EXCELLENT - High-performance GPU"
    elif score > 1000:
        rating = "GOOD - Capable GPU"
    elif score > 500:
        rating = "FAIR - Entry-level GPU"
    else:
        rating = "LOW - Consider using GPU"
    
    print(f"  Rating: {rating}")
    print()
    
    print("+" + "=" * 58 + "+")
    print("|" + " " * 18 + "BENCHMARK COMPLETE" + " " * 20 + "|")
    print("+" + "=" * 58 + "+")
    print()
    print("  This benchmark ran on ComputeSwarm")
    print("  Payment processed via x402 protocol (USDC on Base)")
    print()

if __name__ == "__main__":
    main()

