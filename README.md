# ComputeSwarm

Decentralized P2P GPU marketplace using [x402 protocol](https://x402.org) for per-second USDC payments.

## Features

- **x402 Payments**: HTTP 402-based USDC micropayments on Base L2
- **Multi-GPU Support**: NVIDIA CUDA + Apple Silicon MPS
- **Per-Second Pricing**: Pay only for compute time used
- **Production-Ready**: Supabase, Upstash Redis, comprehensive tests
- **100% Free Tier**: All services available on free plans

## Architecture

**Marketplace** (FastAPI): Node discovery, x402 manifest, job registry
**Seller Agent** (Python): GPU detection, job execution, payment verification
**Buyer CLI** (Python): Node discovery, job submission, automated payments

**Tech Stack**: FastAPI, Supabase (PostgreSQL), Upstash Redis, x402 SDK, Web3.py, PyTorch

All services free tier compatible. See [FREE_TIER_SETUP.md](FREE_TIER_SETUP.md).

## Quick Start

```bash
# Setup
make install
cp .env.example .env  # Add your wallet keys

# Run tests
make test

# Start services
make run-marketplace  # Terminal 1
make run-seller       # Terminal 2
make run-buyer        # Terminal 3
```

## Development

```bash
make test              # Run all tests
make test-cov          # Run tests with coverage
make lint              # Run linters
make format            # Format code
make clean             # Clean build artifacts
```

## Configuration

Edit `.env`:

```bash
SELLER_PRIVATE_KEY=0x...
BUYER_PRIVATE_KEY=0x...
NETWORK=base-sepolia
```

## Project Structure

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

## Testing

See `pytest.ini` for configuration. Tests use Factory Boy for fixtures and pytest-asyncio for async support.

```bash
make test              # All tests
make test-unit         # Unit tests only
make test-cov          # With coverage report
```

## Deployment

```bash
docker-compose up      # Local with PostgreSQL + Redis
```

See `Dockerfile` and `docker-compose.yml` for production deployment.

## Documentation

- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Tech Stack**: [TECH_STACK.md](TECH_STACK.md)
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **x402 Integration**: [docs/X402_IMPLEMENTATION_REVIEW.md](docs/X402_IMPLEMENTATION_REVIEW.md)

## License

MIT