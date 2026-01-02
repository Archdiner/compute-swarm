# ComputeSwarm

**Queue-based P2P GPU marketplace** using [x402 protocol](https://x402.org) for per-second USDC payments.

## Features

- **Queue-Based Architecture**: Fault-tolerant job queue with atomic claiming
- **x402 Payments**: HTTP 402-based USDC micropayments on Base L2
- **Multi-GPU Support**: NVIDIA CUDA + Apple Silicon MPS
- **Job Execution Engine**: Isolated Python script execution with safety controls
- **Production Database**: Supabase PostgreSQL with real-time updates
- **100% Free Tier**: All services available on free plans

## Architecture

**Queue-Based Job System**: Buyers submit to queue, sellers poll and claim jobs atomically. No direct node assignment needed. See [QUEUE_SYSTEM.md](QUEUE_SYSTEM.md) for details.

**Marketplace** (FastAPI): Job queue management, statistics, maintenance tasks
**Seller Agent** (Python): GPU detection, queue polling, job execution, result reporting
**Buyer CLI** (Python): Job submission, status monitoring, cancellation

**Tech Stack**: FastAPI, Supabase (PostgreSQL), x402 SDK, Web3.py, PyTorch

All services free tier compatible. See [FREE_TIER_SETUP.md](FREE_TIER_SETUP.md).

## 🚀 Getting Started

**New to the project?** See [SETUP_GUIDE.md](SETUP_GUIDE.md) for complete step-by-step instructions including:
- All accounts you need to create (Supabase, Upstash, Base Sepolia)
- API keys and credentials to obtain
- Software to download
- Complete setup walkthrough

## Quick Start

```bash
# 1. Setup database
# Create Supabase project at https://app.supabase.com
# Run src/database/schema.sql in SQL Editor
# Copy URL and anon key

# 2. Install dependencies
make install
cp .env.example .env

# 3. Configure environment
# Edit .env with:
#   - SUPABASE_URL and SUPABASE_ANON_KEY
#   - SELLER_PRIVATE_KEY and BUYER_PRIVATE_KEY

# 4. Run tests
make test

# 5. Start services
make run-marketplace  # Terminal 1
make run-seller       # Terminal 2
make run-buyer        # Terminal 3 (interactive CLI)
```

### Example Usage

```bash
# In buyer CLI
> stats              # View marketplace statistics
> submit             # Submit job to queue
  Path: examples/hello.py
  Max price: 2.0
  GPU: cuda

✓ Job submitted (ID: abc-123)

> status abc-123     # Check job status
Status: COMPLETED
Output: Hello from GPU!
Cost: $0.0012
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