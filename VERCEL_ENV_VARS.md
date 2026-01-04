# Vercel Environment Variables Guide

## Quick Setup

Copy these into Vercel Dashboard → Your Project → Settings → Environment Variables

## Required Variables

```bash
# Database (Required)
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Network Configuration (Required)
VITE_NETWORK=base-sepolia
NETWORK=base-sepolia

# Frontend URL (Auto-detected, but can set manually)
FRONTEND_URL=https://your-app.vercel.app
```

## Optional Variables (with sensible defaults)

```bash
# Backend Network
RPC_URL=https://sepolia.base.org
USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# Frontend
VITE_BACKEND_URL=  # Leave empty for same-domain, or set custom URL

# CORS
CORS_ORIGINS=https://your-app.vercel.app,https://www.your-app.vercel.app

# Logging
LOG_LEVEL=INFO

# Optional: Wallet Keys (if needed for automated operations)
SELLER_PRIVATE_KEY=0x...
BUYER_PRIVATE_KEY=0x...
```

## For Production (Base Mainnet)

Change these for production:

```bash
VITE_NETWORK=base-mainnet
NETWORK=base-mainnet
RPC_URL=https://mainnet.base.org
USDC_CONTRACT_ADDRESS=0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
```

## Getting Your Supabase Credentials

1. Go to https://supabase.com
2. Select your project
3. Go to Settings → API
4. Copy:
   - Project URL → `SUPABASE_URL`
   - `anon` `public` key → `SUPABASE_ANON_KEY`

## Setting in Vercel

1. Go to your project on Vercel
2. Settings → Environment Variables
3. Add each variable
4. Select environments (Production, Preview, Development)
5. Save and redeploy

## Verification

After deployment, verify:
- Frontend loads: `https://your-app.vercel.app`
- Backend health: `https://your-app.vercel.app/api/health`
- API docs: `https://your-app.vercel.app/api/docs`

