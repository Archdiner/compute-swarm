#!/bin/bash
# Start the ComputeSwarm Frontend Development Server

set -e

cd "$(dirname "$0")/../frontend"

echo "Starting ComputeSwarm Frontend..."
echo ""

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

# Check for .env.local
if [ ! -f ".env.local" ]; then
    echo "WARNING: .env.local not found. Creating from example..."
    if [ -f ".env.local.example" ]; then
        cp .env.local.example .env.local
        echo "Please edit .env.local and add your Privy App ID"
    else
        echo "ERROR: .env.local.example not found"
        exit 1
    fi
fi

echo "Starting development server on http://localhost:3000"
echo ""

npm run dev

