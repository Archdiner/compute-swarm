"""
Distributed Training Support
Detects and configures PyTorch DDP and Horovod for multi-GPU/multi-node training
"""

import os
import re
from typing import Optional, Dict, Any
import structlog

logger = structlog.get_logger()


class DistributedBackend(str):
    """Supported distributed training backends"""
    DDP = "ddp"
    NONE = "none"


def detect_distributed_backend(script: str) -> DistributedBackend:
    """
    Detect which distributed training backend is used in the script
    
    Args:
        script: Python script content
        
    Returns:
        DistributedBackend enum value
    """
    script_lower = script.lower()
    
    # Check for PyTorch DDP
    ddp_patterns = [
        r"torch\.distributed\.init_process_group",
        r"torch\.distributed\.DistributedDataParallel",
        r"DistributedDataParallel",
        r"from torch\.nn\.parallel import DistributedDataParallel",
        r"import torch\.distributed",
    ]
    
    for pattern in ddp_patterns:
        if re.search(pattern, script_lower):
            logger.info("ddp_detected", pattern=pattern)
            return DistributedBackend.DDP
    
    return DistributedBackend.NONE


def setup_ddp_environment(
    num_gpus: int,
    master_addr: Optional[str] = None,
    master_port: int = 29500,
    rank: Optional[int] = None,
    local_rank: Optional[int] = None
) -> Dict[str, str]:
    """
    Set up environment variables for PyTorch DDP
    
    Args:
        num_gpus: Number of GPUs (WORLD_SIZE)
        master_addr: Master node address (default: localhost for single-node)
        master_port: Master node port (default: 29500)
        rank: Process rank (optional, will be set per process)
        local_rank: Local GPU index (optional, will be set per process)
        
    Returns:
        Dictionary of environment variables to set
    """
    env_vars = {}
    
    # Set master address (default to localhost for single-node)
    if master_addr is None:
        master_addr = "localhost"
    
    env_vars["MASTER_ADDR"] = master_addr
    env_vars["MASTER_PORT"] = str(master_port)
    env_vars["WORLD_SIZE"] = str(num_gpus)
    
    # Set rank and local_rank if provided
    if rank is not None:
        env_vars["RANK"] = str(rank)
    if local_rank is not None:
        env_vars["LOCAL_RANK"] = str(local_rank)
    
    # Set CUDA visible devices if not already set
    if "CUDA_VISIBLE_DEVICES" not in os.environ:
        cuda_devices = ",".join([str(i) for i in range(num_gpus)])
        env_vars["CUDA_VISIBLE_DEVICES"] = cuda_devices
    
    logger.info(
        "ddp_environment_setup",
        num_gpus=num_gpus,
        master_addr=master_addr,
        master_port=master_port,
        rank=rank,
        local_rank=local_rank
    )
    
    return env_vars




def get_distributed_env_vars(
    script: str,
    num_gpus: int,
    num_nodes: int = 1,
    master_addr: Optional[str] = None,
    master_port: int = 29500,
    rank: Optional[int] = None,
    local_rank: Optional[int] = None
) -> Dict[str, str]:
    """
    Automatically detect distributed backend and set up environment variables
    
    Args:
        script: Python script content
        num_gpus: Number of GPUs
        num_nodes: Number of nodes (default: 1)
        master_addr: Master node address (for multi-node)
        master_port: Master node port
        rank: Process rank (for multi-node)
        local_rank: Local GPU index
        
    Returns:
        Dictionary of environment variables to set
    """
    backend = detect_distributed_backend(script)
    
    if backend == DistributedBackend.DDP:
        # For multi-node, use provided master_addr, otherwise localhost
        if num_nodes > 1 and master_addr:
            return setup_ddp_environment(
                num_gpus=num_gpus * num_nodes,  # Total GPUs across all nodes
                master_addr=master_addr,
                master_port=master_port,
                rank=rank,
                local_rank=local_rank
            )
        else:
            # Single-node multi-GPU
            return setup_ddp_environment(
                num_gpus=num_gpus,
                master_addr="localhost",
                master_port=master_port,
                rank=rank,
                local_rank=local_rank
            )
    else:
        # No distributed training detected or unsupported
        return {}


def format_docker_env_vars(env_vars: Dict[str, str]) -> list:
    """
    Format environment variables for Docker command
    
    Args:
        env_vars: Dictionary of environment variables
        
    Returns:
        List of ["-e", "KEY=VALUE"] pairs for Docker command
    """
    docker_env = []
    for key, value in env_vars.items():
        docker_env.extend(["-e", f"{key}={value}"])
    return docker_env

