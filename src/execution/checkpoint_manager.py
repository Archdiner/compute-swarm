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
    
    # Common checkpoint file patterns (glob style)
    CHECKPOINT_GLOBS = [
        "**/checkpoint*.[pP][tT]",
        "**/checkpoint*.[pP][tT][hH]",
        "**/checkpoint*.[cC][kK][pP][tT]",
        "**/*.safetensors",
        "**/*epoch*.[pP][tT]*",
        "**/*step*.[pP][tT]*",
        "**/pytorch_model.bin",
        "**/adapter_model.safetensors"
    ]
    
    def __init__(self, job_id: str, workspace_path: Path, p2p_upload_dir: Optional[Path] = None):
        """
        Initialize checkpoint manager
        
        Args:
            job_id: Job ID
            workspace_path: Path to workspace directory
            p2p_upload_dir: Path to copy checkpoints for P2P delivery
        """
        self.job_id = job_id
        self.workspace_path = workspace_path
        self.checkpoint_dir = workspace_path / "checkpoints"
        self.p2p_upload_dir = p2p_upload_dir
        # Lazy-loaded storage and db clients (to avoid errors when not configured)
        self._storage = None
        self._db = None
        self.uploaded_checkpoints: set = set()  # Track uploaded files
    
    @property
    def storage(self):
        if self._storage is None:
            self._storage = get_storage_client()
        return self._storage
    
    @property
    def db(self):
        if self._db is None:
            self._db = get_db_client()
        return self._db

    
    def detect_checkpoint_files(self) -> List[Path]:
        """
        Detect checkpoint files in workspace using glob patterns
        
        Returns:
            List of checkpoint file paths
        """
        checkpoints = []
        all_files = list(self.workspace_path.glob("**/*"))
        with open("debug_scan.log", "a") as f:
            f.write(f"\n--- SCAN for {self.job_id} ---\n")
            f.write(f"Workspace: {self.workspace_path}\n")
            f.write(f"Total files found: {len(all_files)}\n")
            for fl in all_files:
                f.write(f"  {fl}\n")

        for pattern in self.CHECKPOINT_GLOBS:
            found = list(self.workspace_path.glob(pattern))
            if found:
                with open("debug_scan.log", "a") as f:
                    f.write(f"Pattern {pattern} matched: {[str(x) for x in found]}\n")
            for file_path in found:
                if file_path.is_file():
                    checkpoints.append(file_path)
        
        # Remove duplicates and filter out already uploaded
        unique_checkpoints = []
        seen = set()
        for cp in checkpoints:
            cp_str = str(cp)
            if cp_str not in self.uploaded_checkpoints and cp_str not in seen:
                unique_checkpoints.append(cp)
                seen.add(cp_str)
        
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
        Upload a checkpoint file to storage and save metadata.
        P2P copy happens first for guaranteed local delivery.
        
        Args:
            file_path: Path to checkpoint file
            
        Returns:
            Checkpoint ID if successful, None otherwise
        """
        checkpoint_id = None
        
        try:
            # Calculate file size and checksum
            file_size = file_path.stat().st_size
            checksum = self._calculate_checksum(file_path)
            
            # P2P FIRST: Copy to P2P storage area for immediate swarm delivery
            # This is independent of central storage for local/swarm robustness
            p2p_filename = None
            if self.p2p_upload_dir:
                try:
                    import shutil
                    self.p2p_upload_dir.mkdir(parents=True, exist_ok=True)
                    p2p_filename = f"{self.job_id}_{file_path.name}"
                    p2p_path = self.p2p_upload_dir / p2p_filename
                    shutil.copy2(file_path, p2p_path)
                    logger.info("checkpoint_prepared_for_p2p", 
                               job_id=self.job_id, 
                               p2p_path=str(p2p_path),
                               filename=p2p_filename)
                    checkpoint_id = f"p2p_{self.job_id}"
                except Exception as e:
                    logger.warning("p2p_checkpoint_copy_failed", job_id=self.job_id, error=str(e))
            
            # Central storage (best-effort, wrapped in try-except)
            storage_path = None
            try:
                storage_path = self.storage.generate_storage_path(
                    job_id=self.job_id,
                    file_name=file_path.name,
                    file_type="checkpoint"
                )
                await self.storage.upload_file(
                    file_path=str(file_path),
                    storage_path=storage_path
                )
            except Exception as e:
                logger.warning("central_storage_upload_failed", job_id=self.job_id, error=str(e))
                storage_path = None
            
            # Parse metadata from filename
            metadata = self.parse_checkpoint_metadata(file_path)
            
            # Save checkpoint metadata to database if possible
            try:
                db_checkpoint_id = await self.db.save_checkpoint(
                    job_id=self.job_id,
                    storage_path=storage_path or f"p2p://{self.job_id}/{file_path.name}",
                    file_size_bytes=file_size,
                    checkpoint_name=file_path.name,
                    epoch=metadata.get("epoch"),
                    step=metadata.get("step"),
                    loss=metadata.get("loss"),
                    checksum=checksum
                )
                if db_checkpoint_id:
                    checkpoint_id = db_checkpoint_id
            except Exception as e:
                logger.warning("db_checkpoint_save_failed", job_id=self.job_id, error=str(e))
            
            # Mark as uploaded (at least attempted/P2P)
            self.uploaded_checkpoints.add(str(file_path))
            
            logger.info(
                "checkpoint_processed",
                checkpoint_id=checkpoint_id,
                job_id=self.job_id,
                file_name=file_path.name,
                p2p_ready=bool(self.p2p_upload_dir and p2p_filename)
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


def create_checkpoint_manager(
    job_id: str, 
    workspace_path: Path, 
    p2p_upload_dir: Optional[Path] = None
) -> CheckpointManager:
    """
    Create a checkpoint manager for a job
    
    Args:
        job_id: Job ID
        workspace_path: Workspace directory path
        p2p_upload_dir: Path to copy checkpoints for P2P delivery
        
    Returns:
        CheckpointManager instance
    """
    return CheckpointManager(job_id, workspace_path, p2p_upload_dir)

