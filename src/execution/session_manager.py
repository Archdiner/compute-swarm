"""
Session Manager for Jupyter Notebooks and Container Sessions
Manages the lifecycle of interactive compute sessions
"""

import asyncio
import secrets
import socket
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from decimal import Decimal

import structlog

from src.config import get_seller_config
from src.models import JobType, SessionStatus

logger = structlog.get_logger()


@dataclass
class SessionInfo:
    """Information about a running session"""
    session_id: str
    job_id: str
    container_id: str
    session_type: JobType
    session_url: str
    session_token: str
    session_port: int
    started_at: datetime
    expires_at: datetime
    docker_image: str


class SessionManager:
    """
    Manages interactive Jupyter notebook and container sessions
    
    Features:
    - Start/stop Jupyter notebooks
    - Start/stop custom containers
    - Port allocation
    - Session billing
    - Automatic cleanup
    """
    
    def __init__(
        self,
        jupyter_image: str = "jupyter/scipy-notebook:latest",
        port_range_start: int = 8888,
        port_range_end: int = 8988,
        public_host: str = "localhost"
    ):
        """
        Initialize session manager
        
        Args:
            jupyter_image: Default Jupyter Docker image
            port_range_start: Start of port range for sessions
            port_range_end: End of port range
            public_host: Public hostname for session URLs
        """
        self.jupyter_image = jupyter_image
        self.port_range_start = port_range_start
        self.port_range_end = port_range_end
        self.public_host = public_host
        
        # Track active sessions
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.used_ports: set = set()
    
    def _find_available_port(self) -> int:
        """Find an available port in the configured range"""
        for port in range(self.port_range_start, self.port_range_end + 1):
            if port in self.used_ports:
                continue
            
            # Check if port is actually available
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(("0.0.0.0", port))
                    return port
            except OSError:
                continue
        
        raise RuntimeError("No available ports in range")
    
    async def _check_docker_available(self) -> bool:
        """Check if Docker is available"""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except FileNotFoundError:
            return False
    
    async def start_notebook_session(
        self,
        job_id: str,
        session_id: str,
        docker_image: Optional[str] = None,
        timeout_minutes: int = 60,
        gpu_enabled: bool = True,
        memory_limit: str = "8g",
        workspace_path: Optional[str] = None,
        num_gpus: int = 1,
        gpu_memory_limit_per_gpu: Optional[str] = None
    ) -> SessionInfo:
        """
        Start a Jupyter notebook session
        
        Args:
            job_id: Associated job ID
            session_id: Session record ID
            docker_image: Docker image to use (default: jupyter_image)
            timeout_minutes: Session duration
            gpu_enabled: Whether to enable GPU access
            memory_limit: Container memory limit
            workspace_path: Optional path to mount as workspace
            num_gpus: Number of GPUs to allocate (default: 1)
            gpu_memory_limit_per_gpu: Per-GPU memory limit (e.g., "8g")
            
        Returns:
            SessionInfo with connection details
        """
        if not await self._check_docker_available():
            raise RuntimeError(
                "Docker is not available. Please ensure Docker Desktop is installed and running. "
                "On macOS, start Docker Desktop with: open -a Docker"
            )
        
        image = docker_image or self.jupyter_image
        port = self._find_available_port()
        token = secrets.token_urlsafe(32)
        container_name = f"jupyter_{job_id.replace('-', '_')}"
        
        # Build Docker command
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:8888",
            "--memory", memory_limit,
            "--restart", "no",
        ]
        
        # Add GPU access if enabled and available
        if gpu_enabled:
            # Check for NVIDIA GPU (CUDA)
            nvidia_check = await asyncio.create_subprocess_exec(
                "docker", "run", "--rm", "--gpus", "all", "nvidia/cuda:11.8.0-base-ubuntu22.04",
                "nvidia-smi",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await nvidia_check.communicate()
            
            if nvidia_check.returncode == 0:
                # Multi-GPU support with optional per-GPU memory limits
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
                
                logger.info("gpu_enabled_for_session", job_id=job_id, gpu_type="CUDA", num_gpus=num_gpus, 
                           gpu_memory_limit=gpu_memory_limit_per_gpu)
            else:
                # For Apple Silicon (MPS), GPU access works natively in containers
                # MPS doesn't need Docker GPU flags - PyTorch will detect it automatically
                # MPS doesn't support multi-GPU (unified architecture)
                if num_gpus > 1:
                    logger.warning("mps_multi_gpu_not_supported", job_id=job_id, num_gpus=num_gpus, 
                                  note="MPS doesn't support multi-GPU, using single GPU")
                logger.info("gpu_enabled_for_session", job_id=job_id, gpu_type="MPS", num_gpus=1, 
                           note="MPS works natively in containers")
        
        # Add workspace mount
        if workspace_path:
            cmd.extend(["-v", f"{workspace_path}:/home/jovyan/work"])
        
        # Add environment variables
        env_vars = [
            "-e", f"JUPYTER_TOKEN={token}",
            "-e", "JUPYTER_ENABLE_LAB=yes",
        ]
        
        # Add distributed training environment variables for multi-GPU
        if gpu_enabled and num_gpus > 1:
            # Set CUDA visible devices
            cuda_visible = ",".join([str(i) for i in range(num_gpus)])
            env_vars.extend(["-e", f"CUDA_VISIBLE_DEVICES={cuda_visible}"])
            # Set distributed training variables
            env_vars.extend(["-e", "WORLD_SIZE={}".format(num_gpus)])
            env_vars.extend(["-e", "MASTER_ADDR=localhost"])
            env_vars.extend(["-e", "MASTER_PORT=29500"])
            # LOCAL_RANK will be set per process if using torchrun
            logger.info("distributed_env_vars_set", job_id=job_id, num_gpus=num_gpus)
        
        cmd.extend(env_vars)
        
        # Add image and start command
        cmd.extend([
            image,
            "start-notebook.sh",
            "--NotebookApp.token=''",  # Disable token auth, use our own
            "--NotebookApp.password=''",
        ])
        
        logger.info(
            "starting_jupyter_session",
            job_id=job_id,
            port=port,
            image=image
        )
        
        # Start container
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            logger.error("jupyter_start_failed", job_id=job_id, error=error_msg)
            raise RuntimeError(f"Failed to start Jupyter: {error_msg}")
        
        container_id = stdout.decode("utf-8").strip()[:12]
        
        # Wait for Jupyter to be ready
        await self._wait_for_jupyter_ready(port, timeout=30)
        
        # Create session info
        session_url = f"http://{self.public_host}:{port}/lab?token={token}"
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        
        session_info = SessionInfo(
            session_id=session_id,
            job_id=job_id,
            container_id=container_id,
            session_type=JobType.NOTEBOOK_SESSION,
            session_url=session_url,
            session_token=token,
            session_port=port,
            started_at=datetime.utcnow(),
            expires_at=expires_at,
            docker_image=image
        )
        
        self.active_sessions[job_id] = session_info
        self.used_ports.add(port)
        
        logger.info(
            "jupyter_session_started",
            job_id=job_id,
            container_id=container_id,
            port=port,
            expires_at=expires_at.isoformat()
        )
        
        return session_info
    
    async def _wait_for_jupyter_ready(self, port: int, timeout: int = 30) -> None:
        """Wait for Jupyter to be ready to accept connections"""
        import httpx
        
        start_time = datetime.utcnow()
        url = f"http://localhost:{port}/api"
        
        while (datetime.utcnow() - start_time).seconds < timeout:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=2.0)
                    if response.status_code in [200, 401, 403]:
                        logger.debug("jupyter_ready", port=port)
                        return
            except Exception:
                pass
            
            await asyncio.sleep(1)
        
        logger.warning("jupyter_ready_timeout", port=port, timeout=timeout)
    
    async def start_container_session(
        self,
        job_id: str,
        session_id: str,
        docker_image: str,
        timeout_minutes: int = 60,
        gpu_enabled: bool = True,
        memory_limit: str = "8g",
        exposed_port: int = 8080,
        command: Optional[str] = None
    ) -> SessionInfo:
        """
        Start a custom container session
        
        Args:
            job_id: Associated job ID
            session_id: Session record ID
            docker_image: Docker image to run
            timeout_minutes: Session duration
            gpu_enabled: Whether to enable GPU access
            memory_limit: Container memory limit
            exposed_port: Port to expose from container
            command: Optional command to run
            
        Returns:
            SessionInfo with connection details
        """
        if not await self._check_docker_available():
            raise RuntimeError(
                "Docker is not available. Please ensure Docker Desktop is installed and running. "
                "On macOS, start Docker Desktop with: open -a Docker"
            )
        
        port = self._find_available_port()
        token = secrets.token_urlsafe(32)
        container_name = f"container_{job_id.replace('-', '_')}"
        
        # Pull image first
        logger.info("pulling_image", image=docker_image)
        pull_process = await asyncio.create_subprocess_exec(
            "docker", "pull", docker_image,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await pull_process.communicate()
        
        # Build Docker command
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "-p", f"{port}:{exposed_port}",
            "--memory", memory_limit,
            "--restart", "no",
            "-e", f"SESSION_TOKEN={token}",
        ]
        
        # Add GPU access if enabled
        if gpu_enabled:
            nvidia_check = await asyncio.create_subprocess_exec(
                "nvidia-smi",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await nvidia_check.communicate()
            
            if nvidia_check.returncode == 0:
                cmd.extend(["--gpus", "all"])
        
        cmd.append(docker_image)
        
        if command:
            cmd.extend(["sh", "-c", command])
        
        logger.info(
            "starting_container_session",
            job_id=job_id,
            port=port,
            image=docker_image
        )
        
        # Start container
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace")
            logger.error("container_start_failed", job_id=job_id, error=error_msg)
            raise RuntimeError(f"Failed to start container: {error_msg}")
        
        container_id = stdout.decode("utf-8").strip()[:12]
        
        # Create session info
        session_url = f"http://{self.public_host}:{port}"
        expires_at = datetime.utcnow() + timedelta(minutes=timeout_minutes)
        
        session_info = SessionInfo(
            session_id=session_id,
            job_id=job_id,
            container_id=container_id,
            session_type=JobType.CONTAINER_SESSION,
            session_url=session_url,
            session_token=token,
            session_port=port,
            started_at=datetime.utcnow(),
            expires_at=expires_at,
            docker_image=docker_image
        )
        
        self.active_sessions[job_id] = session_info
        self.used_ports.add(port)
        
        logger.info(
            "container_session_started",
            job_id=job_id,
            container_id=container_id,
            port=port
        )
        
        return session_info
    
    async def stop_session(self, job_id: str) -> bool:
        """
        Stop a running session
        
        Args:
            job_id: Job ID of session to stop
            
        Returns:
            True if stopped successfully
        """
        session = self.active_sessions.get(job_id)
        if not session:
            logger.warning("session_not_found", job_id=job_id)
            return False
        
        container_name = f"jupyter_{job_id.replace('-', '_')}" if session.session_type == JobType.NOTEBOOK_SESSION else f"container_{job_id.replace('-', '_')}"
        
        try:
            # Stop container
            stop_process = await asyncio.create_subprocess_exec(
                "docker", "stop", container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await asyncio.wait_for(stop_process.communicate(), timeout=30)
            
            # Remove container
            rm_process = await asyncio.create_subprocess_exec(
                "docker", "rm", container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await rm_process.communicate()
            
            # Clean up tracking
            self.used_ports.discard(session.session_port)
            del self.active_sessions[job_id]
            
            logger.info(
                "session_stopped",
                job_id=job_id,
                container_id=session.container_id
            )
            
            return True
            
        except Exception as e:
            logger.error("session_stop_failed", job_id=job_id, error=str(e))
            return False
    
    async def get_session_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a session
        
        Args:
            job_id: Job ID to check
            
        Returns:
            Status dict or None if not found
        """
        session = self.active_sessions.get(job_id)
        if not session:
            return None
        
        # Check if container is still running
        container_name = f"jupyter_{job_id.replace('-', '_')}" if session.session_type == JobType.NOTEBOOK_SESSION else f"container_{job_id.replace('-', '_')}"
        
        inspect_process = await asyncio.create_subprocess_exec(
            "docker", "inspect", "--format", "{{.State.Status}}", container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, _ = await inspect_process.communicate()
        container_status = stdout.decode("utf-8").strip() if inspect_process.returncode == 0 else "unknown"
        
        # Calculate billing
        elapsed_minutes = int((datetime.utcnow() - session.started_at).total_seconds() / 60)
        
        return {
            "job_id": job_id,
            "session_id": session.session_id,
            "container_id": session.container_id,
            "session_type": session.session_type.value,
            "session_url": session.session_url,
            "session_port": session.session_port,
            "container_status": container_status,
            "started_at": session.started_at.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "elapsed_minutes": elapsed_minutes,
            "time_remaining_minutes": max(0, int((session.expires_at - datetime.utcnow()).total_seconds() / 60))
        }
    
    def get_session_info(self, job_id: str) -> Optional[SessionInfo]:
        """Get session info by job ID"""
        return self.active_sessions.get(job_id)
    
    async def cleanup_expired_sessions(self) -> int:
        """
        Stop all expired sessions
        
        Returns:
            Number of sessions stopped
        """
        now = datetime.utcnow()
        expired = [
            job_id for job_id, session in self.active_sessions.items()
            if session.expires_at < now
        ]
        
        stopped_count = 0
        for job_id in expired:
            if await self.stop_session(job_id):
                stopped_count += 1
        
        if stopped_count > 0:
            logger.info("expired_sessions_cleaned", count=stopped_count)
        
        return stopped_count
    
    def calculate_session_cost(
        self,
        session: SessionInfo,
        price_per_hour: Decimal
    ) -> tuple[int, Decimal]:
        """
        Calculate billing for a session
        
        Args:
            session: Session info
            price_per_hour: Hourly rate
            
        Returns:
            Tuple of (billed_minutes, total_cost_usd)
        """
        elapsed_seconds = (datetime.utcnow() - session.started_at).total_seconds()
        billed_minutes = int(elapsed_seconds / 60) + 1  # Round up
        
        # Price per minute
        price_per_minute = price_per_hour / Decimal("60")
        total_cost = price_per_minute * Decimal(str(billed_minutes))
        
        return billed_minutes, total_cost


# Singleton instance
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Get or create session manager singleton"""
    global _session_manager
    
    if _session_manager is None:
        config = get_seller_config()
        
        _session_manager = SessionManager(
            jupyter_image=config.jupyter_docker_image,
            port_range_start=config.jupyter_port_range_start,
            port_range_end=config.jupyter_port_range_end,
            public_host=config.public_host
        )
    
    return _session_manager

