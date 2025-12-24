"""
Setup configuration for ComputeSwarm
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="compute-swarm",
    version="0.1.0",
    author="ComputeSwarm Team",
    description="Decentralized P2P GPU Marketplace using x402 protocol",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/compute-swarm",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.109.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.5.3",
        "pydantic-settings>=2.1.0",
        "httpx>=0.26.0",
        "torch>=2.1.2",
        "web3>=6.15.0",
        "eth-account>=0.10.0",
        "structlog>=24.1.0",
        "python-dotenv>=1.0.0",
        "rich>=13.7.0",
        "supabase>=2.3.4",
        "upstash-redis>=0.15.0",
        "x402>=0.2.1",
    ],
    # Note: Removed entry_points for console_scripts
    # These don't work well with async functions
    # Use scripts/start_*.sh instead or run directly:
    #   python -m src.marketplace.server
    #   python -m src.seller.agent
    #   python -m src.buyer.cli
)
