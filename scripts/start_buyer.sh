#!/bin/bash
# Start the ComputeSwarm Buyer CLI

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

echo "Starting ComputeSwarm Buyer CLI..."
echo "Buyer Address: ${BUYER_ADDRESS:-Not configured}"
echo "Marketplace URL: ${MARKETPLACE_URL:-http://localhost:8000}"
echo ""

# Start the buyer CLI
python -m src.buyer.cli "$@"
