# Free Tier Services Setup Guide

This guide shows how to set up all free-tier services for ComputeSwarm.

## 1. Supabase (Database) - FREE

**Free Tier**: 500MB database, 2GB bandwidth/month

### Setup

1. Go to [supabase.com](https://supabase.com)
2. Click "Start your project" (sign up with GitHub)
3. Create new project
   - Organization: Create new
   - Name: `computeswarm`
   - Database Password: Generate strong password (save it!)
   - Region: Choose closest to you
   - Pricing Plan: **Free**

4. Wait ~2 minutes for project to initialize

5. Get credentials from **Project Settings > API**:
   ```bash
   SUPABASE_URL=https://xxxxx.supabase.co
   SUPABASE_ANON_KEY=eyJhb...
   SUPABASE_SERVICE_KEY=eyJhb...
   ```

6. Get database connection from **Project Settings > Database**:
   ```bash
   DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.xxxxx.supabase.co:5432/postgres
   ```

7. Create tables in SQL Editor:
   - Go to **SQL Editor**
   - Run the SQL from `TECH_STACK.md` (nodes, jobs, payments tables)

### Limits
- ✅ 500MB storage (thousands of jobs)
- ✅ 2GB bandwidth/month
- ✅ 50,000 monthly active users
- ✅ Daily backups
- ✅ Unlimited API requests

---

## 2. Upstash Redis (Caching) - OPTIONAL

**Note**: Redis is not currently used in the codebase. The app works entirely with Supabase (PostgreSQL). You can skip this for MVP.

**Free Tier**: 10,000 commands/day

### Setup (Optional)

1. Go to [upstash.com](https://upstash.com)
2. Sign up with GitHub
3. Click "Create Database"
   - Name: `computeswarm-cache`
   - Type: **Regional** (faster, free tier)
   - Region: Choose closest to you
   - TLS: Enabled

4. Copy credentials from dashboard:
   ```bash
   UPSTASH_REDIS_REST_URL=https://xxxxx.upstash.io
   UPSTASH_REDIS_REST_TOKEN=AXXXXXXXXXXXXXXXXXbw
   ```

### Limits
- ✅ 10,000 commands/day (enough for dev + light production)
- ✅ 256MB storage
- ✅ TLS encryption
- ⚠️ Resets daily (not persistent beyond 24hrs on free tier)

---

## 3. Base Sepolia (Testnet) - FREE

**Free Tier**: Unlimited transactions (testnet)

### Setup

1. Get testnet ETH (for gas):
   - Go to [Coinbase Faucet](https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet)
   - Connect your wallet
   - Request testnet ETH (0.1 ETH/day)

2. Get testnet USDC:
   - Contract: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
   - Use a faucet or bridge from Sepolia ETH to Base Sepolia

3. Add to .env:
   ```bash
   NETWORK=base-sepolia
   RPC_URL=https://sepolia.base.org
   USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e
   ```

### Limits
- ✅ Unlimited testnet transactions
- ✅ Free gas (via faucet)
- ✅ Resets daily

---

## 4. Render (Hosting) - FREE

**Free Tier**: 750 hours/month (sleeps after 15min inactivity)

### Setup

1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your GitHub repo
5. Configure:
   - Name: `computeswarm-api`
   - Region: Oregon (US West) - free
   - Branch: `main`
   - Runtime: **Python 3**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn src.marketplace.server:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT`
   - Plan: **Free**

6. Add environment variables in Render dashboard (copy from .env)

7. Deploy!

### Limits
- ✅ 750 hours/month (24/7 with sleep)
- ⚠️ Spins down after 15min inactivity (cold start ~30s)
- ✅ Auto SSL certificate
- ✅ 100GB bandwidth/month

**Note**: To avoid cold starts, upgrade to $7/month for always-on.

---

## 5. GitHub Actions (CI/CD) - FREE

**Free Tier**: 2,000 minutes/month (public repos unlimited)

### Setup

Already configured in `.github/workflows/tests.yml`!

Just push to GitHub and tests run automatically.

### Limits
- ✅ 2,000 minutes/month (private repos)
- ✅ Unlimited for public repos
- ✅ Linux runners

---

## 6. Sentry (Error Tracking) - OPTIONAL FREE

**Free Tier**: 5,000 errors/month

### Setup

1. Go to [sentry.io](https://sentry.io)
2. Sign up (free plan)
3. Create new project
   - Platform: **Python**
   - Name: `computeswarm`
4. Copy DSN:
   ```bash
   SENTRY_DSN=https://xxxxx@xxxxx.ingest.sentry.io/xxxxx
   ```

5. Add to code (optional):
   ```python
   import sentry_sdk
   sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"))
   ```

### Limits
- ✅ 5,000 errors/month
- ✅ 1 team member
- ✅ 30 days retention

---

## Summary

| Service | Free Tier | Setup Time | Required? |
|---------|-----------|------------|-----------|
| Supabase | 500MB DB | 5 min | ✅ Yes |
| Upstash | 10K cmds/day | 2 min | ❌ Optional (not used yet) |
| Base Sepolia | Unlimited | 5 min | ✅ Yes |
| Render | 750 hrs/mo | 10 min | ⚠️ Dev only |
| GitHub Actions | 2K min/mo | 0 min | ✅ Yes |
| Sentry | 5K errors/mo | 5 min | ❌ Optional |

**Total Setup Time**: ~30 minutes
**Total Cost**: $0/month for MVP

---

## After Setup

Add all credentials to `.env`:

```bash
# Copy from .env.example
cp .env.example .env

# Edit with your credentials
nano .env
```

Then test locally:

```bash
make install
make test
make run-marketplace
```

Once working locally, push to GitHub → Render auto-deploys!
