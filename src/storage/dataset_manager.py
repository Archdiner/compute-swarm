"""
Dataset Management
Handles dataset versioning, metadata, and sharing
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import structlog

from src.storage.supabase_storage import StorageClient, get_storage_client
from src.database import get_db_client

logger = structlog.get_logger()


class DatasetManager:
    """Manages datasets with versioning and metadata"""
    
    def __init__(self, storage_client: Optional[StorageClient] = None):
        """
        Initialize dataset manager
        
        Args:
            storage_client: Storage client instance (default: get from singleton)
        """
        self.storage = storage_client or get_storage_client()
        self.db = get_db_client()
    
    async def create_dataset(
        self,
        buyer_address: str,
        name: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: bool = False
    ) -> Dict[str, Any]:
        """
        Create a new dataset
        
        Args:
            buyer_address: Owner of the dataset
            name: Dataset name
            description: Optional description
            tags: Optional tags for categorization
            is_public: Whether dataset is publicly shareable
            
        Returns:
            Dataset metadata dict
        """
        dataset_id = str(uuid.uuid4())
        
        dataset_data = {
            "dataset_id": dataset_id,
            "buyer_address": buyer_address,
            "name": name,
            "description": description,
            "tags": tags or [],
            "is_public": is_public,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Store in database (would need datasets table)
        # For now, we'll use storage metadata
        logger.info("dataset_created", dataset_id=dataset_id, name=name, buyer=buyer_address)
        
        return dataset_data
    
    async def upload_dataset_version(
        self,
        dataset_id: str,
        file_path: str,
        version: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a new version of a dataset
        
        Args:
            dataset_id: Dataset ID
            file_path: Local file path to upload
            version: Version string (e.g., "1.0.0", "1.1.0") - auto-increments if not provided
            description: Optional version description
            
        Returns:
            Version metadata dict
        """
        # Generate storage path
        storage_path = self.storage.generate_storage_path(
            job_id=dataset_id,
            file_name=Path(file_path).name,
            file_type="dataset"
        )
        
        # Upload file (use chunked upload for large files)
        file_size = Path(file_path).stat().st_size
        if file_size > 100 * 1024 * 1024:  # > 100MB
            upload_result = await self.storage.upload_chunked(
                file_path=file_path,
                storage_path=storage_path
            )
        else:
            upload_result = await self.storage.upload_file(
                file_path=file_path,
                storage_path=storage_path
            )
        
        # Generate version if not provided (semantic versioning)
        if version is None:
            # Get latest version and increment
            # For now, default to 1.0.0
            version = "1.0.0"
        
        version_data = {
            "dataset_id": dataset_id,
            "version": version,
            "storage_path": storage_path,
            "file_size_bytes": upload_result["file_size_bytes"],
            "checksum": upload_result.get("checksum"),
            "description": description,
            "created_at": datetime.utcnow().isoformat()
        }
        
        logger.info(
            "dataset_version_uploaded",
            dataset_id=dataset_id,
            version=version,
            file_size=upload_result["file_size_bytes"]
        )
        
        return version_data
    
    async def get_dataset(
        self,
        dataset_id: str,
        buyer_address: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get dataset metadata
        
        Args:
            dataset_id: Dataset ID
            buyer_address: Optional buyer address for access control
            
        Returns:
            Dataset metadata or None if not found
        """
        # Would query database for dataset metadata
        # For now, return placeholder
        logger.debug("dataset_retrieved", dataset_id=dataset_id)
        return None
    
    async def list_datasets(
        self,
        buyer_address: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: Optional[bool] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List datasets with optional filtering
        
        Args:
            buyer_address: Filter by owner (None = all accessible)
            tags: Filter by tags
            is_public: Filter by public/private
            limit: Maximum number of results
            
        Returns:
            List of dataset metadata dicts
        """
        # Would query database
        # For now, return empty list
        logger.debug("datasets_listed", buyer=buyer_address, tags=tags, limit=limit)
        return []
    
    async def get_dataset_version(
        self,
        dataset_id: str,
        version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get specific dataset version
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            
        Returns:
            Version metadata or None if not found
        """
        logger.debug("dataset_version_retrieved", dataset_id=dataset_id, version=version)
        return None
    
    async def list_dataset_versions(
        self,
        dataset_id: str
    ) -> List[Dict[str, Any]]:
        """
        List all versions of a dataset
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            List of version metadata dicts
        """
        logger.debug("dataset_versions_listed", dataset_id=dataset_id)
        return []
    
    async def download_dataset_version(
        self,
        dataset_id: str,
        version: str,
        destination_path: str
    ) -> str:
        """
        Download a dataset version
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            destination_path: Local destination path
            
        Returns:
            Local file path
        """
        # Get version metadata to find storage path
        version_data = await self.get_dataset_version(dataset_id, version)
        if not version_data:
            raise ValueError(f"Dataset version not found: {dataset_id}@{version}")
        
        storage_path = version_data["storage_path"]
        
        # Download from storage
        local_path = await self.storage.download_file(
            storage_path=storage_path,
            destination_path=destination_path
        )
        
        logger.info(
            "dataset_version_downloaded",
            dataset_id=dataset_id,
            version=version,
            destination=local_path
        )
        
        return local_path
    
    def generate_storage_path_for_dataset(
        self,
        dataset_id: str,
        version: str,
        file_name: str
    ) -> str:
        """
        Generate storage path for dataset file
        
        Args:
            dataset_id: Dataset ID
            version: Version string
            file_name: Original file name
            
        Returns:
            Storage path
        """
        return f"datasets/{dataset_id}/{version}/{file_name}"


# Singleton instance
_dataset_manager: Optional[DatasetManager] = None


def get_dataset_manager() -> DatasetManager:
    """Get or create dataset manager singleton"""
    global _dataset_manager
    
    if _dataset_manager is None:
        _dataset_manager = DatasetManager()
    
    return _dataset_manager

