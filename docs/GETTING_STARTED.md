# Getting Started with ComputeSwarm

This guide will walk you through setting up and running ComputeSwarm on your machine.

## Prerequisites

Before you begin, ensure you have:

1. **Python 3.10 or higher**
   ```bash
   python3 --version
   ```

2. **PyTorch 2.1+**
   - For NVIDIA GPUs: Install PyTorch with CUDA support
   - For Apple Silicon: PyTorch with MPS support (comes by default on macOS)
   - [PyTorch Installation Guide](https://pytorch.org/get-started/locally/)

3. **Base Sepolia Testnet Wallet**
   - Create a wallet using MetaMask or similar
   - Get testnet ETH from [Base Sepolia Faucet](https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet)
   - Get testnet USDC (contract: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`)

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/compute-swarm.git
cd compute-swarm
```

### 2. Run the Setup Script

```bash
./scripts/setup_dev.sh
```

This will:
- Create a Python virtual environment
- Install all dependencies
- Create a `.env` file from the template
- Make scripts executable

### 3. Configure Your Environment

Edit the `.env` file with your settings:

```bash
nano .env  # or use your preferred editor
```

**Required Configuration:**

```bash
# Seller Configuration (if running a seller agent)
SELLER_PRIVATE_KEY=0xyour_private_key_here
SELLER_ADDRESS=0xyour_address_here

# Buyer Configuration (if using the buyer CLI)
BUYER_PRIVATE_KEY=0xyour_private_key_here
BUYER_ADDRESS=0xyour_address_here

# Network Settings
NETWORK=base-sepolia
RPC_URL=https://sepolia.base.org
```

**⚠️ Security Warning:** Never commit your `.env` file or share your private keys!

### 4. Verify GPU Detection

Test that your GPU is detected correctly:

```bash
source venv/bin/activate
./scripts/test_gpu.sh
```

Expected output:
```
=== GPU Detection Test ===

GPU Type: mps  # or cuda
Device Name: Apple M4 Max  # or NVIDIA GPU name
VRAM: 64.0 GB

Torch Device: mps

=== Running GPU Test ===

Test Result: PASSED
```

## Running ComputeSwarm

### As a Marketplace Operator

Start the central marketplace server:

```bash
./scripts/start_marketplace.sh
```

The server will start on `http://localhost:8000`

**Verify it's running:**
```bash
curl http://localhost:8000/health
curl http://localhost:8000/x402.json
```

### As a GPU Seller

If you have a GPU and want to monetize it:

1. Ensure the marketplace is running (locally or point to a remote one)
2. Configure your seller wallet in `.env`
3. Start the seller agent:

```bash
./scripts/start_seller.sh
```

The agent will:
- Detect your GPU
- Register with the marketplace
- Send periodic heartbeats
- Wait for compute jobs

**Verify registration:**
```bash
curl http://localhost:8000/api/v1/nodes
```

### As a Compute Buyer

If you want to use GPU compute:

1. Configure your buyer wallet in `.env`
2. Ensure you have USDC in your wallet
3. Start the buyer CLI:

```bash
./scripts/start_buyer.sh
```

**Example Session:**

```
ComputeSwarm Buyer CLI
Commands: discover, submit, status, quit

> discover
GPU type filter (cuda/mps/all): all

┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Node ID               ┃ GPU Type ┃ Device         ┃ VRAM (GB) ┃ Price/hr (USD)  ┃ Status    ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ node_abc123...        │ MPS      │ Apple M4 Max   │      64.0 │           $0.50 │ available │
│ node_xyz789...        │ CUDA     │ NVIDIA RTX 4090│      24.0 │           $2.00 │ available │
└───────────────────────┴──────────┴────────────────┴───────────┴─────────────────┴───────────┘

> quit
```

## Testing the Full Flow

### 1. Start All Components

**Terminal 1 - Marketplace:**
```bash
./scripts/start_marketplace.sh
```

**Terminal 2 - Seller:**
```bash
./scripts/start_seller.sh
```

**Terminal 3 - Buyer:**
```bash
./scripts/start_buyer.sh
```

### 2. Create a Test Script

Create `test_job.py`:
```python
import torch

# Test GPU availability
device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
print(f"Using device: {device}")

# Simple computation
x = torch.randn(1000, 1000, device=device)
y = torch.randn(1000, 1000, device=device)
z = torch.matmul(x, y)

print(f"Computation complete. Result shape: {z.shape}")
print(f"Mean: {z.mean().item():.4f}")
```

### 3. Submit the Job

In the Buyer CLI:
```
> submit
Node ID: <copy node ID from discover>
Path to Python script: test_job.py
```

### 4. Monitor Job Status

```
> status
Job ID: <paste job ID>
```

## Troubleshooting

### GPU Not Detected

**For Apple Silicon:**
- Ensure you're on macOS 12.3+
- Verify PyTorch version: `python -c "import torch; print(torch.__version__)"`
- Check MPS availability: `python -c "import torch; print(torch.backends.mps.is_available())"`

**For NVIDIA GPUs:**
- Verify CUDA installation: `nvidia-smi`
- Check PyTorch CUDA: `python -c "import torch; print(torch.cuda.is_available())"`

### Marketplace Connection Failed

- Verify the marketplace is running: `curl http://localhost:8000/health`
- Check the `MARKETPLACE_URL` in your `.env`
- Ensure no firewall is blocking port 8000

### Payment Failed

- Verify you have USDC in your wallet
- Check you have enough ETH for gas fees
- Ensure you're on the correct network (Base Sepolia)
- Verify the USDC contract address in `.env`

### Port Already in Use

If port 8000 is taken:
```bash
# Change in .env
MARKETPLACE_PORT=8001
```

Then restart the marketplace.

## Next Steps

- Read the [Architecture Documentation](./ARCHITECTURE.md)
- Learn about [x402 Protocol Integration](./X402_INTEGRATION.md)
- Explore [Security Best Practices](./SECURITY.md)
- Check the [API Reference](http://localhost:8000/docs)

## Getting Help

- Check the [FAQ](./FAQ.md)
- Review existing [GitHub Issues](https://github.com/yourusername/compute-swarm/issues)
- Join our [Discord Community](#)

## Development Mode

For development with auto-reload:

```bash
# In .env
DEBUG=true
RELOAD=true
LOG_LEVEL=DEBUG
```

Then restart the marketplace:
```bash
./scripts/start_marketplace.sh
```
