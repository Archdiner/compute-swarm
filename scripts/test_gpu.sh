#!/bin/bash
# Test GPU detection

set -e

echo "Testing GPU Detection..."
echo ""

python -m src.compute.gpu_detector
