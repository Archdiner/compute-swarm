#!/bin/bash
# Start the ComputeSwarm Seller Agent

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "Starting ComputeSwarm Seller Agent..."
echo "Seller Address: ${SELLER_ADDRESS:-Not configured}"
echo "Marketplace URL: ${MARKETPLACE_URL:-http://localhost:8000}"
echo ""

# Start the seller agent
python -m src.seller.agent
