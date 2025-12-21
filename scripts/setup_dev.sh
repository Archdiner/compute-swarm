#!/bin/bash
# Set up development environment

set -e

echo "========================================="
echo "ComputeSwarm Development Setup"
echo "========================================="
echo ""

# Check Python version
python_version=$(python3 --version | cut -d' ' -f2)
echo "Python version: $python_version"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip
echo "✓ pip upgraded"

# Install requirements
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt
echo "✓ Dependencies installed"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Please edit .env and add your wallet addresses and keys"
fi

# Make scripts executable
echo ""
echo "Making scripts executable..."
chmod +x scripts/*.sh
echo "✓ Scripts are executable"

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env with your configuration"
echo "2. Test GPU detection: ./scripts/test_gpu.sh"
echo "3. Start marketplace: ./scripts/start_marketplace.sh"
echo "4. In another terminal, start seller: ./scripts/start_seller.sh"
echo "5. In another terminal, use buyer CLI: ./scripts/start_buyer.sh"
echo ""
echo "To activate the virtual environment in new terminals:"
echo "  source venv/bin/activate"
echo ""
