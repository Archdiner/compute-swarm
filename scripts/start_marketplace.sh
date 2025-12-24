#!/bin/bash
# Start the ComputeSwarm Marketplace Server

set -e

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
HOST=${MARKETPLACE_HOST:-0.0.0.0}
PORT=${MARKETPLACE_PORT:-8000}
RELOAD=${RELOAD:-false}
LOG_LEVEL=${LOG_LEVEL:-info}

echo "Starting ComputeSwarm Marketplace..."
echo "Host: $HOST"
echo "Port: $PORT"
echo "Log Level: $LOG_LEVEL"
echo ""

# Start the server
if [ "$RELOAD" = "true" ]; then
    uvicorn src.marketplace.server:app \
        --host $HOST \
        --port $PORT \
        --reload \
        --log-level $(echo $LOG_LEVEL | tr '[:upper:]' '[:lower:]')
else
    uvicorn src.marketplace.server:app \
        --host $HOST \
        --port $PORT \
        --log-level $(echo $LOG_LEVEL | tr '[:upper:]' '[:lower:]')
fi
