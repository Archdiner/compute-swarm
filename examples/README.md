# ComputeSwarm Example Jobs

This directory contains example compute jobs that can be submitted to ComputeSwarm.

## Available Examples

### 1. GPU Test (`test_gpu.py`)

Simple GPU test that verifies hardware is accessible and performs basic matrix multiplication.

**Usage:**
```bash
./scripts/start_buyer.sh

> submit
Node ID: node_abc123...
Path to Python script: examples/test_gpu.py
```

**Expected Output:**
```
Device: mps
Device Name: Apple Silicon MPS
VRAM: Shared

Running matrix multiplication benchmark...
✓ Matrix multiplication (2000x2000) completed in 0.1234 seconds
Result shape: torch.Size([2000, 2000])
Result mean: -0.0012
Result std: 44.7213

Test completed successfully!
```

**Duration:** ~1-5 seconds
**Cost:** ~$0.0001 - $0.0014 USD

---

### 2. MNIST Training (`mnist_train.py`)

Demonstrates a realistic machine learning training job using a simple CNN on synthetic MNIST-like data.

**Features:**
- CNN with 2 conv layers + 2 FC layers
- Trains for 3 epochs
- Uses synthetic data (no download required)
- Reports loss and accuracy

**Usage:**
```bash
./scripts/start_buyer.sh

> submit
Node ID: node_xyz789...
Path to Python script: examples/mnist_train.py
```

**Expected Output:**
```
Training on device: cuda

Training for 3 epochs...
Epoch [1/3], Batch [0/50], Loss: 2.3456
...
Epoch [1/3] Complete:
  Average Loss: 2.1234
  Accuracy: 12.50%
...
Training completed successfully!
```

**Duration:** ~30-60 seconds
**Cost:** ~$0.01 - $0.03 USD (depending on GPU type)

---

## Creating Your Own Jobs

### Job Requirements

1. **Pure Python**: Job must be a Python script
2. **Self-contained**: All logic in one file (or use `requirements` field)
3. **PyTorch Compatible**: Use PyTorch for GPU access
4. **Output to stdout**: Use `print()` for results

### Device Detection Template

```python
import torch

# Detect device
if torch.cuda.is_available():
    device = "cuda"
elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
    device = "mps"
else:
    device = "cpu"

print(f"Using device: {device}")

# Your computation here
x = torch.randn(1000, 1000, device=device)
```

### Best Practices

1. **Report Progress**: Print status updates for long jobs
2. **Handle Errors**: Wrap main logic in try/except
3. **Time Limits**: Keep jobs under 1 hour (default timeout)
4. **Memory Management**: Monitor VRAM usage
5. **Reproducibility**: Set random seeds if needed

### Example: Custom Job

```python
import torch
import time

def main():
    device = "cuda" if torch.cuda.is_available() else "mps" if hasattr(torch.backends, "mps") and torch.backends.mps.is_available() else "cpu"

    print(f"Starting computation on {device}...")

    # Your custom computation
    result = your_computation(device)

    print(f"Computation complete!")
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
```

## Submitting Jobs with Dependencies

If your job requires additional packages:

```python
# In your job script
# REQUIREMENTS: transformers==4.30.0 numpy==1.24.0

import transformers
import numpy as np

# ... your code
```

Then submit with:
```bash
> submit
Node ID: node_abc123...
Path to Python script: your_job.py
Additional requirements: transformers==4.30.0 numpy==1.24.0
```

## Cost Estimation

Estimate job cost before submitting:

```
Cost = (Duration in seconds / 3600) × Price per hour

Examples:
- 30 second job on $0.50/hr GPU: (30 / 3600) × 0.50 = $0.0042
- 5 minute job on $2.00/hr GPU: (300 / 3600) × 2.00 = $0.1667
```

## Job Limits

Current limits (Phase 1):
- Max duration: 1 hour
- Max memory: Based on GPU VRAM
- No network access (future: sandboxed)
- No file I/O (future: temporary storage)

## Troubleshooting

**Job fails immediately:**
- Check for syntax errors: `python your_job.py`
- Verify imports are available
- Test locally first

**Out of memory:**
- Reduce batch size
- Use gradient checkpointing
- Choose GPU with more VRAM

**Timeout:**
- Optimize computation
- Reduce number of iterations
- Split into smaller jobs

## More Examples Coming

Future examples:
- Stable Diffusion image generation
- LLM fine-tuning
- Video processing
- Scientific computing (protein folding, etc.)

## Contributing Examples

Have a cool example job? Submit a PR!

1. Create your job script
2. Test it locally and on ComputeSwarm
3. Document requirements and expected output
4. Add to this directory
