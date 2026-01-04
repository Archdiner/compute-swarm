# Deployment Guide

Deploy ComputeSwarm in 10 minutes.

## Free Hosting Options

Since you already have Render, here are **free tier alternatives**:

### 🚂 Railway (Recommended)
**Free tier:** 512MB RAM, 1GB disk, PostgreSQL included

1. **Sign up:** [railway.app](https://railway.app)
2. **Create project:** Click "New Project" → "Deploy from GitHub repo"
3. **Connect repo:** Select your `compute-swarm` repository
4. **Environment variables:**
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_ANON_KEY=your-anon-key
   NETWORK=base-sepolia
   TESTNET_MODE=true
   LOG_LEVEL=INFO
   ```
5. **Add database:** Click "Add Plugin" → PostgreSQL
6. **Deploy:** Railway will auto-detect FastAPI and deploy

**Your URL:** `https://computeswarm-production.up.railway.app`

### 🪶 Fly.io
**Free tier:** 256MB RAM, 1GB disk

1. **Install flyctl:** `brew install flyctl`
2. **Login:** `fly auth login`
3. **Launch:** `fly launch` (in project directory)
4. **Configure:** Select region, set secrets for env vars
5. **Deploy:** `fly deploy`

### 🌐 Vercel (Not Recommended for APIs)
**Free tier:** Good for static sites, not Python APIs

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         CLOUD                                │
│  ┌─────────────────────────────────────────────────────┐    │
│  │           Railway (Free Tier)                      │    │
│  │  ┌─────────────────────────────────────────────┐    │    │
│  │  │     Marketplace API (FastAPI)               │    │    │
│  │  │     https://your-app.railway.app            │    │    │
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

## Railway Deployment Steps

### 1. Push Code to GitHub
```bash
cd compute-swarm
git add .
git commit -m "Ready for production deployment"
git push origin main
```

### 2. Create Railway Account
- Go to [railway.app](https://railway.app)
- Sign up with GitHub (fastest)
- Verify your email

### 3. Deploy Project
1. **New Project** → **Deploy from GitHub repo**
2. **Search** → Select your `compute-swarm` repo
3. **Configure:**
   - **Root Directory:** `/` (leave default)
   - **Environment:** Production
4. Click **Deploy**

### 4. Add Database
1. In your project dashboard, click **+ Add Plugin**
2. Search **PostgreSQL** → Add it
3. Railway will create a DATABASE_URL automatically

### 5. Set Environment Variables
In your Railway project settings:

```
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
NETWORK=base-sepolia
TESTNET_MODE=true

# Optional
LOG_LEVEL=INFO
DEBUG=false
```

### 6. Update Buyer/Seller Config
Once deployed, update your local `.env`:

```bash
# Use your Railway URL
MARKETPLACE_URL=https://your-app.railway.app
```

## Demo Setup

### For Hackathon Judges
1. **Deployed API:** `https://your-app.railway.app/docs`
2. **Seller machine:** Run `./scripts/setup_seller.sh`
3. **Buyer machine:** Run `python -m src.buyer.cli`
4. **Demo script:** `python examples/demo_quick_benchmark.py`

---

## Troubleshooting

### Railway Issues
- **Build fails:** Check Railway logs, ensure `requirements-server.txt` exists
- **App crashes:** Check env vars are set correctly
- **Database connection:** Use Railway's PostgreSQL, not Supabase for now

### Common Fixes
- **Memory issues:** Free tier is 512MB, might need to optimize
- **Cold starts:** Railway has some cold start delay (10-30s)
- **Logs:** Use `railway logs` command to debug

---

## Alternative Free Options

| Platform | RAM | Disk | Database | Python Support |
|----------|-----|------|----------|----------------|
| **Railway** | 512MB | 1GB | PostgreSQL | ✅ Excellent |
| **Fly.io** | 256MB | 1GB | External | ✅ Good |
| **Render** | 750MB | 1GB | External | ✅ Good |
| **Heroku** | 512MB | - | Add-on | ❌ Free tier gone |

**Railway is your best bet** - it's designed for modern apps like yours!
