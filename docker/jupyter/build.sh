#!/bin/bash
# Build the ComputeSwarm Jupyter GPU image

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Build image
echo "Building computeswarm/jupyter-gpu:latest..."
docker build -t computeswarm/jupyter-gpu:latest "$SCRIPT_DIR"

echo ""
echo "✓ Image built successfully!"
echo ""
echo "To test locally:"
echo "  docker run --gpus all -p 8888:8888 computeswarm/jupyter-gpu:latest"
echo ""
echo "To push to Docker Hub (requires login):"
echo "  docker push computeswarm/jupyter-gpu:latest"

