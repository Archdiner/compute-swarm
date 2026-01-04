"""
Vercel Serverless Function Entry Point for FastAPI Backend
"""
import os
import sys

# Add project root to Python path
project_root = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, project_root)

from mangum import Mangum
from src.marketplace.server import app

# Wrap FastAPI app with Mangum for AWS Lambda/API Gateway (which Vercel uses)
# Note: lifespan events don't work in serverless, so we disable them
# The api_gateway_base_path strips /api prefix before routing
handler = Mangum(app, lifespan="off", api_gateway_base_path="/api")

# Vercel serverless function handler (required export)
# Vercel will call this function for requests matching /api/*
def handler_func(event, context):
    """Vercel serverless function handler"""
    return handler(event, context)
