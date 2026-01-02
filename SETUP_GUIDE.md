# Complete Setup Guide

This guide walks you through everything you need to get ComputeSwarm up and running, including all accounts, keys, and dependencies.

## Prerequisites

### 1. Software to Download/Install

- **Python 3.8-3.12** (recommended) or **Python 3.13+** - Check with `python3 --version`
  - Download from [python.org](https://www.python.org/downloads/) if needed
  - **Note**: Python 3.13+ requires PyTorch 2.6.0+ (automatically handled in requirements.txt)
- **Git** - For cloning the repository (if not already installed)
- **Web3 Wallet** (optional but recommended) - MetaMask or similar for managing testnet wallets

### 2. System Requirements

- **For GPU Support**:
  - **NVIDIA GPU**: CUDA-compatible GPU with CUDA drivers installed
  - **Apple Silicon**: M1/M2/M3 Mac (MPS support)
  - **CPU-only**: Works but slower (no GPU acceleration)

## Step-by-Step Setup

### Step 1: Clone and Navigate to Project

```bash
cd /Users/asadr/compute-swarm
```

### Step 2: Create Accounts and Get API Keys

#### A. Supabase Account (Database) - **REQUIRED**

1. Go to [https://supabase.com](https://supabase.com)
2. Click "Start your project" and sign up with GitHub
3. Create a new project:
   - Organization: Create new
   - Name: `computeswarm` (or your choice)
   - Database Password: Generate a strong password (SAVE THIS!)
   - Region: Choose closest to you
   - Pricing Plan: **Free**
4. Wait ~2 minutes for project initialization
5. Get credentials:
   - Go to **Project Settings > API**
   - Copy:
     - `SUPABASE_URL` (e.g., `https://xxxxx.supabase.co`)
     - `SUPABASE_ANON_KEY` (starts with `eyJhb...`)
     - `SUPABASE_SERVICE_KEY` (optional, for admin operations)
   - Go to **Project Settings > Database**
   - Copy connection string:
     - `DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres`
6. Set up database schema:
   - Go to **SQL Editor** in Supabase dashboard
   - Copy and paste the entire contents of `src/database/schema.sql`
   - Click "Run" to execute

**Free Tier Limits:**
- ✅ 500MB database storage
- ✅ 2GB bandwidth/month
- ✅ Unlimited API requests

#### B. Upstash Redis Account (Caching) - **OPTIONAL for MVP**

**Note**: Redis is not currently used in the codebase. The app works entirely with Supabase (PostgreSQL). You can skip this step for MVP.

If you want to set it up for future use:
1. Go to [https://upstash.com](https://upstash.com)
2. Sign up with GitHub
3. Click "Create Database"
   - Name: `computeswarm-cache`
   - Type: **Regional** (faster, free tier)
   - Region: Choose closest to you
   - TLS: Enabled
4. Copy credentials from dashboard:
   - `UPSTASH_REDIS_REST_URL` (e.g., `https://xxxxx.upstash.io`)
   - `UPSTASH_REDIS_REST_TOKEN` (starts with `AXX...`)

**Free Tier Limits:**
- ✅ 10,000 commands/day
- ✅ 256MB storage
- ⚠️ Resets daily (not persistent beyond 24hrs)

#### C. Base Sepolia Testnet Setup (Blockchain) - **REQUIRED**

1. **Get Testnet ETH (for gas fees)**:
   - Go to [Coinbase Base Sepolia Faucet](https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet)
   - Connect your wallet (MetaMask recommended)
   - Request testnet ETH (0.1 ETH/day limit)
   - Make sure your wallet is connected to Base Sepolia network

2. **Get Testnet USDC**:
   - USDC Contract Address: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
   - You can use a faucet or bridge from Sepolia ETH to Base Sepolia
   - Alternative: Use [Base Sepolia Faucet](https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet)

3. **Create Wallet Addresses** (if you don't have them):
   - Use MetaMask or any Web3 wallet
   - Create two separate wallets (or use one for both):
     - **Seller wallet**: For receiving payments
     - **Buyer wallet**: For making payments
   - Export private keys (keep these SECURE):
     - In MetaMask: Account → Account Details → Show Private Key
     - Format: `0x...` (64 hex characters)

**Network Configuration:**
- Network: `base-sepolia`
- RPC URL: `https://sepolia.base.org`
- USDC Contract: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`

### Step 3: Install Dependencies

```bash
# Option 1: Use the setup script (recommended)
./scripts/setup_dev.sh

# Option 2: Manual setup
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development/testing
```

### Step 4: Create Environment File

Create a `.env` file in the project root:

```bash
# Copy template if it exists, or create new
touch .env
```

Add the following to `.env`:

```bash
# ===== DATABASE (Supabase) =====
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhb...
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres

# ===== CACHING (Upstash Redis) - OPTIONAL =====
# Redis is not currently used in the codebase - you can skip these for MVP
# UPSTASH_REDIS_REST_URL=https://xxxxx.upstash.io
# UPSTASH_REDIS_REST_TOKEN=AXX...

# ===== BLOCKCHAIN (Base Sepolia) =====
NETWORK=base-sepolia
RPC_URL=https://sepolia.base.org
USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# ===== WALLETS =====
# Seller wallet (for receiving payments)
SELLER_PRIVATE_KEY=0x...
SELLER_ADDRESS=0x...  # Optional, auto-derived from private key

# Buyer wallet (for making payments)
BUYER_PRIVATE_KEY=0x...
BUYER_ADDRESS=0x...  # Optional, auto-derived from private key

# ===== MARKETPLACE SERVER =====
MARKETPLACE_HOST=0.0.0.0
MARKETPLACE_PORT=8000

# ===== OPTIONAL =====
# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Development
DEBUG=false
RELOAD=false
```

**⚠️ SECURITY WARNING**: Never commit `.env` to git! It contains private keys.

### Step 5: Verify GPU Detection (Optional but Recommended)

```bash
# Activate virtual environment first
source venv/bin/activate

# Test GPU detection
./scripts/test_gpu.sh

# Or manually
python -c "from src.compute.gpu_detector import detect_gpu; print(detect_gpu())"
```

Expected output:
- NVIDIA: `{'type': 'CUDA', 'device_name': 'NVIDIA GeForce RTX...', ...}`
- Apple Silicon: `{'type': 'MPS', 'device_name': 'Apple M1/M2/M3', ...}`
- CPU-only: `{'type': 'CPU', ...}`

### Step 6: Run Tests

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Run all tests
make test

# Or with pytest directly
pytest

# Run with coverage
make test-cov

# Run specific test file
pytest tests/test_marketplace.py
```

**Note**: Some tests may require the database to be set up. If tests fail, ensure:
1. Supabase credentials are correct in `.env`
2. Database schema has been created (Step 2A.6)

### Step 7: Start the Services

You'll need **3 separate terminal windows**:

#### Terminal 1: Marketplace Server
```bash
source venv/bin/activate
make run-marketplace
# Or: ./scripts/start_marketplace.sh
```

Server should start at `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

#### Terminal 2: Seller Agent
```bash
source venv/bin/activate
make run-seller
# Or: ./scripts/start_seller.sh
```

This will:
- Detect your GPU
- Register with the marketplace
- Poll for available jobs
- Execute jobs when claimed

#### Terminal 3: Buyer CLI
```bash
source venv/bin/activate
make run-buyer
# Or: ./scripts/start_buyer.sh
```

Interactive CLI for:
- Submitting jobs
- Checking job status
- Viewing marketplace stats

## Quick Reference: All Required Credentials

| Service | What You Need | Where to Get It |
|---------|---------------|-----------------|
| **Supabase** | `SUPABASE_URL`<br>`SUPABASE_ANON_KEY`<br>`DATABASE_URL` | [supabase.com](https://supabase.com) → Project Settings → API & Database |
| **Upstash** (Optional) | `UPSTASH_REDIS_REST_URL`<br>`UPSTASH_REDIS_REST_TOKEN` | [upstash.com](https://upstash.com) → Dashboard<br>**Not needed for MVP** |
| **Base Sepolia** | `SELLER_PRIVATE_KEY`<br>`BUYER_PRIVATE_KEY`<br>Testnet ETH & USDC | MetaMask + [Coinbase Faucet](https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet) |

## Troubleshooting

### Tests Fail with Database Errors
- Verify Supabase credentials in `.env`
- Ensure database schema is created (run `src/database/schema.sql` in Supabase SQL Editor)
- Check network connectivity to Supabase

### GPU Not Detected
- **NVIDIA**: Install CUDA drivers and toolkit
- **Apple Silicon**: PyTorch should auto-detect MPS
- **CPU-only**: System will fall back to CPU (slower but works)

### Wallet/Blockchain Errors
- Ensure you have testnet ETH for gas fees
- Verify wallet addresses are correct
- Check that private keys start with `0x`
- Ensure you're on Base Sepolia network

### PyTorch Installation Errors (Python 3.13+)
- **Error**: `Could not find a version that satisfies the requirement torch==2.1.2`
- **Solution**: The requirements.txt has been updated to use `torch>=2.6.0` which supports Python 3.13+
- If you still have issues, try: `pip install torch torchvision --upgrade`

### Import Errors
- Make sure virtual environment is activated: `source venv/bin/activate`
- Reinstall dependencies: `pip install -r requirements.txt`

## Next Steps

Once everything is running:

1. **Test the system**:
   ```bash
   # In buyer CLI
   > stats              # View marketplace
   > submit             # Submit a test job
   ```

2. **Check API documentation**: Visit `http://localhost:8000/docs`

3. **Read the docs**:
   - [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design
   - [QUEUE_SYSTEM.md](QUEUE_SYSTEM.md) - Queue implementation
   - [TECH_STACK.md](TECH_STACK.md) - Technology choices

## Summary Checklist

- [ ] Python 3.8+ installed
- [ ] Supabase account created and project set up
- [ ] Database schema created in Supabase
- [ ] ~~Upstash Redis account created~~ (Optional - not needed for MVP)
- [ ] Base Sepolia testnet wallets created
- [ ] Testnet ETH obtained (for gas)
- [ ] Testnet USDC obtained (for payments)
- [ ] Private keys exported from wallets
- [ ] Dependencies installed (`make install`)
- [ ] `.env` file created with all credentials
- [ ] GPU detection tested (optional)
- [ ] Tests passing (`make test`)
- [ ] Marketplace server running
- [ ] Seller agent running
- [ ] Buyer CLI working

**Total Setup Time**: ~30-45 minutes (mostly waiting for account creation and database setup)

**Total Cost**: $0/month (all free tiers)

