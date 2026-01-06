"""
Model Versioning
Auto-detects and versions trained models
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


class ModelManager:
    """Manages model detection and versioning"""
    
    # Model file extensions
    MODEL_EXTENSIONS = [".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".h5", ".pb"]
    
    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        "pytorch": [r"\.(pt|pth)$", r"pytorch", r"torch"],
        "tensorflow": [r"\.(pb|h5)$", r"tensorflow", r"tf"],
        "onnx": [r"\.onnx$", r"onnx"],
        "safetensors": [r"\.safetensors$", r"safetensors"]
    }
    
    def __init__(self, job_id: str, workspace_path: Path, buyer_address: str):
        """
        Initialize model manager
        
        Args:
            job_id: Job ID
            workspace_path: Path to workspace directory
            buyer_address: Buyer address (for model ownership)
        """
        self.job_id = job_id
        self.workspace_path = workspace_path
        self.buyer_address = buyer_address
        self.model_dir = workspace_path / "models"
        self.storage = get_storage_client()
        self.db = get_db_client()
        self.uploaded_models: set = set()  # Track uploaded files
    
    def detect_model_files(self) -> List[Path]:
        """
        Detect model files in workspace
        
        Returns:
            List of model file paths
        """
        models = []
        
        # Check dedicated models directory
        if self.model_dir.exists():
            for ext in self.MODEL_EXTENSIONS:
                for file_path in self.model_dir.glob(f"**/*{ext}"):
                    if file_path.is_file():
                        models.append(file_path)
        
        # Also check workspace root for model files
        for ext in self.MODEL_EXTENSIONS:
            for file_path in self.workspace_path.glob(f"*{ext}"):
                if file_path.is_file():
                    models.append(file_path)
        
        # Remove duplicates and filter out already uploaded
        unique_models = []
        for model in models:
            if str(model) not in self.uploaded_models:
                unique_models.append(model)
        
        return unique_models
    
    def detect_framework(self, file_path: Path) -> Optional[str]:
        """
        Detect model framework from filename and extension
        
        Args:
            file_path: Path to model file
            
        Returns:
            Framework name or None
        """
        filename = file_path.name.lower()
        ext = file_path.suffix.lower()
        
        for framework, patterns in self.FRAMEWORK_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename + ext, re.IGNORECASE):
                    return framework
        
        # Default based on extension
        if ext in [".pt", ".pth"]:
            return "pytorch"
        elif ext in [".pb", ".h5"]:
            return "tensorflow"
        elif ext == ".onnx":
            return "onnx"
        elif ext == ".safetensors":
            return "safetensors"
        
        return None
    
    def extract_model_name(self, file_path: Path) -> str:
        """
        Extract model name from file path
        
        Args:
            file_path: Path to model file
            
        Returns:
            Model name
        """
        # Remove extension and path
        name = file_path.stem
        
        # Clean up common patterns
        name = re.sub(r"[-_]?epoch.*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"[-_]?step.*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"[-_]?checkpoint.*$", "", name, flags=re.IGNORECASE)
        name = re.sub(r"[-_]?model.*$", "", name, flags=re.IGNORECASE)
        name = name.strip("-_")
        
        # Default name if empty
        if not name:
            name = "model"
        
        return name
    
    async def get_next_version(self, model_name: str) -> str:
        """
        Get next version for a model (semantic versioning)
        
        Args:
            model_name: Model name
            
        Returns:
            Version string (e.g., "1.0.0")
        """
        # Get existing models for this buyer and name
        existing_models = await self.db.list_models(
            buyer_address=self.buyer_address,
            limit=1000
        )
        
        # Filter by name
        same_name_models = [m for m in existing_models if m.get("name") == model_name]
        
        if not same_name_models:
            return "1.0.0"
        
        # Parse versions and find highest
        max_major = 0
        max_minor = 0
        max_patch = 0
        
        for model in same_name_models:
            version = model.get("version", "1.0.0")
            try:
                parts = version.split(".")
                major = int(parts[0]) if len(parts) > 0 else 0
                minor = int(parts[1]) if len(parts) > 1 else 0
                patch = int(parts[2]) if len(parts) > 2 else 0
                
                if major > max_major:
                    max_major = major
                    max_minor = minor
                    max_patch = patch
                elif major == max_major:
                    if minor > max_minor:
                        max_minor = minor
                        max_patch = patch
                    elif minor == max_minor:
                        if patch > max_patch:
                            max_patch = patch
            except (ValueError, IndexError):
                continue
        
        # Increment patch version
        return f"{max_major}.{max_minor}.{max_patch + 1}"
    
    async def upload_model(self, file_path: Path, model_name: Optional[str] = None, version: Optional[str] = None) -> Optional[str]:
        """
        Upload a model file to storage and save metadata
        
        Args:
            file_path: Path to model file
            model_name: Optional model name (auto-detected if not provided)
            version: Optional version (auto-incremented if not provided)
            
        Returns:
            Model ID if successful, None otherwise
        """
        try:
            # Extract model name if not provided
            if not model_name:
                model_name = self.extract_model_name(file_path)
            
            # Get next version if not provided
            if not version:
                version = await self.get_next_version(model_name)
            
            # Generate storage path
            storage_path = self.storage.generate_storage_path(
                job_id=self.job_id,
                file_name=file_path.name,
                file_type="model"
            )
            
            # Calculate file size and checksum
            file_size = file_path.stat().st_size
            checksum = self._calculate_checksum(file_path)
            
            # Detect framework and format
            framework = self.detect_framework(file_path)
            format_ext = file_path.suffix.lstrip(".")
            
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
            
            # Save model metadata to database
            model_id = await self.db.save_model(
                job_id=self.job_id,
                buyer_address=self.buyer_address,
                name=model_name,
                version=version,
                storage_path=storage_path,
                file_size_bytes=file_size,
                checksum=checksum,
                format=format_ext,
                framework=framework
            )
            
            # Mark as uploaded
            self.uploaded_models.add(str(file_path))
            
            logger.info(
                "model_uploaded",
                model_id=model_id,
                job_id=self.job_id,
                name=model_name,
                version=version,
                file_name=file_path.name,
                file_size=file_size,
                framework=framework
            )
            
            return model_id
            
        except Exception as e:
            logger.error(
                "model_upload_failed",
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
    
    async def scan_and_upload_models(self) -> List[str]:
        """
        Scan workspace for models and upload any new ones
        
        Returns:
            List of model IDs that were uploaded
        """
        models = self.detect_model_files()
        uploaded_ids = []
        
        for model_path in models:
            model_id = await self.upload_model(model_path)
            if model_id:
                uploaded_ids.append(model_id)
        
        if uploaded_ids:
            logger.info(
                "models_scanned_and_uploaded",
                job_id=self.job_id,
                count=len(uploaded_ids)
            )
        
        return uploaded_ids


def create_model_manager(job_id: str, workspace_path: Path, buyer_address: str) -> ModelManager:
    """
    Create a model manager for a job
    
    Args:
        job_id: Job ID
        workspace_path: Workspace directory path
        buyer_address: Buyer address
        
    Returns:
        ModelManager instance
    """
    return ModelManager(job_id, workspace_path, buyer_address)

