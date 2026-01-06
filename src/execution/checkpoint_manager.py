"""
Checkpoint Management
Auto-detects and uploads training checkpoints
"""

import re
import hashlib
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import structlog

from src.storage import get_storage_client
from src.database import get_db_client

logger = structlog.get_logger()


class CheckpointManager:
    """Manages checkpoint detection and upload"""
    
    # Common checkpoint file patterns
    CHECKPOINT_PATTERNS = [
        r"checkpoint.*\.(pt|pth|ckpt|safetensors)",
        r"model.*\.(pt|pth|ckpt|safetensors)",
        r".*epoch.*\.(pt|pth|ckpt|safetensors)",
        r".*step.*\.(pt|pth|ckpt|safetensors)",
    ]
    
    def __init__(self, job_id: str, workspace_path: Path):
        """
        Initialize checkpoint manager
        
        Args:
            job_id: Job ID
            workspace_path: Path to workspace directory
        """
        self.job_id = job_id
        self.workspace_path = workspace_path
        self.checkpoint_dir = workspace_path / "checkpoints"
        self.storage = get_storage_client()
        self.db = get_db_client()
        self.uploaded_checkpoints: set = set()  # Track uploaded files
    
    def detect_checkpoint_files(self) -> List[Path]:
        """
        Detect checkpoint files in workspace
        
        Returns:
            List of checkpoint file paths
        """
        checkpoints = []
        
        # Check dedicated checkpoints directory
        if self.checkpoint_dir.exists():
            for pattern in self.CHECKPOINT_PATTERNS:
                for file_path in self.checkpoint_dir.glob("**/*"):
                    if file_path.is_file() and re.search(pattern, file_path.name, re.IGNORECASE):
                        checkpoints.append(file_path)
        
        # Also check workspace root for checkpoint files
        for pattern in self.CHECKPOINT_PATTERNS:
            for file_path in self.workspace_path.glob("*"):
                if file_path.is_file() and re.search(pattern, file_path.name, re.IGNORECASE):
                    checkpoints.append(file_path)
        
        # Remove duplicates and filter out already uploaded
        unique_checkpoints = []
        for cp in checkpoints:
            if str(cp) not in self.uploaded_checkpoints:
                unique_checkpoints.append(cp)
        
        return unique_checkpoints
    
    def parse_checkpoint_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse metadata from checkpoint filename
        
        Args:
            file_path: Path to checkpoint file
            
        Returns:
            Dict with epoch, step, loss if found in filename
        """
        filename = file_path.name
        metadata = {}
        
        # Try to extract epoch
        epoch_match = re.search(r"epoch[_-]?(\d+)", filename, re.IGNORECASE)
        if epoch_match:
            try:
                metadata["epoch"] = int(epoch_match.group(1))
            except ValueError:
                pass
        
        # Try to extract step
        step_match = re.search(r"step[_-]?(\d+)", filename, re.IGNORECASE)
        if step_match:
            try:
                metadata["step"] = int(step_match.group(1))
            except ValueError:
                pass
        
        # Try to extract loss
        loss_match = re.search(r"loss[_-]?([0-9]+\.[0-9]+)", filename, re.IGNORECASE)
        if loss_match:
            try:
                metadata["loss"] = float(loss_match.group(1))
            except ValueError:
                pass
        
        return metadata
    
    async def upload_checkpoint(self, file_path: Path) -> Optional[str]:
        """
        Upload a checkpoint file to storage and save metadata
        
        Args:
            file_path: Path to checkpoint file
            
        Returns:
            Checkpoint ID if successful, None otherwise
        """
        try:
            # Generate storage path
            storage_path = self.storage.generate_storage_path(
                job_id=self.job_id,
                file_name=file_path.name,
                file_type="checkpoint"
            )
            
            # Calculate file size and checksum
            file_size = file_path.stat().st_size
            checksum = self._calculate_checksum(file_path)
            
            # Upload file (use chunked upload for large files)
            if file_size > 100 * 1024 * 1024:  # > 100MB
                await self.storage.upload_chunked(
                    file_path=str(file_path),
                    storage_path=storage_path
                )
            else:
                await self.storage.upload_file(
                    file_path=str(file_path),
                    storage_path=storage_path
                )
            
            # Parse metadata from filename
            metadata = self.parse_checkpoint_metadata(file_path)
            
            # Save checkpoint metadata to database
            checkpoint_id = await self.db.save_checkpoint(
                job_id=self.job_id,
                storage_path=storage_path,
                file_size_bytes=file_size,
                checkpoint_name=file_path.name,
                epoch=metadata.get("epoch"),
                step=metadata.get("step"),
                loss=metadata.get("loss"),
                checksum=checksum
            )
            
            # Mark as uploaded
            self.uploaded_checkpoints.add(str(file_path))
            
            logger.info(
                "checkpoint_uploaded",
                checkpoint_id=checkpoint_id,
                job_id=self.job_id,
                file_name=file_path.name,
                file_size=file_size,
                epoch=metadata.get("epoch"),
                step=metadata.get("step")
            )
            
            return checkpoint_id
            
        except Exception as e:
            logger.error(
                "checkpoint_upload_failed",
                job_id=self.job_id,
                file_path=str(file_path),
                error=str(e)
            )
            return None
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    async def scan_and_upload_checkpoints(self) -> List[str]:
        """
        Scan workspace for checkpoints and upload any new ones
        
        Returns:
            List of checkpoint IDs that were uploaded
        """
        checkpoints = self.detect_checkpoint_files()
        uploaded_ids = []
        
        for checkpoint_path in checkpoints:
            checkpoint_id = await self.upload_checkpoint(checkpoint_path)
            if checkpoint_id:
                uploaded_ids.append(checkpoint_id)
        
        if uploaded_ids:
            logger.info(
                "checkpoints_scanned_and_uploaded",
                job_id=self.job_id,
                count=len(uploaded_ids)
            )
        
        return uploaded_ids


def create_checkpoint_manager(job_id: str, workspace_path: Path) -> CheckpointManager:
    """
    Create a checkpoint manager for a job
    
    Args:
        job_id: Job ID
        workspace_path: Workspace directory path
        
    Returns:
        CheckpointManager instance
    """
    return CheckpointManager(job_id, workspace_path)

