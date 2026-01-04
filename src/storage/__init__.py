"""
Storage module for ComputeSwarm
Provides file upload/download functionality via Supabase Storage
"""

from src.storage.supabase_storage import StorageClient, get_storage_client

__all__ = ["StorageClient", "get_storage_client"]

