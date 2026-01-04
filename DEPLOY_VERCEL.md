# Deploying Frontend to Vercel

This guide explains how to deploy the ComputeSwarm frontend to Vercel.

## Prerequisites

1. A Vercel account (sign up at https://vercel.com)
2. Your Privy App ID (get from https://privy.io)
3. Your backend API URL (where the FastAPI server is deployed)

## Deployment Steps

### Option 1: Deploy via Vercel Dashboard (Recommended)

1. **Import Project:**
   - Go to https://vercel.com/new
   - Import your GitHub repository (Archdiner/compute-swarm)
   - Select the repository and click "Import"

2. **Configure Project:**
   - **Root Directory:** Set to `frontend`
   - **Framework Preset:** Vercel should auto-detect "Vite"
   - **Build Command:** `npm run build` (auto-detected)
   - **Output Directory:** `dist` (auto-detected)
   - **Install Command:** `npm install` (auto-detected)

3. **Set Environment Variables:**
   Add these in the Vercel dashboard under "Environment Variables":
   
   - `VITE_PRIVY_APP_ID`: Your Privy App ID
     - Example: `clxxxxxxxxxxxxxxxxxx`
   - `VITE_BACKEND_URL`: Your backend API URL
     - For development: `http://localhost:8000`
     - For production: `https://api.yourdomain.com` or your deployed backend URL
   - `VITE_NETWORK`: Network to use
     - `base-sepolia` (testnet) or `base-mainnet` (production)

4. **Deploy:**
   - Click "Deploy"
   - Vercel will build and deploy your frontend
   - You'll get a URL like `https://compute-swarm-frontend.vercel.app`

### Option 2: Deploy via Vercel CLI

1. **Install Vercel CLI:**
   ```bash
   npm install -g vercel
   ```

2. **Login:**
   ```bash
   vercel login
   ```

3. **Navigate to frontend directory:**
   ```bash
   cd frontend
   ```

4. **Deploy:**
   ```bash
   vercel
   ```

5. **Set Environment Variables:**
   ```bash
   vercel env add VITE_PRIVY_APP_ID
   vercel env add VITE_BACKEND_URL
   vercel env add VITE_NETWORK
   ```

6. **Redeploy with environment variables:**
   ```bash
   vercel --prod
   ```

## Post-Deployment Configuration

### Update Backend CORS

After deploying to Vercel, update your backend CORS settings to include your Vercel URL:

1. Add your Vercel frontend URL to the backend environment variable:
   ```bash
   FRONTEND_URL=https://your-app.vercel.app
   ```

2. Or update `src/config.py` CORS origins to include:
   ```python
   cors_origins: list[str] = Field(
       default=["http://localhost:3000", "https://your-app.vercel.app"]
   )
   ```

### Update Privy Configuration

1. In your Privy dashboard, add your Vercel domain to allowed origins
2. This allows Privy authentication to work from your production domain

### Custom Domain (Optional)

1. In Vercel dashboard, go to your project settings
2. Click "Domains"
3. Add your custom domain (e.g., `app.computeswarm.xyz`)
4. Update DNS records as instructed by Vercel

## Environment Variables Summary

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_PRIVY_APP_ID` | Privy App ID for authentication | `clxxxxxxxxxxxxxxxxxx` |
| `VITE_BACKEND_URL` | Backend API URL | `https://api.computeswarm.xyz` |
| `VITE_NETWORK` | Blockchain network | `base-sepolia` or `base-mainnet` |

## Troubleshooting

### Build Fails

- Check that all environment variables are set
- Verify `package.json` has all required dependencies
- Check Vercel build logs for specific errors

### CORS Errors

- Ensure backend CORS includes your Vercel URL
- Check that `FRONTEND_URL` is set in backend environment

### Privy Authentication Not Working

- Verify Privy App ID is correct
- Check that Vercel domain is added to Privy allowed origins
- Ensure network configuration matches (testnet vs mainnet)

### API Calls Failing

- Verify `VITE_BACKEND_URL` is correctly set
- Check backend is accessible from the internet
- Verify backend CORS configuration

## Continuous Deployment

Once connected to GitHub, Vercel automatically deploys on every push to `main` branch. 

- **Preview deployments:** Created for every pull request
- **Production deployments:** Created for pushes to `main`

## Monitoring

- Check deployment status in Vercel dashboard
- View build logs for debugging
- Monitor runtime errors in Vercel's function logs

## Cost

Vercel offers a generous free tier:
- Unlimited deployments
- 100GB bandwidth per month
- Automatic HTTPS
- Global CDN

For production workloads, consider Vercel Pro plan.

