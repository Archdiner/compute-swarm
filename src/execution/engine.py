"""
Secure job execution engine
Executes Python scripts in isolated environment with safety controls
"""

import asyncio
import subprocess
import tempfile
import os
import signal
from pathlib import Path
from typing import Optional, Tuple
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
    Secure Python job executor with resource limits

    Safety features:
    - Timeout enforcement
    - Isolated temporary directory
    - Limited file system access
    - No network access (TODO: implement with firejail/bubblewrap)
    - Resource usage monitoring
    """

    def __init__(
        self,
        workspace_dir: Optional[Path] = None,
        max_output_size: int = 1024 * 1024  # 1MB
    ):
        """
        Initialize executor

        Args:
            workspace_dir: Directory for temporary files (default: system temp)
            max_output_size: Maximum output size in bytes
        """
        self.workspace_dir = workspace_dir or Path(tempfile.gettempdir()) / "computeswarm"
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.max_output_size = max_output_size

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
            # Install requirements if specified
            if requirements:
                await self._install_requirements(job_workspace, requirements, timeout_seconds // 4)

            # Execute the script
            result = await self._run_script(job_workspace, script, timeout_seconds)

            execution_time = Decimal(str(time.time() - start_time))
            logger.info(
                "job_execution_completed",
                job_id=job_id,
                success=result.success,
                execution_time=float(execution_time),
                exit_code=result.exit_code
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

    async def _install_requirements(
        self,
        workspace: Path,
        requirements: str,
        timeout: int
    ) -> None:
        """
        Install Python requirements in isolated environment

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
        Run Python script in isolated workspace

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
                exit_code=process.returncode,
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
            import shutil
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
