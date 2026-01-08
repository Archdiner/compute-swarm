
import uuid
from typing import Optional, List

from fastapi import APIRouter, Request, HTTPException, status
import structlog

from src.database import get_db_client
from src.marketplace.dependencies import limiter, logger

router = APIRouter()

@router.get("/api/v1/models", tags=["Models"])
@limiter.limit("100/minute")
async def list_models(
    request: Request,
    buyer_address: Optional[str] = None,
    experiment_id: Optional[str] = None,
    limit: int = 50
):
    """List trained models"""
    db = get_db_client()
    
    models = await db.list_models(
        buyer_address=buyer_address,
        experiment_id=experiment_id,
        limit=limit
    )
    
    return {
        "models": models,
        "count": len(models)
    }


@router.get("/api/v1/models/{model_id}/download", tags=["Models"])
@limiter.limit("10/minute")
async def download_model(request: Request, model_id: str):
    """Get download URL for a model"""
    from src.storage import get_storage_client
    
    db = get_db_client()
    storage = get_storage_client()
    
    # Get model metadata
    model = await db.get_model(model_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Model {model_id} not found"
        )
    
    # Generate signed download URL
    storage_path = model["storage_path"]
    download_url = storage.get_signed_download_url(storage_path, expires_in_seconds=3600)
    
    return {
        "model_id": model_id,
        "model_name": model["name"],
        "version": model["version"],
        "download_url": download_url,
        "expires_in": 3600,
        "file_size_bytes": model["file_size_bytes"]
    }


@router.get("/api/v1/datasets", tags=["Datasets"])
@limiter.limit("100/minute")
async def list_datasets(
    request: Request,
    buyer_address: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_public: Optional[bool] = None,
    limit: int = 50
):
    """List datasets"""
    from src.storage.dataset_manager import get_dataset_manager
    
    dataset_manager = get_dataset_manager()
    datasets = await dataset_manager.list_datasets(
        buyer_address=buyer_address,
        tags=tags,
        is_public=is_public,
        limit=limit
    )
    
    return {
        "datasets": datasets,
        "count": len(datasets)
    }


@router.post("/api/v1/datasets", status_code=status.HTTP_201_CREATED, tags=["Datasets"])
@limiter.limit("10/minute")
async def create_dataset(
    request: Request,
    buyer_address: str,
    name: str,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    is_public: bool = False
):
    """Create a new dataset"""
    from src.storage.dataset_manager import get_dataset_manager
    
    dataset_manager = get_dataset_manager()
    dataset = await dataset_manager.create_dataset(
        buyer_address=buyer_address,
        name=name,
        description=description,
        tags=tags,
        is_public=is_public
    )
    
    return dataset


@router.post("/api/v1/files/upload/chunked", tags=["Files"])
@limiter.limit("5/minute")
async def start_chunked_upload(
    request: Request,
    file_name: str,
    file_size: int,
    content_type: Optional[str] = None
):
    """Start a chunked file upload"""
    from src.storage import get_storage_client
    
    storage = get_storage_client()
    job_id = str(uuid.uuid4())  # Would come from request context
    
    storage_path = storage.generate_storage_path(
        job_id=job_id,
        file_name=file_name,
        file_type="input"
    )
    
    # Generate upload URL
    upload_url = storage.get_signed_upload_url(storage_path)
    
    return {
        "upload_id": str(uuid.uuid4()),
        "storage_path": storage_path,
        "upload_url": upload_url,
        "chunk_size": 10 * 1024 * 1024,  # 10MB
        "expires_in": 3600
    }
