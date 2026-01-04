# Deployment Guide

Deploy ComputeSwarm in 10 minutes.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLOUD                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Render.com (Free Tier)                     │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │     Marketplace API (FastAPI)               │    │    │
│  │  │     https://computeswarm.onrender.com       │    │    │
│  │  └─────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────┘    │
│                            │                                 │
│  ┌─────────────────────────┴───────────────────────────┐    │
│  │              Supabase (Free Tier)                    │    │
│  │              PostgreSQL Database                     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                             │
                             │ HTTPS API
                             │
┌────────────────────────────┴────────────────────────────────┐
│                      LOCAL MACHINES                          │
│                                                              │
│  ┌──────────────────┐          ┌──────────────────┐         │
│  │   Seller Agent   │          │   Buyer CLI      │         │
│  │   (GPU Machine)  │          │   (Any Machine)  │         │
│  │                  │          │                  │         │
│  │  🎮 RTX 4090     │          │  $ submit job    │         │
│  │  💰 Earns USDC   │          │  💳 Pays USDC    │         │
│  └──────────────────┘          └──────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

## Step 1: Deploy Marketplace to Render

### Option A: One-Click Deploy (Easiest)

1. Push your code to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click "New" → "Blueprint"
4. Connect your GitHub repo
5. Render will use `render.yaml` automatically

### Option B: Manual Deploy

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New" → "Web Service"
3. Connect your GitHub repo
4. Configure:
   - **Name**: `computeswarm-marketplace`
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements-server.txt`
   - **Start Command**: `uvicorn src.marketplace.server:app --host 0.0.0.0 --port $PORT`
5. Add environment variables:
   - `SUPABASE_URL` = your Supabase project URL
   - `SUPABASE_ANON_KEY` = your Supabase anon key
   - `NETWORK` = `base-sepolia`
   - `TESTNET_MODE` = `true`
6. Click "Create Web Service"

Your marketplace will be live at: `https://computeswarm-xxx.onrender.com`

## Step 2: Set Up Supabase Database

1. Create account at [supabase.com](https://supabase.com)
2. Create new project
3. Go to SQL Editor
4. Run the schema:

```sql
-- Copy contents of src/database/schema.sql and run it
```

5. Get your credentials from Project Settings → API:
   - Project URL
   - Anon/Public key

## Step 3: Configure Local Seller

On a machine with a GPU:

```bash
# Clone the repo
git clone https://github.com/yourusername/compute-swarm.git
cd compute-swarm

# Setup
./scripts/setup_seller.sh

# Configure .env
MARKETPLACE_URL=https://computeswarm-xxx.onrender.com  # Your Render URL
SELLER_PRIVATE_KEY=0x...  # Your wallet private key
SELLER_ADDRESS=0x...      # Your wallet address

# Start earning!
python -m src.seller.agent
```

## Step 4: Submit Jobs as Buyer

```bash
# Configure buyer
MARKETPLACE_URL=https://computeswarm-xxx.onrender.com
BUYER_PRIVATE_KEY=0x...
BUYER_ADDRESS=0x...

# Submit a job
python -m src.buyer.cli

> templates   # See available templates
> template    # Submit using a template
```

---

## How to Demo

### Demo Script (2-3 minutes)

**Setup (before demo):**
1. Have marketplace running on Render
2. Have seller agent running locally (your GPU machine)
3. Have buyer CLI ready

**Demo Flow:**

1. **Show the marketplace is live** (30 sec)
   ```bash
   curl https://computeswarm-xxx.onrender.com/health
   curl https://computeswarm-xxx.onrender.com/api/v1/stats
   ```

2. **Show seller agent detecting GPU** (30 sec)
   - Point to the terminal running seller agent
   - Show GPU detection, registration, "Available" status

3. **Submit a job** (60 sec)
   ```bash
   python -m src.buyer.cli
   > templates                    # Show available templates
   > template                     # Select gpu_benchmark
     matrix_size: 2048
     iterations: 10
   ```

4. **Watch it execute** (30 sec)
   - Switch to seller terminal
   - Show job being claimed, executed
   - Show earnings update

5. **Show the result** (30 sec)
   ```bash
   > status <job_id>
   # Show COMPLETED status, output, cost
   ```

### Key Points to Highlight

- **x402 Integration**: "Payment is handled trustlessly via x402 protocol"
- **No Trust Required**: "Buyer's funds are verified before job starts"
- **Real GPU**: "This is running on my actual GPU right now"
- **Per-Second Billing**: "Charged $X for Y seconds of compute"

---

## Troubleshooting

### Render deployment fails

- Check build logs for errors
- Ensure `requirements-server.txt` has all needed packages
- Check Python version is 3.11+

### Seller can't connect to marketplace

- Verify `MARKETPLACE_URL` is correct (include https://)
- Check Render service is running (not sleeping)
- Free tier services sleep after 15 min inactivity

### Database errors

- Verify Supabase credentials are correct
- Ensure schema is applied
- Check Supabase dashboard for errors

---

## Environment Variables Reference

### Marketplace (Render)
```
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
NETWORK=base-sepolia
TESTNET_MODE=true
LOG_LEVEL=INFO
```

### Seller (Local)
```
MARKETPLACE_URL=https://computeswarm-xxx.onrender.com
SELLER_PRIVATE_KEY=0x...
SELLER_ADDRESS=0x...
DOCKER_ENABLED=true
```

### Buyer (Local)
```
MARKETPLACE_URL=https://computeswarm-xxx.onrender.com
BUYER_PRIVATE_KEY=0x...
BUYER_ADDRESS=0x...
```

