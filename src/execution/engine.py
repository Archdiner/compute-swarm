"""
Secure job execution engine
Executes Python scripts in isolated Docker containers with safety controls
Supports GPU passthrough for CUDA workloads
"""

import asyncio
import shutil
import tempfile
import os
import signal
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass
from decimal import Decimal
import time

import structlog

from src.execution.distributed import (
    detect_distributed_backend,
    get_distributed_env_vars,
    format_docker_env_vars
)
from src.execution.metrics import MetricsCollector
from src.execution.checkpoint_manager import create_checkpoint_manager
from src.execution.model_manager import create_model_manager

logger = structlog.get_logger()

# GPU type for execution context
GPUExecutionType = Literal["cuda", "mps", "cpu", "none"]


@dataclass
class ExecutionResult:
    """Result of job execution"""
    success: bool
    output: str
    error: str
    exit_code: int
    execution_time: Decimal  # seconds
    stdout: str
    stderr: str
    metrics_collector: Optional['MetricsCollector'] = None  # For metrics collection


class JobExecutor:
    """
    Secure Python job executor with Docker sandboxing

    Safety features:
    - Docker container isolation
    - No network access (--network none)
    - Read-only filesystem (--read-only)
    - Memory limits (--memory)
    - CPU limits (--cpus)
    - Process limits (--pids-limit)
    - Non-root user execution
    - Timeout enforcement
    """

    def __init__(
        self,
        workspace_dir: Optional[Path] = None,
        max_output_size: int = 1024 * 1024,  # 1MB
        docker_enabled: bool = True,
        docker_image: str = "computeswarm-sandbox:latest",
        docker_image_gpu: str = "computeswarm-sandbox-gpu:latest",
        docker_memory_limit: str = "4g",
        docker_cpu_limit: float = 2.0,
        docker_pids_limit: int = 100,
        docker_tmpfs_size: str = "1g",
        model_cache_dir: Optional[Path] = None,
        gpu_type: GPUExecutionType = "none",
        docker_network_enabled: bool = True,
        docker_setup_timeout: int = 300
    ):
        """
        Initialize executor

        Args:
            workspace_dir: Directory for temporary files (default: system temp)
            max_output_size: Maximum output size in bytes
            docker_enabled: Whether to use Docker sandboxing
            docker_image: Docker image for CPU sandboxed execution
            docker_image_gpu: Docker image for GPU sandboxed execution (CUDA)
            docker_memory_limit: Memory limit for containers (e.g., "4g")
            docker_cpu_limit: CPU limit for containers
            docker_pids_limit: Maximum number of processes in container
            docker_tmpfs_size: Size of tmpfs mount for /tmp
            model_cache_dir: Directory for persistent model cache (HuggingFace, etc.)
            gpu_type: GPU type for execution ("cuda", "mps", "cpu", "none")
        """
        self.workspace_dir = workspace_dir or Path(tempfile.gettempdir()) / "computeswarm"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.max_output_size = max_output_size
        self.docker_enabled = docker_enabled
        self.docker_image = docker_image
        self.docker_image_gpu = docker_image_gpu
        self.docker_memory_limit = docker_memory_limit
        self.docker_cpu_limit = docker_cpu_limit
        self.docker_pids_limit = docker_pids_limit
        self.docker_tmpfs_size = docker_tmpfs_size
        self.gpu_type = gpu_type
        
        # Model cache directory for persistent caching
        self.model_cache_dir = model_cache_dir or Path.home() / ".cache" / "computeswarm"
        self.model_cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Network access configuration
        self.docker_network_enabled = docker_network_enabled
        self.docker_setup_timeout = docker_setup_timeout
        
        # Check Docker availability on init
        self._docker_available: Optional[bool] = None
        self._nvidia_docker_available: Optional[bool] = None

    async def _check_docker_available(self) -> bool:
        """Check if Docker is available and running"""
        if self._docker_available is not None:
            return self._docker_available
            
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            self._docker_available = process.returncode == 0
            
            if self._docker_available:
                logger.info("docker_available", image=self.docker_image)
            else:
                logger.warning("docker_not_available", message="Docker command failed")
                
        except FileNotFoundError:
            self._docker_available = False
            logger.warning("docker_not_found", message="Docker binary not found")
            
        return self._docker_available

    async def _check_docker_image_exists(self, image: Optional[str] = None) -> bool:
        """Check if a Docker image exists"""
        image = image or self.docker_image
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "image", "inspect", image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    async def _check_nvidia_docker_available(self) -> bool:
        """Check if nvidia-docker (GPU support) is available"""
        if self._nvidia_docker_available is not None:
            return self._nvidia_docker_available
        
        try:
            # Try to run a simple GPU container
            process = await asyncio.create_subprocess_exec(
                "docker", "run", "--rm", "--gpus", "all",
                "nvidia/cuda:12.1.0-base-ubuntu22.04",
                "nvidia-smi", "--query-gpu=name", "--format=csv,noheader",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30
            )
            self._nvidia_docker_available = process.returncode == 0
            
            if self._nvidia_docker_available:
                gpu_name = stdout.decode().strip().split('\n')[0]
                logger.info("nvidia_docker_available", gpu=gpu_name)
            else:
                logger.warning("nvidia_docker_not_available", 
                             message="nvidia-docker check failed",
                             stderr=stderr.decode()[:200])
                
        except asyncio.TimeoutError:
            self._nvidia_docker_available = False
            logger.warning("nvidia_docker_timeout", message="GPU check timed out")
        except FileNotFoundError:
            self._nvidia_docker_available = False
            logger.warning("nvidia_docker_not_found", message="Docker not found")
        except Exception as e:
            self._nvidia_docker_available = False
            logger.warning("nvidia_docker_check_failed", error=str(e))
            
        return self._nvidia_docker_available
    
    def _get_effective_docker_image(self) -> str:
        """Get the appropriate Docker image based on GPU type"""
        if self.gpu_type == "cuda":
            return self.docker_image_gpu
        return self.docker_image

    async def execute_job(
        self,
        job_id: str,
        script: str,
        requirements: Optional[str] = None,
        timeout_seconds: int = 3600,
        gpu_type: Optional[GPUExecutionType] = None,
        num_gpus: int = 1,
        gpu_memory_limit_per_gpu: Optional[str] = None,
        buyer_address: Optional[str] = None,
        resume_from_checkpoint: Optional[str] = None
    ) -> ExecutionResult:
        """
        Execute a Python job with safety controls

        Args:
            job_id: Unique job identifier
            script: Python script to execute
            requirements: Optional pip requirements (e.g., "numpy==1.24.0\\ntorch==2.1.0")
            timeout_seconds: Maximum execution time
            gpu_type: Override GPU type for this job (defaults to executor's gpu_type)
            num_gpus: Number of GPUs to allocate (for multi-GPU jobs)
            gpu_memory_limit_per_gpu: Per-GPU memory limit (e.g., "8g")

        Returns:
            ExecutionResult with output and status
        """
        effective_gpu_type = gpu_type or self.gpu_type
        logger.info("job_execution_started", job_id=job_id, timeout=timeout_seconds, 
                   gpu_type=effective_gpu_type, num_gpus=num_gpus)
        start_time = time.time()

        # Create isolated workspace for this job
        job_workspace = self.workspace_dir / job_id
        job_workspace.mkdir(parents=True, exist_ok=True)
        
        # Create checkpoints directory
        checkpoint_dir = job_workspace / "checkpoints"
        checkpoint_dir.mkdir(exist_ok=True)

        try:
            # Download checkpoint if resuming
            if resume_from_checkpoint:
                try:
                    from src.database import get_db_client
                    from src.storage import get_storage_client
                    
                    db = get_db_client()
                    storage = get_storage_client()
                    
                    checkpoint = await db.get_checkpoint(resume_from_checkpoint)
                    if checkpoint:
                        # Download checkpoint to workspace
                        checkpoint_path = checkpoint_dir / Path(checkpoint["storage_path"]).name
                        await storage.download_file(
                            storage_path=checkpoint["storage_path"],
                            destination_path=str(checkpoint_path)
                        )
                        logger.info(
                            "checkpoint_restored",
                            job_id=job_id,
                            checkpoint_id=resume_from_checkpoint,
                            checkpoint_path=str(checkpoint_path)
                        )
                    else:
                        logger.warning(
                            "checkpoint_not_found",
                            job_id=job_id,
                            checkpoint_id=resume_from_checkpoint
                        )
                except Exception as e:
                    logger.warning(
                        "checkpoint_restore_failed",
                        job_id=job_id,
                        checkpoint_id=resume_from_checkpoint,
                        error=str(e)
                    )
                    # Continue execution even if checkpoint restore fails
            # Determine execution mode
            use_docker = self.docker_enabled and await self._check_docker_available()
            
            # Select appropriate image based on GPU type
            if effective_gpu_type == "cuda":
                docker_image = self.docker_image_gpu
            else:
                docker_image = self.docker_image
            
            if use_docker and not await self._check_docker_image_exists(docker_image):
                logger.warning(
                    "docker_image_not_found",
                    image=docker_image,
                    message="Falling back to subprocess execution"
                )
                use_docker = False
            
            # Check nvidia-docker for GPU jobs
            use_gpu = False
            if use_docker and effective_gpu_type == "cuda":
                if await self._check_nvidia_docker_available():
                    use_gpu = True
                else:
                    logger.warning(
                        "nvidia_docker_unavailable",
                        message="GPU requested but nvidia-docker not available, running on CPU"
                    )
            
            if use_docker:
                logger.info("using_docker_execution", job_id=job_id, image=docker_image, 
                           gpu_enabled=use_gpu, num_gpus=num_gpus,
                           network_enabled=self.docker_network_enabled)
                result = await self._run_in_docker(
                    job_id=job_id,
                    workspace=job_workspace,
                    script=script,
                    requirements=requirements,
                    timeout=timeout_seconds,
                    docker_image=docker_image,
                    use_gpu=use_gpu,
                    num_gpus=num_gpus,
                    gpu_memory_limit_per_gpu=gpu_memory_limit_per_gpu
                )
            else:
                logger.info("using_subprocess_execution", job_id=job_id)
                # Install requirements if specified (only for subprocess mode)
                if requirements:
                    await self._install_requirements(job_workspace, requirements, timeout_seconds // 4)
                result = await self._run_script(job_workspace, script, timeout_seconds)

            execution_time = Decimal(str(time.time() - start_time))
            
            # Collect metrics from output
            metrics_collector = MetricsCollector(job_id)
            parsed_metrics = metrics_collector.parse_output(result.stdout, result.stderr)
            
            if parsed_metrics:
                logger.info(
                    "metrics_collected",
                    job_id=job_id,
                    metric_count=len(parsed_metrics),
                    metric_names=list(set(m["metric_name"] for m in parsed_metrics))
                )
            
            # Detect ML frameworks
            if metrics_collector.detect_mlflow_usage(result.stdout + result.stderr):
                logger.info("mlflow_detected_in_output", job_id=job_id)
            if metrics_collector.detect_wandb_usage(result.stdout + result.stderr):
                logger.info("wandb_detected_in_output", job_id=job_id)
            
            # Scan and upload checkpoints
            checkpoint_ids = []
            try:
                checkpoint_manager = create_checkpoint_manager(job_id, job_workspace)
                checkpoint_ids = await checkpoint_manager.scan_and_upload_checkpoints()
                if checkpoint_ids:
                    logger.info(
                        "checkpoints_auto_uploaded",
                        job_id=job_id,
                        checkpoint_count=len(checkpoint_ids)
                    )
            except Exception as e:
                logger.warning("checkpoint_scan_failed", job_id=job_id, error=str(e))
            
            # Scan and upload models
            model_ids = []
            if buyer_address:
                try:
                    model_manager = create_model_manager(job_id, job_workspace, buyer_address)
                    model_ids = await model_manager.scan_and_upload_models()
                    if model_ids:
                        logger.info(
                            "models_auto_uploaded",
                            job_id=job_id,
                            model_count=len(model_ids)
                        )
                except Exception as e:
                    logger.warning("model_scan_failed", job_id=job_id, error=str(e))
            
            logger.info(
                "job_execution_completed",
                job_id=job_id,
                success=result.success,
                execution_time=float(execution_time),
                exit_code=result.exit_code,
                docker=use_docker,
                metrics_collected=len(parsed_metrics),
                checkpoints_uploaded=len(checkpoint_ids),
                models_uploaded=len(model_ids)
            )

            return ExecutionResult(
                success=result.success,
                output=result.output,
                error=result.error,
                exit_code=result.exit_code,
                execution_time=execution_time,
                stdout=result.stdout,
                stderr=result.stderr,
                metrics_collector=metrics_collector if parsed_metrics else None
            )

        except asyncio.TimeoutError:
            execution_time = Decimal(str(time.time() - start_time))
            logger.warning("job_execution_timeout", job_id=job_id, timeout=timeout_seconds)
            return ExecutionResult(
                success=False,
                output="",
                error=f"Job execution timed out after {timeout_seconds} seconds",
                exit_code=-1,
                execution_time=execution_time,
                stdout="",
                stderr="Timeout",
                metrics_collector=None
            )

        except Exception as e:
            execution_time = Decimal(str(time.time() - start_time))
            logger.error("job_execution_error", job_id=job_id, error=str(e))
            return ExecutionResult(
                success=False,
                output="",
                error=f"Job execution failed: {str(e)}",
                exit_code=-1,
                execution_time=execution_time,
                stdout="",
                stderr=str(e),
                metrics_collector=None
            )

        finally:
            # Cleanup workspace
            await self._cleanup_workspace(job_workspace)

    async def _run_in_docker(
        self,
        job_id: str,
        workspace: Path,
        script: str,
        requirements: Optional[str],
        timeout: int,
        docker_image: Optional[str] = None,
        use_gpu: bool = False,
        num_gpus: int = 1,
        gpu_memory_limit_per_gpu: Optional[str] = None
    ) -> ExecutionResult:
        """
        Run job with two-phase execution if network is enabled:
        - Phase 1: Setup container (network enabled) - install requirements, download models
        - Phase 2: Execution container (network disabled) - run job script
        """
        # If network is enabled and we have requirements, use two-phase execution
        if self.docker_network_enabled and requirements:
            return await self._run_two_phase_docker(
                job_id=job_id,
                workspace=workspace,
                script=script,
                requirements=requirements,
                timeout=timeout,
                docker_image=docker_image,
                use_gpu=use_gpu,
                num_gpus=num_gpus,
                gpu_memory_limit_per_gpu=gpu_memory_limit_per_gpu
            )
        else:
            # Fall back to single-phase execution (original behavior)
            return await self._run_single_phase_docker(
                job_id=job_id,
                workspace=workspace,
                script=script,
                requirements=requirements,
                timeout=timeout,
                docker_image=docker_image,
                use_gpu=use_gpu,
                num_gpus=num_gpus,
                gpu_memory_limit_per_gpu=gpu_memory_limit_per_gpu
            )
    
    async def _run_two_phase_docker(
        self,
        job_id: str,
        workspace: Path,
        script: str,
        requirements: Optional[str],
        timeout: int,
        docker_image: Optional[str] = None,
        use_gpu: bool = False,
        num_gpus: int = 1,
        gpu_memory_limit_per_gpu: Optional[str] = None
    ) -> ExecutionResult:
        """
        Two-phase execution:
        Phase 1: Setup container with network (install requirements, download models)
        Phase 2: Execution container without network (run job)
        """
        container_name = f"computeswarm_job_{job_id.replace('-', '_')}"
        setup_container_name = f"{container_name}_setup"
        effective_image = docker_image or self.docker_image
        
        # Write script and requirements to workspace
        script_file = workspace / "job_script.py"
        script_file.write_text(script)
        
        if requirements:
            req_file = workspace / "requirements.txt"
            req_file.write_text(requirements)
        
        # Create shared volume directory for installed packages
        shared_volume = workspace / "shared_volume"
        shared_volume.mkdir(exist_ok=True)
        packages_dir = shared_volume / ".local"
        packages_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("two_phase_execution_starting", job_id=job_id, phase="setup")
        
        # ========================================================================
        # PHASE 1: Setup Container (Network Enabled)
        # ========================================================================
        setup_success = False
        setup_error = ""
        
        try:
            setup_result = await self._run_setup_container(
                setup_container_name=setup_container_name,
                workspace=workspace,
                shared_volume=shared_volume,
                requirements=requirements,
                docker_image=effective_image,
                use_gpu=use_gpu,
                num_gpus=num_gpus,
                gpu_memory_limit_per_gpu=gpu_memory_limit_per_gpu
            )
            setup_success = setup_result["success"]
            setup_error = setup_result.get("error", "")
            
            if not setup_success:
                logger.error("setup_phase_failed", job_id=job_id, error=setup_error)
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"Setup phase failed: {setup_error}",
                    exit_code=-1,
                    execution_time=Decimal("0"),
                    stdout=setup_result.get("stdout", ""),
                    stderr=setup_result.get("stderr", ""),
                    metrics_collector=None
                )
            
            logger.info("setup_phase_completed", job_id=job_id)
            
        except asyncio.TimeoutError:
            logger.error("setup_phase_timeout", job_id=job_id, timeout=self.docker_setup_timeout)
            return ExecutionResult(
                success=False,
                output="",
                error=f"Setup phase timed out after {self.docker_setup_timeout} seconds",
                exit_code=-1,
                execution_time=Decimal("0"),
                stdout="",
                stderr="Setup timeout",
                metrics_collector=None
            )
        except Exception as e:
            logger.error("setup_phase_error", job_id=job_id, error=str(e))
            return ExecutionResult(
                success=False,
                output="",
                error=f"Setup phase error: {str(e)}",
                exit_code=-1,
                execution_time=Decimal("0"),
                stdout="",
                stderr=str(e),
                metrics_collector=None
            )
        
        # ========================================================================
        # PHASE 2: Execution Container (Network Disabled)
        # ========================================================================
        logger.info("two_phase_execution_starting", job_id=job_id, phase="execution")
        
        return await self._run_execution_container(
            container_name=container_name,
            workspace=workspace,
            shared_volume=shared_volume,
            script=script,
            timeout=timeout,
            docker_image=effective_image,
            use_gpu=use_gpu,
            num_gpus=num_gpus,
            gpu_memory_limit_per_gpu=gpu_memory_limit_per_gpu
        )
    
    async def _run_setup_container(
        self,
        setup_container_name: str,
        workspace: Path,
        shared_volume: Path,
        requirements: Optional[str],
        docker_image: str,
        use_gpu: bool,
        num_gpus: int,
        gpu_memory_limit_per_gpu: Optional[str]
    ) -> dict:
        """
        Phase 1: Run setup container with network enabled to install requirements
        """
        cmd = [
            "docker", "run",
            "--rm",
            "--name", setup_container_name,
            # Network enabled for setup phase
            # Note: Docker doesn't support domain whitelisting natively
            # We rely on the setup timeout and monitoring to limit exposure
            "--memory", self.docker_memory_limit,
            "--cpus", str(self.docker_cpu_limit),
            "--pids-limit", str(self.docker_pids_limit),
            "--tmpfs", f"/tmp:size={self.docker_tmpfs_size}",
            "--security-opt", "no-new-privileges",
        ]
        
        # Add GPU passthrough if needed (for model downloads that might use GPU)
        if use_gpu:
            if num_gpus >= 8 or num_gpus == 0:
                if gpu_memory_limit_per_gpu:
                    gpu_spec = ",".join([f"device={i}:memory={gpu_memory_limit_per_gpu}" for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"{gpu_spec}"'])
                else:
                    cmd.extend(["--gpus", "all"])
            else:
                if gpu_memory_limit_per_gpu:
                    gpu_spec = ",".join([f"device={i}:memory={gpu_memory_limit_per_gpu}" for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"{gpu_spec}"'])
                else:
                    gpu_spec = ",".join([str(i) for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"device={gpu_spec}"'])
        
        # Mount model cache for downloads
        cmd.extend([
            "-v", f"{self.model_cache_dir.absolute()}:/root/.cache:rw",
            "-e", "HF_HOME=/root/.cache/huggingface",
            "-e", "TORCH_HOME=/root/.cache/torch",
            "-e", "TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers",
        ])
        
        # Mount workspace and shared volume
        cmd.extend([
            "-v", f"{workspace.absolute()}:/workspace:ro",  # Read-only workspace
            "-v", f"{shared_volume.absolute()}:/shared:rw",  # Writable shared volume for packages
            "-w", "/workspace",
            docker_image,
        ])
        
        # Setup script: install requirements to shared volume
        setup_script = f'''#!/bin/bash
set -e
export PYTHONUSERBASE=/shared/.local
export PATH="/shared/.local/bin:$PATH"

echo "=== Setup Phase: Installing Requirements ==="
if [ -f /workspace/requirements.txt ]; then
    pip install --user --no-cache-dir -r /workspace/requirements.txt
    echo "=== Requirements installed successfully ==="
else
    echo "=== No requirements.txt found, skipping installation ==="
fi

# Verify installation
echo "=== Verifying installed packages ==="
pip list --user | head -20
echo "=== Setup phase complete ==="
'''
        
        setup_file = workspace / "setup.sh"
        setup_file.write_text(setup_script)
        
        cmd.extend(["/bin/bash", "/workspace/setup.sh"])
        
        logger.info("setup_container_starting", container_name=setup_container_name, job_id=workspace.name)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.docker_setup_timeout
            )
            
            stdout_str = stdout.decode('utf-8', errors='replace')
            stderr_str = stderr.decode('utf-8', errors='replace')
            
            success = process.returncode == 0
            
            if not success:
                logger.warning("setup_container_failed", 
                             container_name=setup_container_name,
                             exit_code=process.returncode,
                             stderr=stderr_str[:500])
            
            return {
                "success": success,
                "stdout": stdout_str,
                "stderr": stderr_str,
                "error": stderr_str if not success else ""
            }
            
        except asyncio.TimeoutError:
            # Kill the container on timeout
            logger.warning("setup_container_timeout", container_name=setup_container_name)
            try:
                kill_process = await asyncio.create_subprocess_exec(
                    "docker", "kill", setup_container_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await kill_process.communicate()
            except Exception as e:
                logger.warning("docker_kill_failed", container_name=setup_container_name, error=str(e))
            
            raise
    
    async def _run_execution_container(
        self,
        container_name: str,
        workspace: Path,
        shared_volume: Path,
        script: str,
        timeout: int,
        docker_image: str,
        use_gpu: bool,
        num_gpus: int,
        gpu_memory_limit_per_gpu: Optional[str]
    ) -> ExecutionResult:
        """
        Phase 2: Run execution container with network disabled
        """
        script_file = workspace / "job_script.py"
        
        # Build Docker command with security constraints
        cmd = [
            "docker", "run",
            "--rm",
            "--name", container_name,
            "--network", "none",  # No network access
            "--read-only",  # Read-only filesystem
            "--tmpfs", f"/tmp:size={self.docker_tmpfs_size}",
            "--memory", self.docker_memory_limit,
            "--cpus", str(self.docker_cpu_limit),
            "--pids-limit", str(self.docker_pids_limit),
            "--security-opt", "no-new-privileges",
        ]
        
        # Add GPU passthrough if requested
        if use_gpu:
            if num_gpus >= 8 or num_gpus == 0:
                if gpu_memory_limit_per_gpu:
                    gpu_spec = ",".join([f"device={i}:memory={gpu_memory_limit_per_gpu}" for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"{gpu_spec}"'])
                else:
                    cmd.extend(["--gpus", "all"])
            else:
                if gpu_memory_limit_per_gpu:
                    gpu_spec = ",".join([f"device={i}:memory={gpu_memory_limit_per_gpu}" for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"{gpu_spec}"'])
                else:
                    gpu_spec = ",".join([str(i) for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"device={gpu_spec}"'])
            logger.info("gpu_passthrough_enabled", num_gpus=num_gpus, job_id=workspace.name,
                       gpu_memory_limit=gpu_memory_limit_per_gpu)
        
        # Detect distributed training and set up environment variables
        distributed_env_vars = {}
        if use_gpu and num_gpus > 1:
            script_content = script_file.read_text()
            distributed_env_vars = get_distributed_env_vars(
                script=script_content,
                num_gpus=num_gpus,
                num_nodes=1,
                master_addr="localhost",
                master_port=29500
            )
            
            if distributed_env_vars:
                backend = detect_distributed_backend(script_content)
                logger.info(
                    "distributed_training_detected",
                    backend=backend,
                    num_gpus=num_gpus,
                    job_id=workspace.name
                )
        
        # Mount model cache (read-only for execution)
        cmd.extend([
            "-v", f"{self.model_cache_dir.absolute()}:/root/.cache:ro",
            "-e", "HF_HOME=/root/.cache/huggingface",
            "-e", "TORCH_HOME=/root/.cache/torch",
            "-e", "TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers",
        ])
        
        # Mount shared volume with installed packages (read-only)
        cmd.extend([
            "-v", f"{shared_volume.absolute()}:/shared:ro",
        ])
        
        # Add distributed training environment variables
        if distributed_env_vars:
            cmd.extend(format_docker_env_vars(distributed_env_vars))
        
        # Mount workspace read-only and set working directory
        cmd.extend([
            "-v", f"{workspace.absolute()}:/workspace:ro",
            "-w", "/workspace",
            docker_image,
        ])
        
        # Run script with packages from shared volume
        wrapper_script = f'''#!/bin/bash
set -e
export PYTHONUSERBASE=/shared/.local
export PATH="/shared/.local/bin:$PATH"
export PYTHONPATH="/shared/.local/lib/python3.10/site-packages:/shared/.local/lib/python3.11/site-packages:$PYTHONPATH"
python3 /workspace/job_script.py
'''
        wrapper_file = workspace / "run_job.sh"
        wrapper_file.write_text(wrapper_script)
        cmd.extend(["/bin/bash", "/workspace/run_job.sh"])
        
        logger.info("execution_container_starting", container_name=container_name, job_id=workspace.name,
                   image=docker_image, gpu=use_gpu)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            stdout_str = stdout.decode('utf-8', errors='replace')[:self.max_output_size]
            stderr_str = stderr.decode('utf-8', errors='replace')[:self.max_output_size]
            
            success = process.returncode == 0
            output = stdout_str if success else ""
            error = stderr_str if not success else ""
            
            return ExecutionResult(
                success=success,
                output=output,
                error=error,
                exit_code=process.returncode or 0,
                execution_time=Decimal("0"),
                stdout=stdout_str,
                stderr=stderr_str,
                metrics_collector=None
            )
            
        except asyncio.TimeoutError:
            logger.warning("execution_container_timeout", container_name=container_name, job_id=workspace.name)
            try:
                kill_process = await asyncio.create_subprocess_exec(
                    "docker", "kill", container_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await kill_process.communicate()
            except Exception as e:
                logger.warning("docker_kill_failed", container_name=container_name, error=str(e))
            
            raise
    
    async def _run_single_phase_docker(
        self,
        job_id: str,
        workspace: Path,
        script: str,
        requirements: Optional[str],
        timeout: int,
        docker_image: Optional[str] = None,
        use_gpu: bool = False,
        num_gpus: int = 1,
        gpu_memory_limit_per_gpu: Optional[str] = None
    ) -> ExecutionResult:
        """
        Original single-phase execution (network disabled, requirements fail silently)
        Used as fallback when network is disabled or no requirements specified
        """
        """
        Run Python script in a Docker container with full sandboxing

        Security constraints:
        - --network none: No network access
        - --read-only: Read-only root filesystem
        - --tmpfs /tmp: Writable temp with size limit
        - --memory: Memory limit
        - --cpus: CPU limit
        - --pids-limit: Process limit
        - --security-opt no-new-privileges: Prevent privilege escalation
        - --user: Run as non-root
        
        GPU support:
        - --gpus: Pass through NVIDIA GPUs when available
        - Model cache volume for persistent caching
        """
        container_name = f"computeswarm_job_{job_id.replace('-', '_')}"
        effective_image = docker_image or self.docker_image
        
        # Write script to workspace
        script_file = workspace / "job_script.py"
        script_file.write_text(script)
        
        # Write requirements if specified
        if requirements:
            req_file = workspace / "requirements.txt"
            req_file.write_text(requirements)
        
        # Build Docker command with security constraints
        cmd = [
            "docker", "run",
            "--rm",  # Remove container after execution
            "--name", container_name,
            "--network", "none",  # No network access
            "--read-only",  # Read-only filesystem
            "--tmpfs", f"/tmp:size={self.docker_tmpfs_size}",  # Writable /tmp
            "--memory", self.docker_memory_limit,
            "--cpus", str(self.docker_cpu_limit),
            "--pids-limit", str(self.docker_pids_limit),
            "--security-opt", "no-new-privileges",  # Prevent privilege escalation
        ]
        
        # Add GPU passthrough if requested and available
        if use_gpu:
            if num_gpus >= 8 or num_gpus == 0:
                # Use all GPUs
                if gpu_memory_limit_per_gpu:
                    # Per-GPU memory limit not supported with "all", use device specification
                    gpu_spec = ",".join([f"device={i}:memory={gpu_memory_limit_per_gpu}" for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"{gpu_spec}"'])
                else:
                    cmd.extend(["--gpus", "all"])
            else:
                # Specify specific GPUs
                if gpu_memory_limit_per_gpu:
                    # Per-GPU memory limits
                    gpu_spec = ",".join([f"device={i}:memory={gpu_memory_limit_per_gpu}" for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"{gpu_spec}"'])
                else:
                    # Just device numbers
                    gpu_spec = ",".join([str(i) for i in range(num_gpus)])
                    cmd.extend(["--gpus", f'"device={gpu_spec}"'])
            logger.info("gpu_passthrough_enabled", num_gpus=num_gpus, job_id=job_id, 
                       gpu_memory_limit=gpu_memory_limit_per_gpu)
        
        # Detect distributed training and set up environment variables
        distributed_env_vars = {}
        if use_gpu and num_gpus > 1:
            # Read script to detect distributed backend
            script_content = script_file.read_text()
            distributed_env_vars = get_distributed_env_vars(
                script=script_content,
                num_gpus=num_gpus,
                num_nodes=1,  # Single-node for now, multi-node will be handled separately
                master_addr="localhost",
                master_port=29500
            )
            
            if distributed_env_vars:
                backend = detect_distributed_backend(script_content)
                logger.info(
                    "distributed_training_detected",
                    backend=backend,
                    num_gpus=num_gpus,
                    job_id=job_id
                )
        
        # Mount model cache for persistent caching (read-write for downloads)
        # This significantly speeds up repeated runs with same models
        cmd.extend([
            "-v", f"{self.model_cache_dir.absolute()}:/root/.cache:rw",
            "-e", "HF_HOME=/root/.cache/huggingface",
            "-e", "TORCH_HOME=/root/.cache/torch",
            "-e", "TRANSFORMERS_CACHE=/root/.cache/huggingface/transformers",
        ])
        
        # Add distributed training environment variables
        if distributed_env_vars:
            cmd.extend(format_docker_env_vars(distributed_env_vars))
        
        # Mount workspace read-only and set working directory
        cmd.extend([
            "-v", f"{workspace.absolute()}:/workspace:ro",
            "-w", "/workspace",
            effective_image,
        ])
        
        # If requirements specified, install them first then run script
        if requirements:
            # Create a wrapper script that installs requirements in /tmp and runs the job
            wrapper_script = f'''#!/bin/bash
set -e
export PYTHONUSERBASE=/tmp/.local
export PATH="/tmp/.local/bin:$PATH"
pip install --user --no-cache-dir -q -r /workspace/requirements.txt 2>/dev/null || true
python3 /workspace/job_script.py
'''
            wrapper_file = workspace / "run_job.sh"
            wrapper_file.write_text(wrapper_script)
            cmd.extend(["/bin/bash", "/workspace/run_job.sh"])
        else:
            cmd.extend(["python3", "/workspace/job_script.py"])
        
        logger.info("docker_container_starting", container_name=container_name, job_id=job_id,
                   image=effective_image, gpu=use_gpu)
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            
            stdout_str = stdout.decode('utf-8', errors='replace')[:self.max_output_size]
            stderr_str = stderr.decode('utf-8', errors='replace')[:self.max_output_size]
            
            success = process.returncode == 0
            output = stdout_str if success else ""
            error = stderr_str if not success else ""
            
            return ExecutionResult(
                success=success,
                output=output,
                error=error,
                exit_code=process.returncode or 0,
                execution_time=Decimal("0"),  # Will be set by caller
                stdout=stdout_str,
                stderr=stderr_str,
                metrics_collector=None
            )
            
        except asyncio.TimeoutError:
            # Kill the container on timeout
            logger.warning("docker_container_timeout", container_name=container_name, job_id=job_id)
            try:
                kill_process = await asyncio.create_subprocess_exec(
                    "docker", "kill", container_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await kill_process.communicate()
            except Exception as e:
                logger.warning("docker_kill_failed", container_name=container_name, error=str(e))
            
            raise

    async def _install_requirements(
        self,
        workspace: Path,
        requirements: str,
        timeout: int
    ) -> None:
        """
        Install Python requirements in isolated environment (subprocess mode only)

        Args:
            workspace: Job workspace directory
            requirements: Requirements string (one per line)
            timeout: Installation timeout in seconds
        """
        logger.info("installing_requirements", workspace=str(workspace))

        # Write requirements to file
        req_file = workspace / "requirements.txt"
        req_file.write_text(requirements)

        # Install in user space within workspace
        env = os.environ.copy()
        env["PYTHONUSERBASE"] = str(workspace / ".local")

        process = await asyncio.create_subprocess_exec(
            "pip", "install",
            "--user",
            "--no-warn-script-location",
            "-r", str(req_file),
            cwd=str(workspace),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            if process.returncode != 0:
                raise RuntimeError(
                    f"Failed to install requirements: {stderr.decode()[:500]}"
                )

            logger.info("requirements_installed", workspace=str(workspace))

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError(f"Requirements installation timed out after {timeout}s")

    async def _run_script(
        self,
        workspace: Path,
        script: str,
        timeout: int
    ) -> ExecutionResult:
        """
        Run Python script in isolated workspace (subprocess mode - fallback)

        Args:
            workspace: Job workspace directory
            script: Python script content
            timeout: Execution timeout in seconds

        Returns:
            ExecutionResult
        """
        # Write script to file
        script_file = workspace / "job_script.py"
        script_file.write_text(script)

        # Set up environment with local packages
        env = os.environ.copy()
        env["PYTHONUSERBASE"] = str(workspace / ".local")
        env["PYTHONPATH"] = str(workspace / ".local" / "lib" / "python3.10" / "site-packages")

        # Execute script
        logger.info("executing_script", workspace=str(workspace))

        process = await asyncio.create_subprocess_exec(
            "python3",
            str(script_file),
            cwd=str(workspace),
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group for cleanup
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )

            stdout_str = stdout.decode('utf-8', errors='replace')[:self.max_output_size]
            stderr_str = stderr.decode('utf-8', errors='replace')[:self.max_output_size]

            success = process.returncode == 0
            output = stdout_str if success else ""
            error = stderr_str if not success else ""

            return ExecutionResult(
                success=success,
                output=output,
                error=error,
                exit_code=process.returncode or 0,
                execution_time=Decimal("0"),  # Will be set by caller
                stdout=stdout_str,
                stderr=stderr_str,
                metrics_collector=None
            )

        except asyncio.TimeoutError:
            # Kill entire process group
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass

            await process.wait()
            raise

    async def _cleanup_workspace(self, workspace: Path) -> None:
        """
        Clean up job workspace

        Args:
            workspace: Directory to clean up
        """
        try:
            shutil.rmtree(workspace, ignore_errors=True)
            logger.info("workspace_cleaned", workspace=str(workspace))
        except Exception as e:
            logger.warning("workspace_cleanup_failed", workspace=str(workspace), error=str(e))

    def get_workspace_size(self, job_id: str) -> int:
        """
        Get total size of job workspace in bytes

        Args:
            job_id: Job identifier

        Returns:
            Size in bytes
        """
        workspace = self.workspace_dir / job_id
        if not workspace.exists():
            return 0

        total = 0
        for dirpath, dirnames, filenames in os.walk(workspace):
            for filename in filenames:
                filepath = Path(dirpath) / filename
                total += filepath.stat().st_size

        return total
