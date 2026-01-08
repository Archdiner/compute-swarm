"""
Unit tests for JobManager State Machine
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from src.execution.job_manager import JobManager, JobState
from src.execution.engine import JobExecutor, ExecutionResult

@pytest.fixture
def mock_executor():
    executor = MagicMock(spec=JobExecutor)
    executor.execute_job = AsyncMock()
    return executor

@pytest.fixture
def job_manager(mock_executor):
    return JobManager(executor=mock_executor)

@pytest.mark.asyncio
async def test_create_job(job_manager):
    job = await job_manager.create_job(
        job_id="test-job-1",
        buyer_address="0x123",
        script="print('hello')",
        timeout_seconds=60
    )
    
    assert job.job_id == "test-job-1"
    assert job.state == JobState.CLAIMED
    assert job_manager.get_job("test-job-1") == job

@pytest.mark.asyncio
async def test_run_job_success(job_manager, mock_executor):
    # Setup
    job = await job_manager.create_job(
        job_id="test-job-2",
        buyer_address="0x123",
        script="print('hello')"
    )
    
    # Mock successful execution
    mock_executor.execute_job.return_value = ExecutionResult(
        success=True,
        output="hello",
        error="",
        exit_code=0,
        execution_time=1.0,
        stdout="hello",
        stderr="",
        metrics_collector=None
    )
    
    # Run
    result = await job_manager.run_job("test-job-2")
    
    assert result.success is True
    assert job.state == JobState.COMPLETED
    assert job.started_at is not None
    assert job.ended_at is not None

@pytest.mark.asyncio
async def test_run_job_failure(job_manager, mock_executor):
    # Setup
    job = await job_manager.create_job(
        job_id="test-job-3",
        buyer_address="0x123",
        script="raise Exception('boom')"
    )
    
    # Mock failed execution
    mock_executor.execute_job.return_value = ExecutionResult(
        success=False,
        output="",
        error="boom",
        exit_code=1,
        execution_time=1.0,
        stdout="",
        stderr="boom",
        metrics_collector=None
    )
    
    # Run
    result = await job_manager.run_job("test-job-3")
    
    assert result.success is False
    assert job.state == JobState.FAILED

@pytest.mark.asyncio
async def test_get_nonexistent_job(job_manager):
    assert job_manager.get_job("fake-id") is None
    with pytest.raises(ValueError):
        await job_manager.run_job("fake-id")
