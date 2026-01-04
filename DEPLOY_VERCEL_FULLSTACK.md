# Deploying Full Stack to Vercel

This guide explains how to deploy the entire ComputeSwarm application (frontend + backend) to Vercel.

## Overview

Vercel supports both frontend and backend deployment:
- **Frontend**: React app (static build)
- **Backend**: FastAPI app (Python serverless functions)

Both deploy from a single repository with automatic routing.

## Prerequisites

1. A Vercel account (sign up at https://vercel.com)
2. GitHub repository with your code
3. Supabase database configured
4. Environment variables ready

## Deployment Steps

### 1. Import Project to Vercel

1. Go to https://vercel.com/new
2. Import your GitHub repository
3. Vercel will auto-detect the configuration from `vercel.json`

### 2. Configure Environment Variables

Add these in the Vercel dashboard under "Environment Variables":

#### Frontend Variables
- `VITE_BACKEND_URL`: Leave empty (uses same domain) or set to your backend URL
- `VITE_NETWORK`: `base-sepolia` (testnet) or `base-mainnet` (production)

#### Backend Variables
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_ANON_KEY`: Your Supabase anonymous key
- `DATABASE_URL`: Your Supabase database URL (optional, Supabase SDK uses URL + KEY)
- `FRONTEND_URL`: Your Vercel frontend URL (auto-set, or set manually)
- `NETWORK`: `base-sepolia` or `base-mainnet`
- `RPC_URL`: Base RPC URL (default: `https://sepolia.base.org` or `https://mainnet.base.org`)
- `USDC_CONTRACT_ADDRESS`: USDC contract address
  - Base Sepolia: `0x036CbD53842c5426634e7929541eC2318f3dCF7e`
  - Base Mainnet: `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
- `SELLER_PRIVATE_KEY`: (Optional) For seller operations
- `BUYER_PRIVATE_KEY`: (Optional) For buyer operations

#### Optional Variables
- `CORS_ORIGINS`: Comma-separated list of allowed origins (defaults include frontend URL)
- `LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`)

### 3. Build Configuration

Vercel will automatically:
- Build frontend from `frontend/` directory
- Deploy backend API routes from `api/` directory
- Route `/api/*` to backend
- Route `/*` to frontend (with SPA fallback)

### 4. Deploy

Click "Deploy" and Vercel will:
1. Install Python dependencies for backend
2. Build React frontend
3. Deploy both as serverless functions
4. Configure routing automatically

## Architecture

```
https://your-app.vercel.app/
├── /api/*          → Python serverless functions (FastAPI backend)
└── /*              → React frontend (static files)
```

## Environment Variables Summary

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `SUPABASE_URL` | Supabase project URL | `https://xxxxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase anonymous key | `eyJxxx...` |
| `VITE_NETWORK` | Blockchain network | `base-sepolia` |

### Optional (with defaults)

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_BACKEND_URL` | Backend API URL | Same domain (empty) |
| `NETWORK` | Backend network config | `base-sepolia` |
| `RPC_URL` | Base RPC endpoint | Auto based on network |
| `USDC_CONTRACT_ADDRESS` | USDC contract | Auto based on network |
| `FRONTEND_URL` | Frontend URL for CORS | Auto-detected |

## Routing

The `vercel.json` configuration handles:
- `/api/*` routes → Backend serverless functions
- `/*` routes → Frontend React app
- SPA routing (all routes fallback to `index.html`)

## Backend Endpoints

Once deployed, your API will be available at:
- `https://your-app.vercel.app/api/v1/stats`
- `https://your-app.vercel.app/api/v1/jobs/submit`
- `https://your-app.vercel.app/api/v1/jobs/{job_id}`
- etc.

## Frontend Configuration

The frontend automatically uses the same domain for API calls:
- Development: Uses `VITE_BACKEND_URL` if set, or proxies to localhost
- Production: Uses relative paths (`/api/*`) to hit same-domain backend

## Troubleshooting

### Backend Not Working

- Check Python version in Vercel (should be 3.10+)
- Verify `api/requirements.txt` has all dependencies
- Check Vercel function logs for errors
- Ensure `mangum` is in requirements

### CORS Errors

- Verify `FRONTEND_URL` is set correctly
- Check that frontend URL is in `CORS_ORIGINS` or defaults
- Ensure backend CORS middleware is configured

### Database Connection Issues

- Verify `SUPABASE_URL` and `SUPABASE_ANON_KEY` are correct
- Check Supabase project is active
- Verify network access from Vercel

### Frontend API Calls Failing

- Check `VITE_BACKEND_URL` is empty or correctly set
- Verify backend is deployed and accessible at `/api/*`
- Check browser console for specific errors

## Advantages of Full Stack on Vercel

✅ **Single Deployment**: Frontend + backend in one deploy  
✅ **Automatic HTTPS**: SSL certificates handled automatically  
✅ **Global CDN**: Fast content delivery worldwide  
✅ **Serverless Scaling**: Automatic scaling for backend functions  
✅ **Zero Config**: Routing handled automatically  
✅ **Preview Deployments**: Test changes before production  

## Limitations

⚠️ **Serverless Functions**: Backend runs as serverless functions (cold starts possible)  
⚠️ **Execution Time**: 10s timeout on Hobby plan, 60s on Pro  
⚠️ **Background Tasks**: Long-running tasks need different approach  
⚠️ **File System**: Ephemeral file system (use Supabase Storage)  

## Cost

**Hobby Plan (Free):**
- 100GB bandwidth/month
- Serverless function execution included
- Perfect for development and small projects

**Pro Plan ($20/month):**
- More bandwidth
- 60s function timeout
- Advanced features

## Monitoring

- Check deployment status in Vercel dashboard
- View function logs for backend debugging
- Monitor API usage and performance
- Set up alerts for errors

