# ComputeSwarm Frontend

React frontend for ComputeSwarm decentralized GPU marketplace.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Create `.env.local` file:
```bash
cp .env.local.example .env.local
```

3. Add your Privy App ID to `.env.local`:
```
VITE_PRIVY_APP_ID=your_privy_app_id_here
VITE_BACKEND_URL=http://localhost:8000
VITE_NETWORK=base-sepolia
```

4. Start development server:
```bash
npm run dev
```

## Deployment on Vercel

This project is configured for automatic deployment on Vercel:

1. Connect your GitHub repository to Vercel
2. Set environment variables in Vercel dashboard:
   - `VITE_PRIVY_APP_ID`: Your Privy App ID
   - `VITE_BACKEND_URL`: Your backend API URL (e.g., https://api.computeswarm.xyz)
   - `VITE_NETWORK`: `base-sepolia` or `base-mainnet`

3. Vercel will automatically:
   - Detect it's a Vite project
   - Run `npm install` and `npm run build`
   - Deploy to a production URL

The `vercel.json` configuration handles:
- SPA routing (all routes redirect to index.html)
- Asset caching for optimal performance

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Privy** for embedded wallet authentication
- **Tailwind CSS** for styling
- **Ethers.js** for blockchain interactions

