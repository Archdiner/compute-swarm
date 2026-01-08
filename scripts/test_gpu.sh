#!/bin/bash
# Test GPU detection

set -e

echo "Testing GPU Detection..."
echo ""

python -m src.execution.gpu_detector
