# ComputeSwarm Jupyter GPU Notebook
# Based on NVIDIA CUDA with JupyterLab and PyTorch

FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

LABEL maintainer="ComputeSwarm"
LABEL description="GPU-enabled JupyterLab for ComputeSwarm sessions"

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    git \
    wget \
    curl \
    vim \
    htop \
    && rm -rf /var/lib/apt/lists/*

# Create jupyter user
RUN useradd -m -s /bin/bash jovyan && \
    mkdir -p /home/jovyan/work && \
    chown -R jovyan:jovyan /home/jovyan

# Set working directory
WORKDIR /home/jovyan

# Install Python packages
RUN pip3 install --no-cache-dir \
    jupyterlab>=4.0 \
    notebook \
    ipywidgets \
    jupyter-server-proxy

# Install PyTorch with CUDA support
RUN pip3 install --no-cache-dir \
    torch \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/cu121

# Install common ML/Data Science packages
RUN pip3 install --no-cache-dir \
    numpy \
    pandas \
    scipy \
    scikit-learn \
    matplotlib \
    seaborn \
    plotly \
    pillow \
    tqdm

# Install transformers and related
RUN pip3 install --no-cache-dir \
    transformers \
    accelerate \
    datasets \
    tokenizers \
    sentencepiece

# Install additional ML frameworks
RUN pip3 install --no-cache-dir \
    xgboost \
    lightgbm \
    optuna

# Clean up
RUN pip3 cache purge

# Switch to jovyan user
USER jovyan

# Expose Jupyter port
EXPOSE 8888

# Set environment variables
ENV JUPYTER_ENABLE_LAB=yes
ENV SHELL=/bin/bash

# Start JupyterLab
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--NotebookApp.token=''", "--NotebookApp.password=''"]

