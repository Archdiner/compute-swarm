"""
Job Manager for ComputeSwarm
Manages the lifecycle of jobs, state transitions, and execution delegation.
"""

import asyncio
import time
from enum import Enum
from typing import Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

import structlog

from src.execution.engine import JobExecutor, ExecutionResult

logger = structlog.get_logger()

class JobState(Enum):
    """Lifecycle states for a compute job"""
    CLAIMED = "claimed"         # Job claimed from marketplace
    PREPARING = "preparing"     # Setting up environment (Docker pull, models)
    RUNNING = "running"         # Script execution in progress
    COMPLETING = "completing"   # execution done, processing results/payments
    COMPLETED = "completed"     # Successfully finished and reported
    FAILED = "failed"           # Execution failed or error occurred
    CANCELLED = "cancelled"     # Cancelled by user or timeout

@dataclass
class JobContext:
    """Context holding all data for a single job"""
    job_id: str
    buyer_address: str
    script: str
    requirements: Optional[str]
    timeout_seconds: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    state: JobState = JobState.CLAIMED
    result: Optional[ExecutionResult] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Resource requirements
    num_gpus: int = 1
    gpu_memory_limit_per_gpu: Optional[str] = None

class JobManager:
    """
    Manages job lifecycle and state transitions.
    """
    
    def __init__(self, executor: JobExecutor):
        self.executor = executor
        self.jobs: Dict[str, JobContext] = {}
        self.active_job_id: Optional[str] = None
        self._state_lock = asyncio.Lock()

    async def create_job(
        self, 
        job_id: str, 
        buyer_address: str,
        script: str, 
        requirements: Optional[str] = None,
        timeout_seconds: int = 3600,
        num_gpus: int = 1,
        gpu_memory_limit_per_gpu: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ) -> JobContext:
        """Register a new job in CLAIMED state"""
        async with self._state_lock:
            if job_id in self.jobs:
                raise ValueError(f"Job {job_id} already exists")
            
            job = JobContext(
                job_id=job_id,
                buyer_address=buyer_address,
                script=script,
                requirements=requirements,
                timeout_seconds=timeout_seconds,
                num_gpus=num_gpus,
                gpu_memory_limit_per_gpu=gpu_memory_limit_per_gpu,
                metadata=metadata or {}
            )
            self.jobs[job_id] = job
            logger.info("job_manager_job_created", job_id=job_id, state=job.state.value)
            return job

    async def run_job(self, job_id: str) -> ExecutionResult:
        """
        Execute the job through its lifecycle.
        Transitions: CLAIMED -> PREPARING -> RUNNING -> COMPLETED/FAILED
        """
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
            
        # 1. PREPARING
        await self._transition_state(job, JobState.PREPARING)
        self.active_job_id = job_id
        
        try:
            # 2. RUNNING
            await self._transition_state(job, JobState.RUNNING)
            job.started_at = datetime.utcnow()
            
            # Execute logic
            result = await self.executor.execute_job(
                job_id=job.job_id,
                script=job.script,
                requirements=job.requirements,
                timeout_seconds=job.timeout_seconds,
                num_gpus=job.num_gpus,
                gpu_memory_limit_per_gpu=job.gpu_memory_limit_per_gpu,
                buyer_address=job.buyer_address
            )
            job.result = result
            job.ended_at = datetime.utcnow()

            # 3. COMPLETING / FAILED
            if result.success:
                await self._transition_state(job, JobState.COMPLETED)
            else:
                await self._transition_state(job, JobState.FAILED)
                
            return result
            
        except asyncio.CancelledError:
            await self._transition_state(job, JobState.CANCELLED)
            job.ended_at = datetime.utcnow()
            raise
            
        except Exception as e:
            logger.error("job_manager_execution_error", job_id=job_id, error=str(e))
            await self._transition_state(job, JobState.FAILED)
            raise
            
        finally:
            if self.active_job_id == job_id:
                self.active_job_id = None

    async def _transition_state(self, job: JobContext, new_state: JobState):
        """Handle state transitions safely"""
        old_state = job.state
        job.state = new_state
        logger.info(
            "job_state_transition", 
            job_id=job.job_id, 
            from_state=old_state.value, 
            to_state=new_state.value
        )
        # Here we could emit events or callbacks if needed

    def get_job(self, job_id: str) -> Optional[JobContext]:
        return self.jobs.get(job_id)
        
    def get_active_job(self) -> Optional[JobContext]:
        if self.active_job_id:
            return self.jobs.get(self.active_job_id)
        return None
