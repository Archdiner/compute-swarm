# ComputeSwarm 🐝

**Decentralized P2P GPU Marketplace for the Agentic Economy**

ComputeSwarm is a peer-to-peer marketplace that enables individual laptop owners to monetize idle GPU compute. Built on the x402 protocol—a modern standard launched by Coinbase and Cloudflare in 2025—it enables native machine-to-machine payments over HTTP with per-second USDC settlement.

## 🎯 The Unfair Advantage

- **Per-Second Settlement**: Pay for exactly 42 seconds if you need 42 seconds. No subscriptions, no minimum spend.
- **Heterogeneous Support**: First-class support for both NVIDIA CUDA and Apple Silicon MPS, unlocking millions of M-series MacBooks.
- **Zero-Friction Access**: No API keys, no manual account setup. Just HTTP + x402 payment protocol.

## 🏗️ Architecture

```
┌─────────────────┐
│  Marketplace    │  ← Discovery Layer (FastAPI)
│  (FastAPI)      │     - x402.json manifest
│                 │     - Node registry
└────────┬────────┘     - Job tracking
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼───┐
│Seller│  │Buyer │
│Agent │  │ CLI  │
└──────┘  └──────┘
    │         │
    │    ┌────┴─────┐
    │    │  x402    │
    └───►│ Protocol │
         │  USDC    │
         └──────────┘
```

### Components

1. **Marketplace Server** (`src/marketplace/`)
   - FastAPI-based discovery layer
   - Tracks active GPU nodes
   - Exposes x402.json manifest
   - Manages job registry

2. **Seller Agent** (`src/seller/`)
   - Detects local GPU (CUDA/MPS)
   - Registers with marketplace
   - Executes compute jobs
   - Handles payment verification

3. **Buyer CLI** (`src/buyer/`)
   - Discovers available nodes
   - Submits compute jobs
   - Handles x402 payment flow
   - Monitors job status

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- PyTorch 2.1+ (with CUDA or MPS support)
- Base Sepolia testnet wallet with USDC

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/compute-swarm.git
cd compute-swarm

# Run setup script
./scripts/setup_dev.sh

# Activate virtual environment
source venv/bin/activate

# Configure environment
cp .env.example .env
# Edit .env with your wallet addresses
```

### Configuration

Edit `.env` with your settings:

```bash
# Wallet Configuration
SELLER_PRIVATE_KEY=your_seller_private_key
SELLER_ADDRESS=your_seller_address
BUYER_PRIVATE_KEY=your_buyer_private_key
BUYER_ADDRESS=your_buyer_address

# Network (Base Sepolia for testing)
NETWORK=base-sepolia
RPC_URL=https://sepolia.base.org
USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# Pricing (USD per hour)
DEFAULT_PRICE_PER_HOUR_MPS=0.50
DEFAULT_PRICE_PER_HOUR_CUDA=2.00
```

### Running the System

#### 1. Start the Marketplace

```bash
./scripts/start_marketplace.sh
```

The marketplace will be available at `http://localhost:8000`

Access the x402 manifest at: `http://localhost:8000/x402.json`

#### 2. Test GPU Detection

```bash
./scripts/test_gpu.sh
```

This will detect your GPU and run a simple test.

#### 3. Start a Seller Agent (on GPU machine)

```bash
./scripts/start_seller.sh
```

The seller will:
- Detect your GPU
- Register with the marketplace
- Send periodic heartbeats
- Wait for compute jobs

#### 4. Use the Buyer CLI

```bash
# Interactive mode
./scripts/start_buyer.sh

# Or command-line mode
./scripts/start_buyer.sh discover
```

Example interactive session:
```
> discover
# Shows table of available nodes

> submit
Node ID: node_abc123...
Path to Python script: examples/test_job.py
# Submits job and shows status
```

## 📁 Project Structure

```
compute-swarm/
├── src/
│   ├── marketplace/        # FastAPI marketplace server
│   │   ├── server.py       # Main server application
│   │   └── models.py       # Data models
│   ├── seller/             # Seller agent
│   │   └── agent.py        # Seller agent implementation
│   ├── buyer/              # Buyer client
│   │   └── cli.py          # CLI interface
│   ├── compute/            # Compute engine
│   │   └── gpu_detector.py # GPU detection
│   ├── payments/           # x402 payment logic (TODO)
│   └── config.py           # Configuration management
├── scripts/                # Helper scripts
│   ├── setup_dev.sh        # Development setup
│   ├── start_marketplace.sh
│   ├── start_seller.sh
│   ├── start_buyer.sh
│   └── test_gpu.sh
├── tests/                  # Test suite
├── docs/                   # Documentation
├── .env.example            # Environment template
├── requirements.txt        # Python dependencies
└── README.md
```

## 🛠️ Development Roadmap

### ✅ Phase 1: Core Protocol (Days 1-4) - IN PROGRESS

- [x] **Day 1**: Project foundation
  - [x] FastAPI marketplace server
  - [x] x402.json manifest
  - [x] GPU detection (CUDA/MPS)
  - [x] Seller/Buyer scaffolds
  - [x] Configuration system

- [ ] **Day 2**: MPS Seller Agent
  - [ ] Local job execution engine
  - [ ] Job isolation and security
  - [ ] Result streaming

- [ ] **Day 3**: x402 Payment Integration
  - [ ] Payment challenge generation
  - [ ] USDC payment verification
  - [ ] Per-second metering

- [ ] **Day 4**: Local Testing
  - [ ] End-to-end payment flow
  - [ ] Job execution on M4 MacBook

### Phase 2: Heterogeneous Expansion (Days 5-9)

- [ ] **Day 5**: Abstract Compute Engine
- [ ] **Day 6**: External NVIDIA GPU testing
- [ ] **Day 7**: Cross-network job submission
- [ ] **Day 8-9**: Job status streaming

### Phase 3: Demo Polish (Days 10-14)

- [ ] **Day 10**: React Dashboard
- [ ] **Day 11**: Performance Benchmarks
- [ ] **Day 12-13**: Pitch Preparation
- [ ] **Day 14**: Final Testing

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src tests/

# Test GPU detection
python -m src.compute.gpu_detector
```

## 📚 API Documentation

Once the marketplace is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- x402 Manifest: `http://localhost:8000/x402.json`

## 🔐 Security Considerations

**⚠️ This is a development preview. DO NOT use in production without:**

1. Proper wallet security (hardware wallets, key management)
2. Job sandboxing and resource limits
3. Rate limiting and DDoS protection
4. Smart contract audits
5. Network security (TLS, authentication)

## 📖 Learn More

- [x402 Protocol Specification](https://x402.org)
- [Coinbase Developer Platform](https://developers.coinbase.com)
- [Base Network Documentation](https://docs.base.org)

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- x402 Protocol: Coinbase & Cloudflare
- Base Network: Coinbase
- FastAPI Framework
- PyTorch Team

---

**Built for the Agentic Economy** 🤖💰

*ComputeSwarm enables AI agents to programmatically discover, pay for, and consume GPU compute without human intervention.*