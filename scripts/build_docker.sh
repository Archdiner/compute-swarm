#!/bin/bash
# Build ComputeSwarm Docker sandbox images
# Usage: ./scripts/build_docker.sh [cpu|gpu|all]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

echo_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

echo_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

build_cpu() {
    echo_info "Building CPU sandbox image..."
    docker build -t computeswarm-sandbox:latest -f "$PROJECT_ROOT/Dockerfile.sandbox" "$PROJECT_ROOT"
    echo_info "CPU sandbox image built: computeswarm-sandbox:latest"
}

build_gpu() {
    echo_info "Building GPU sandbox image (this may take a while)..."
    
    # Check if nvidia-docker is available
    if docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi > /dev/null 2>&1; then
        echo_info "NVIDIA Docker support detected"
    else
        echo_warn "NVIDIA Docker not detected - GPU image will still be built but may not work without nvidia-docker"
    fi
    
    docker build -t computeswarm-sandbox-gpu:latest -f "$PROJECT_ROOT/Dockerfile.sandbox-gpu" "$PROJECT_ROOT"
    echo_info "GPU sandbox image built: computeswarm-sandbox-gpu:latest"
}

build_jupyter() {
    echo_info "Building Jupyter GPU notebook image..."
    docker build -t computeswarm-jupyter:latest -f "$PROJECT_ROOT/docker/jupyter/Dockerfile" "$PROJECT_ROOT/docker/jupyter"
    echo_info "Jupyter image built: computeswarm-jupyter:latest"
}

# Check Docker is available
if ! command -v docker &> /dev/null; then
    echo_error "Docker is not installed. Please install Docker first."
    echo_info "Install instructions: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check Docker daemon is running
if ! docker info > /dev/null 2>&1; then
    echo_error "Docker daemon is not running. Please start Docker."
    exit 1
fi

# Parse arguments
BUILD_TARGET="${1:-all}"

case "$BUILD_TARGET" in
    cpu)
        build_cpu
        ;;
    gpu)
        build_gpu
        ;;
    jupyter)
        build_jupyter
        ;;
    all)
        build_cpu
        build_gpu
        build_jupyter
        ;;
    *)
        echo "Usage: $0 [cpu|gpu|jupyter|all]"
        echo "  cpu     - Build CPU-only sandbox image"
        echo "  gpu     - Build GPU-enabled sandbox image (requires nvidia-docker)"
        echo "  jupyter - Build Jupyter notebook image"
        echo "  all     - Build all images (default)"
        exit 1
        ;;
esac

echo ""
echo_info "Build complete! Available images:"
docker images | grep -E "computeswarm|REPOSITORY" | head -10

