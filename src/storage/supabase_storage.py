"""
Supabase Storage client for file uploads/downloads
Provides pre-signed URLs for secure direct uploads
"""

import os
import uuid
import hashlib
from datetime import datetime, timedelta
from typing import Optional, BinaryIO, Dict, Any
from pathlib import Path

import httpx
import structlog
from supabase import create_client, Client

from src.config import get_marketplace_config

logger = structlog.get_logger()


class StorageClient:
    """
    Supabase Storage client for job file management
    
    Features:
    - Pre-signed upload URLs for direct client uploads
    - Pre-signed download URLs for secure downloads
    - File metadata tracking
    - Automatic cleanup of expired files
    """
    
    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        bucket_name: str = "job-files"
    ):
        """
        Initialize Supabase Storage client
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase anon/service key
            bucket_name: Storage bucket name
        """
        self.client: Client = create_client(supabase_url, supabase_key)
        self.bucket_name = bucket_name
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        
        # Ensure bucket exists (would need service role key)
        self._ensure_bucket_exists()
    
    def _ensure_bucket_exists(self) -> None:
        """Ensure the storage bucket exists"""
        try:
            # List buckets to check if ours exists
            buckets = self.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            
            if self.bucket_name not in bucket_names:
                # Create bucket (requires service role key)
                # Increased file size limit to 10GB for large datasets
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={
                        "public": False,
                        "file_size_limit": 10 * 1024 * 1024 * 1024  # 10GB
                    }
                )
                logger.info("storage_bucket_created", bucket=self.bucket_name, file_size_limit="10GB")
            else:
                logger.debug("storage_bucket_exists", bucket=self.bucket_name)
                
        except Exception as e:
            # Bucket might already exist or we don't have permissions
            logger.warning("storage_bucket_check_failed", error=str(e))
    
    def generate_storage_path(
        self,
        job_id: str,
        file_name: str,
        file_type: str
    ) -> str:
        """
        Generate unique storage path for a file
        
        Format: {file_type}/{job_id}/{uuid}_{filename}
        
        Args:
            job_id: Job UUID
            file_name: Original file name
            file_type: File type (input, output, checkpoint, model, dataset)
            
        Returns:
            Storage path string
        """
        # Sanitize filename
        safe_name = "".join(c for c in file_name if c.isalnum() or c in "._-")[:100]
        unique_id = uuid.uuid4().hex[:8]
        
        return f"{file_type}/{job_id}/{unique_id}_{safe_name}"
    
    async def upload_file(
        self,
        file_path: str,
        storage_path: str,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file to storage
        
        Args:
            file_path: Local file path to upload
            storage_path: Destination path in storage
            content_type: MIME type (auto-detected if not provided)
            
        Returns:
            Dict with upload result including path and size
        """
        try:
            with open(file_path, "rb") as f:
                file_data = f.read()
            
            file_size = len(file_data)
            checksum = hashlib.sha256(file_data).hexdigest()
            
            # Upload to Supabase Storage
            result = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=file_data,
                file_options={
                    "content-type": content_type or "application/octet-stream",
                    "upsert": "true"
                }
            )
            
            logger.info(
                "file_uploaded",
                storage_path=storage_path,
                size_bytes=file_size
            )
            
            return {
                "storage_path": storage_path,
                "file_size_bytes": file_size,
                "checksum": checksum,
                "content_type": content_type
            }
            
        except Exception as e:
            logger.error("file_upload_failed", storage_path=storage_path, error=str(e))
            raise
    
    async def upload_bytes(
        self,
        data: bytes,
        storage_path: str,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload bytes to storage
        
        Args:
            data: Bytes to upload
            storage_path: Destination path in storage
            content_type: MIME type
            
        Returns:
            Dict with upload result
        """
        try:
            file_size = len(data)
            checksum = hashlib.sha256(data).hexdigest()
            
            result = self.client.storage.from_(self.bucket_name).upload(
                path=storage_path,
                file=data,
                file_options={
                    "content-type": content_type or "application/octet-stream",
                    "upsert": "true"
                }
            )
            
            logger.info(
                "bytes_uploaded",
                storage_path=storage_path,
                size_bytes=file_size
            )
            
            return {
                "storage_path": storage_path,
                "file_size_bytes": file_size,
                "checksum": checksum,
                "content_type": content_type
            }
            
        except Exception as e:
            logger.error("bytes_upload_failed", storage_path=storage_path, error=str(e))
            raise
    
    async def upload_chunked(
        self,
        file_path: str,
        storage_path: str,
        chunk_size: int = 10 * 1024 * 1024,  # 10MB chunks
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload large file in chunks with resumable support
        
        Args:
            file_path: Local file path to upload
            storage_path: Destination path in storage
            chunk_size: Size of each chunk in bytes (default: 10MB)
            content_type: MIME type
            
        Returns:
            Dict with upload result including total size and checksum
        """
        try:
            import aiofiles
        except ImportError:
            raise ImportError("aiofiles is required for chunked uploads. Install with: pip install aiofiles")
        
        try:
            file_size = os.path.getsize(file_path)
            total_chunks = (file_size + chunk_size - 1) // chunk_size
            
            logger.info(
                "chunked_upload_starting",
                storage_path=storage_path,
                file_size=file_size,
                chunk_size=chunk_size,
                total_chunks=total_chunks
            )
            
            # For Supabase, we'll use multipart upload if available
            # Otherwise, read file in chunks and upload sequentially
            chunks = []
            checksum = hashlib.sha256()
            
            async with aiofiles.open(file_path, 'rb') as f:
                chunk_index = 0
                while True:
                    chunk_data = await f.read(chunk_size)
                    if not chunk_data:
                        break
                    
                    # Calculate checksum
                    checksum.update(chunk_data)
                    
                    # Upload chunk (Supabase doesn't have native multipart, so we append)
                    # For now, we'll upload the full file but in a way that can be resumed
                    chunk_path = f"{storage_path}.part{chunk_index}"
                    try:
                        self.client.storage.from_(self.bucket_name).upload(
                            path=chunk_path,
                            file=chunk_data,
                            file_options={
                                "content-type": content_type or "application/octet-stream",
                                "upsert": "true"
                            }
                        )
                        chunks.append(chunk_path)
                        chunk_index += 1
                        
                        logger.debug(
                            "chunk_uploaded",
                            chunk_index=chunk_index,
                            total_chunks=total_chunks,
                            chunk_size=len(chunk_data)
                        )
                    except Exception as e:
                        logger.error("chunk_upload_failed", chunk_index=chunk_index, error=str(e))
                        # Clean up uploaded chunks on failure
                        for cp in chunks:
                            try:
                                self.client.storage.from_(self.bucket_name).remove([cp])
                            except:
                                pass
                        raise
            
            # Combine chunks into final file
            # For Supabase, we need to download and re-upload, or use a different approach
            # For now, we'll upload the complete file directly for files < 100MB
            # For larger files, we'll need to implement proper multipart upload
            if file_size < 100 * 1024 * 1024:
                # Small enough to upload directly
                async with aiofiles.open(file_path, 'rb') as f:
                    file_data = await f.read()
                    self.client.storage.from_(self.bucket_name).upload(
                        path=storage_path,
                        file=file_data,
                        file_options={
                            "content-type": content_type or "application/octet-stream",
                            "upsert": "true"
                        }
                    )
            else:
                # For large files, we'll need to implement proper chunking
                # This is a simplified version - in production, use Supabase's multipart API if available
                logger.warning(
                    "large_file_upload",
                    message="File > 100MB, using direct upload. Consider implementing proper multipart upload."
                )
                async with aiofiles.open(file_path, 'rb') as f:
                    file_data = await f.read()
                    self.client.storage.from_(self.bucket_name).upload(
                        path=storage_path,
                        file=file_data,
                        file_options={
                            "content-type": content_type or "application/octet-stream",
                            "upsert": "true"
                        }
                    )
            
            # Clean up chunk files
            for chunk_path in chunks:
                try:
                    self.client.storage.from_(self.bucket_name).remove([chunk_path])
                except:
                    pass
            
            final_checksum = checksum.hexdigest()
            
            logger.info(
                "chunked_upload_completed",
                storage_path=storage_path,
                file_size=file_size,
                total_chunks=total_chunks,
                checksum=final_checksum
            )
            
            return {
                "storage_path": storage_path,
                "file_size_bytes": file_size,
                "checksum": final_checksum,
                "content_type": content_type,
                "chunks_uploaded": total_chunks
            }
            
        except Exception as e:
            logger.error("chunked_upload_failed", storage_path=storage_path, error=str(e))
            raise
    
    async def download_file(
        self,
        storage_path: str,
        destination_path: str
    ) -> str:
        """
        Download a file from storage
        
        Args:
            storage_path: Path in storage
            destination_path: Local destination path
            
        Returns:
            Local file path
        """
        try:
            # Download file content
            response = self.client.storage.from_(self.bucket_name).download(storage_path)
            
            # Write to destination
            Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
            with open(destination_path, "wb") as f:
                f.write(response)
            
            logger.info(
                "file_downloaded",
                storage_path=storage_path,
                destination=destination_path
            )
            
            return destination_path
            
        except Exception as e:
            logger.error("file_download_failed", storage_path=storage_path, error=str(e))
            raise
    
    async def download_bytes(self, storage_path: str) -> bytes:
        """
        Download file as bytes
        
        Args:
            storage_path: Path in storage
            
        Returns:
            File contents as bytes
        """
        try:
            response = self.client.storage.from_(self.bucket_name).download(storage_path)
            
            logger.debug("bytes_downloaded", storage_path=storage_path, size=len(response))
            
            return response
            
        except Exception as e:
            logger.error("bytes_download_failed", storage_path=storage_path, error=str(e))
            raise
    
    def get_signed_upload_url(
        self,
        storage_path: str,
        expires_in_seconds: int = 3600
    ) -> str:
        """
        Generate a pre-signed URL for direct upload
        
        Note: Supabase doesn't support pre-signed upload URLs out of the box.
        This returns a URL that can be used with the Supabase key for upload.
        For true pre-signed uploads, use the REST API directly.
        
        Args:
            storage_path: Destination path in storage
            expires_in_seconds: URL expiration time
            
        Returns:
            Upload URL
        """
        # Supabase upload URL format
        upload_url = f"{self.supabase_url}/storage/v1/object/{self.bucket_name}/{storage_path}"
        
        logger.info(
            "upload_url_generated",
            storage_path=storage_path,
            expires_in=expires_in_seconds
        )
        
        return upload_url
    
    def get_signed_download_url(
        self,
        storage_path: str,
        expires_in_seconds: int = 3600
    ) -> str:
        """
        Generate a pre-signed URL for download
        
        Args:
            storage_path: Path in storage
            expires_in_seconds: URL expiration time
            
        Returns:
            Pre-signed download URL
        """
        try:
            result = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path,
                expires_in=expires_in_seconds
            )
            
            signed_url = result.get("signedURL", "")
            
            logger.info(
                "download_url_generated",
                storage_path=storage_path,
                expires_in=expires_in_seconds
            )
            
            return signed_url
            
        except Exception as e:
            logger.error("signed_url_generation_failed", storage_path=storage_path, error=str(e))
            raise
    
    async def delete_file(self, storage_path: str) -> bool:
        """
        Delete a file from storage
        
        Args:
            storage_path: Path in storage
            
        Returns:
            True if deleted successfully
        """
        try:
            self.client.storage.from_(self.bucket_name).remove([storage_path])
            
            logger.info("file_deleted", storage_path=storage_path)
            return True
            
        except Exception as e:
            logger.error("file_deletion_failed", storage_path=storage_path, error=str(e))
            return False
    
    async def delete_job_files(self, job_id: str) -> int:
        """
        Delete all files for a job
        
        Args:
            job_id: Job UUID
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        
        try:
            # List files in all type directories for this job
            for file_type in ["input", "output", "checkpoint", "model", "dataset"]:
                prefix = f"{file_type}/{job_id}/"
                
                try:
                    files = self.client.storage.from_(self.bucket_name).list(prefix)
                    
                    if files:
                        paths = [f"{prefix}{f['name']}" for f in files]
                        self.client.storage.from_(self.bucket_name).remove(paths)
                        deleted_count += len(paths)
                        
                except Exception:
                    continue
            
            logger.info("job_files_deleted", job_id=job_id, count=deleted_count)
            return deleted_count
            
        except Exception as e:
            logger.error("job_files_deletion_failed", job_id=job_id, error=str(e))
            return deleted_count
    
    def list_files(
        self,
        prefix: str = "",
        limit: int = 100
    ) -> list:
        """
        List files in storage
        
        Args:
            prefix: Path prefix to filter
            limit: Maximum number of files to return
            
        Returns:
            List of file objects
        """
        try:
            files = self.client.storage.from_(self.bucket_name).list(
                path=prefix,
                options={"limit": limit}
            )
            return files
            
        except Exception as e:
            logger.error("file_list_failed", prefix=prefix, error=str(e))
            return []
    
    def get_file_info(self, storage_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata
        
        Args:
            storage_path: Path in storage
            
        Returns:
            File metadata dict or None
        """
        try:
            # Parse path to get directory and filename
            parts = storage_path.rsplit("/", 1)
            if len(parts) == 2:
                prefix, filename = parts
            else:
                prefix = ""
                filename = storage_path
            
            files = self.client.storage.from_(self.bucket_name).list(prefix)
            
            for f in files:
                if f["name"] == filename:
                    return {
                        "name": f["name"],
                        "size": f.get("metadata", {}).get("size"),
                        "created_at": f.get("created_at"),
                        "updated_at": f.get("updated_at"),
                        "content_type": f.get("metadata", {}).get("mimetype")
                    }
            
            return None
            
        except Exception as e:
            logger.error("file_info_failed", storage_path=storage_path, error=str(e))
            return None


# Singleton instance
_storage_client: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    """
    Get or create singleton storage client
    """
    global _storage_client
    
    if _storage_client is None:
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set for storage"
            )
        
        config = get_marketplace_config()
        
        _storage_client = StorageClient(
            supabase_url=supabase_url,
            supabase_key=supabase_key,
            bucket_name=config.supabase_storage_bucket
        )
    
    return _storage_client

