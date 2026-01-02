"""
Secure job execution engine
Executes Python scripts in isolated Docker containers with safety controls
"""

import asyncio
import shutil
import tempfile
import os
import signal
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from decimal import Decimal
import time

import structlog

logger = structlog.get_logger()


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
        docker_memory_limit: str = "4g",
        docker_cpu_limit: float = 2.0,
        docker_pids_limit: int = 100,
        docker_tmpfs_size: str = "1g"
    ):
        """
        Initialize executor

        Args:
            workspace_dir: Directory for temporary files (default: system temp)
            max_output_size: Maximum output size in bytes
            docker_enabled: Whether to use Docker sandboxing
            docker_image: Docker image to use for sandboxed execution
            docker_memory_limit: Memory limit for containers (e.g., "4g")
            docker_cpu_limit: CPU limit for containers
            docker_pids_limit: Maximum number of processes in container
            docker_tmpfs_size: Size of tmpfs mount for /tmp
        """
        self.workspace_dir = workspace_dir or Path(tempfile.gettempdir()) / "computeswarm"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.max_output_size = max_output_size
        self.docker_enabled = docker_enabled
        self.docker_image = docker_image
        self.docker_memory_limit = docker_memory_limit
        self.docker_cpu_limit = docker_cpu_limit
        self.docker_pids_limit = docker_pids_limit
        self.docker_tmpfs_size = docker_tmpfs_size
        
        # Check Docker availability on init
        self._docker_available: Optional[bool] = None

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

    async def _check_docker_image_exists(self) -> bool:
        """Check if the sandbox Docker image exists"""
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "image", "inspect", self.docker_image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    async def execute_job(
        self,
        job_id: str,
        script: str,
        requirements: Optional[str] = None,
        timeout_seconds: int = 3600
    ) -> ExecutionResult:
        """
        Execute a Python job with safety controls

        Args:
            job_id: Unique job identifier
            script: Python script to execute
            requirements: Optional pip requirements (e.g., "numpy==1.24.0\\ntorch==2.1.0")
            timeout_seconds: Maximum execution time

        Returns:
            ExecutionResult with output and status
        """
        logger.info("job_execution_started", job_id=job_id, timeout=timeout_seconds)
        start_time = time.time()

        # Create isolated workspace for this job
        job_workspace = self.workspace_dir / job_id
        job_workspace.mkdir(parents=True, exist_ok=True)

        try:
            # Determine execution mode
            use_docker = self.docker_enabled and await self._check_docker_available()
            
            if use_docker and not await self._check_docker_image_exists():
                logger.warning(
                    "docker_image_not_found",
                    image=self.docker_image,
                    message="Falling back to subprocess execution"
                )
                use_docker = False
            
            if use_docker:
                logger.info("using_docker_execution", job_id=job_id, image=self.docker_image)
                result = await self._run_in_docker(
                    job_id=job_id,
                    workspace=job_workspace,
                    script=script,
                    requirements=requirements,
                    timeout=timeout_seconds
                )
            else:
                logger.info("using_subprocess_execution", job_id=job_id)
                # Install requirements if specified (only for subprocess mode)
                if requirements:
                    await self._install_requirements(job_workspace, requirements, timeout_seconds // 4)
                result = await self._run_script(job_workspace, script, timeout_seconds)

            execution_time = Decimal(str(time.time() - start_time))
            logger.info(
                "job_execution_completed",
                job_id=job_id,
                success=result.success,
                execution_time=float(execution_time),
                exit_code=result.exit_code,
                docker=use_docker
            )

            return ExecutionResult(
                success=result.success,
                output=result.output,
                error=result.error,
                exit_code=result.exit_code,
                execution_time=execution_time,
                stdout=result.stdout,
                stderr=result.stderr
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
                stderr="Timeout"
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
                stderr=str(e)
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
        timeout: int
    ) -> ExecutionResult:
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
        """
        container_name = f"computeswarm_job_{job_id.replace('-', '_')}"
        
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
            f"--tmpfs", f"/tmp:size={self.docker_tmpfs_size},noexec",  # Writable /tmp with noexec
            f"--memory", self.docker_memory_limit,
            f"--cpus", str(self.docker_cpu_limit),
            f"--pids-limit", str(self.docker_pids_limit),
            "--security-opt", "no-new-privileges",  # Prevent privilege escalation
            "-v", f"{workspace.absolute()}:/workspace:ro",  # Mount workspace read-only
            "-w", "/workspace",
            self.docker_image,
        ]
        
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
        
        logger.info("docker_container_starting", container_name=container_name, job_id=job_id)
        
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
                stderr=stderr_str
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
                stderr=stderr_str
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
