#!/bin/bash
# ComputeSwarm Seller Setup Script
# One-click setup for sellers to start earning with their GPU
#
# Usage: ./scripts/setup_seller.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Status indicators
CHECK="${GREEN}✓${NC}"
CROSS="${RED}✗${NC}"
WARN="${YELLOW}!${NC}"
INFO="${BLUE}→${NC}"

echo_header() {
    echo ""
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BOLD}${CYAN}  ComputeSwarm Seller Setup${NC}"
    echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

echo_step() {
    echo -e "\n${BOLD}[$1/6]${NC} $2"
    echo -e "${CYAN}─────────────────────────────────────────${NC}"
}

echo_ok() {
    echo -e "  ${CHECK} $1"
}

echo_fail() {
    echo -e "  ${CROSS} $1"
}

echo_warn() {
    echo -e "  ${WARN} $1"
}

echo_info() {
    echo -e "  ${INFO} $1"
}

# Track overall status
SETUP_OK=true
GPU_TYPE="cpu"
HAS_NVIDIA_DOCKER=false

echo_header

# ============================================================================
# Step 1: Check Docker
# ============================================================================
echo_step 1 "Checking Docker installation"

if command -v docker &> /dev/null; then
    DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
    echo_ok "Docker installed (v$DOCKER_VERSION)"
    
    # Check if Docker daemon is running
    if docker info > /dev/null 2>&1; then
        echo_ok "Docker daemon is running"
    else
        echo_fail "Docker daemon is not running"
        echo_info "Please start Docker and run this script again"
        echo_info "  macOS: Open Docker Desktop"
        echo_info "  Linux: sudo systemctl start docker"
        SETUP_OK=false
    fi
else
    echo_fail "Docker is not installed"
    echo_info "Install Docker from: https://docs.docker.com/get-docker/"
    echo_info "  macOS: brew install --cask docker"
    echo_info "  Ubuntu: sudo apt install docker.io"
    SETUP_OK=false
fi

# ============================================================================
# Step 2: Check GPU and nvidia-docker
# ============================================================================
echo_step 2 "Detecting GPU hardware"

# Check for NVIDIA GPU
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_COUNT=$(nvidia-smi --query-gpu=count --format=csv,noheader 2>/dev/null | head -1)
    if [ -n "$GPU_NAME" ]; then
        echo_ok "NVIDIA GPU detected: $GPU_NAME"
        if [ "$GPU_COUNT" -gt 1 ] 2>/dev/null; then
            echo_ok "Multi-GPU setup: $GPU_COUNT GPUs"
        fi
        GPU_TYPE="cuda"
        
        # Check nvidia-docker
        if docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi > /dev/null 2>&1; then
            echo_ok "NVIDIA Docker support working"
            HAS_NVIDIA_DOCKER=true
        else
            echo_warn "NVIDIA Docker not configured"
            echo_info "Install nvidia-container-toolkit:"
            echo_info "  https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
            echo_info "GPU jobs will not work until this is fixed"
        fi
    fi
elif [ "$(uname)" = "Darwin" ]; then
    # Check for Apple Silicon
    if [ "$(uname -m)" = "arm64" ]; then
        CHIP=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Apple Silicon")
        echo_ok "Apple Silicon detected: $CHIP"
        GPU_TYPE="mps"
        echo_warn "Note: MPS (Metal) runs natively, no Docker GPU passthrough"
    else
        echo_warn "Intel Mac detected - CPU only"
        GPU_TYPE="cpu"
    fi
else
    echo_warn "No GPU detected - CPU only mode"
    GPU_TYPE="cpu"
fi

# ============================================================================
# Step 3: Build/Pull Docker images
# ============================================================================
echo_step 3 "Setting up Docker images"

if [ "$SETUP_OK" = true ]; then
    # Check for existing images
    CPU_IMAGE_EXISTS=$(docker images -q computeswarm-sandbox:latest 2>/dev/null)
    GPU_IMAGE_EXISTS=$(docker images -q computeswarm-sandbox-gpu:latest 2>/dev/null)
    
    # Build CPU image if not exists
    if [ -z "$CPU_IMAGE_EXISTS" ]; then
        echo_info "Building CPU sandbox image..."
        if docker build -t computeswarm-sandbox:latest -f "$PROJECT_ROOT/Dockerfile.sandbox" "$PROJECT_ROOT" > /dev/null 2>&1; then
            echo_ok "CPU sandbox image built"
        else
            echo_warn "CPU sandbox build failed - will use subprocess fallback"
        fi
    else
        echo_ok "CPU sandbox image already exists"
    fi
    
    # Build GPU image if NVIDIA and not exists
    if [ "$GPU_TYPE" = "cuda" ] && [ "$HAS_NVIDIA_DOCKER" = true ]; then
        if [ -z "$GPU_IMAGE_EXISTS" ]; then
            echo_info "Building GPU sandbox image (this may take 5-10 minutes)..."
            if docker build -t computeswarm-sandbox-gpu:latest -f "$PROJECT_ROOT/Dockerfile.sandbox-gpu" "$PROJECT_ROOT" 2>&1 | tail -5; then
                echo_ok "GPU sandbox image built"
            else
                echo_warn "GPU sandbox build failed"
                echo_info "You can try: ./scripts/build_docker.sh gpu"
            fi
        else
            echo_ok "GPU sandbox image already exists"
        fi
    fi
else
    echo_warn "Skipping Docker image setup (Docker not available)"
fi

# ============================================================================
# Step 4: Python environment
# ============================================================================
echo_step 4 "Checking Python environment"

if [ -d "$PROJECT_ROOT/venv" ]; then
    echo_ok "Virtual environment exists"
else
    echo_info "Creating virtual environment..."
    python3 -m venv "$PROJECT_ROOT/venv"
    echo_ok "Virtual environment created"
fi

# Check if dependencies are installed
source "$PROJECT_ROOT/venv/bin/activate"
if python -c "import torch; import fastapi" 2>/dev/null; then
    echo_ok "Dependencies installed"
else
    echo_info "Installing dependencies..."
    pip install -q -r "$PROJECT_ROOT/requirements.txt"
    echo_ok "Dependencies installed"
fi

# ============================================================================
# Step 5: Configuration
# ============================================================================
echo_step 5 "Checking configuration"

ENV_FILE="$PROJECT_ROOT/.env"

if [ -f "$ENV_FILE" ]; then
    echo_ok ".env file exists"
    
    # Check for required seller config
    if grep -q "SELLER_ADDRESS=" "$ENV_FILE" && grep -q "SELLER_PRIVATE_KEY=" "$ENV_FILE"; then
        SELLER_ADDR=$(grep "SELLER_ADDRESS=" "$ENV_FILE" | cut -d'=' -f2)
        if [ -n "$SELLER_ADDR" ] && [ "$SELLER_ADDR" != "" ]; then
            echo_ok "Seller wallet configured: ${SELLER_ADDR:0:10}..."
        else
            echo_warn "SELLER_ADDRESS is empty"
            echo_info "Add your wallet address to .env"
        fi
    else
        echo_warn "Seller wallet not configured"
        echo_info "Add SELLER_ADDRESS and SELLER_PRIVATE_KEY to .env"
    fi
    
    # Check marketplace URL
    if grep -q "MARKETPLACE_URL=" "$ENV_FILE"; then
        MARKETPLACE_URL=$(grep "MARKETPLACE_URL=" "$ENV_FILE" | cut -d'=' -f2)
        echo_ok "Marketplace URL: $MARKETPLACE_URL"
    fi
else
    echo_warn ".env file not found"
    echo_info "Creating .env from template..."
    
    cat > "$ENV_FILE" << 'EOF'
# ComputeSwarm Seller Configuration
# Generated by setup_seller.sh

# === REQUIRED: Seller Wallet ===
# Your Ethereum wallet address (receives payments)
SELLER_ADDRESS=

# Your wallet private key (for signing - keep secret!)
SELLER_PRIVATE_KEY=

# === Marketplace Connection ===
MARKETPLACE_URL=http://localhost:8000

# === Network Configuration ===
# Use base-sepolia for testing, base-mainnet for production
NETWORK=base-sepolia
RPC_URL=https://sepolia.base.org
USDC_CONTRACT_ADDRESS=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# === Pricing (USD per hour) ===
DEFAULT_PRICE_PER_HOUR_CUDA=2.00
DEFAULT_PRICE_PER_HOUR_MPS=0.50

# === Docker Configuration ===
DOCKER_ENABLED=true
DOCKER_IMAGE=computeswarm-sandbox:latest
DOCKER_IMAGE_GPU=computeswarm-sandbox-gpu:latest
DOCKER_MEMORY_LIMIT=4g
DOCKER_CPU_LIMIT=2.0

# === Model Caching ===
MODEL_CACHE_ENABLED=true
MODEL_CACHE_DIR=~/.cache/computeswarm

# === Testnet Mode ===
# Set to false for real USDC payments
TESTNET_MODE=true
EOF
    echo_ok ".env file created"
    echo_warn "Please edit .env and add your wallet address and private key"
fi

# ============================================================================
# Step 6: Test run
# ============================================================================
echo_step 6 "Running diagnostics"

# Test GPU detection
echo_info "Testing GPU detection..."
cd "$PROJECT_ROOT"
source venv/bin/activate

GPU_TEST=$(python -c "
from src.execution.gpu_detector import GPUDetector
gpu = GPUDetector.detect_gpu()
print(f'{gpu.gpu_type.value}|{gpu.device_name}|{gpu.vram_gb or 0}')
" 2>/dev/null || echo "error|unknown|0")

if [ "$GPU_TEST" != "error|unknown|0" ]; then
    IFS='|' read -r DETECTED_TYPE DETECTED_NAME DETECTED_VRAM <<< "$GPU_TEST"
    echo_ok "GPU detection: $DETECTED_TYPE - $DETECTED_NAME (${DETECTED_VRAM}GB)"
else
    echo_warn "GPU detection failed"
fi

# Test Docker execution
if [ "$SETUP_OK" = true ] && docker images -q computeswarm-sandbox:latest > /dev/null 2>&1; then
    echo_info "Testing Docker sandbox..."
    if docker run --rm computeswarm-sandbox:latest python3 -c "print('sandbox ok')" > /dev/null 2>&1; then
        echo_ok "Docker sandbox working"
    else
        echo_warn "Docker sandbox test failed"
    fi
fi

# ============================================================================
# Summary
# ============================================================================
echo ""
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${CYAN}  Setup Summary${NC}"
echo -e "${BOLD}${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

echo -e "  GPU Type:     ${BOLD}$GPU_TYPE${NC}"
if [ "$GPU_TYPE" = "cuda" ]; then
    echo -e "  GPU Docker:   $([ "$HAS_NVIDIA_DOCKER" = true ] && echo "${GREEN}Yes${NC}" || echo "${YELLOW}No${NC}")"
fi
echo -e "  Docker:       $([ "$SETUP_OK" = true ] && echo "${GREEN}Ready${NC}" || echo "${RED}Not Ready${NC}")"
echo ""

if [ "$SETUP_OK" = true ]; then
    echo -e "${GREEN}${BOLD}Ready to start selling compute!${NC}"
    echo ""
    echo "  To start the seller agent:"
    echo -e "    ${CYAN}cd $PROJECT_ROOT${NC}"
    echo -e "    ${CYAN}source venv/bin/activate${NC}"
    echo -e "    ${CYAN}python -m src.seller.agent${NC}"
    echo ""
else
    echo -e "${YELLOW}${BOLD}Setup incomplete - please fix the issues above${NC}"
    echo ""
fi

