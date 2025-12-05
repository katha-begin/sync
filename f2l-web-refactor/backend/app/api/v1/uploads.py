"""
Uploads API - Manage shot uploads to FTP/SFTP endpoints.

Endpoints:
- GET /uploads/structure/{endpoint_id} - Scan local structure for shots
- POST /uploads/tasks - Create upload task
- GET /uploads/tasks - List upload tasks
- GET /uploads/tasks/{task_id} - Get task details
- POST /uploads/tasks/{task_id}/execute - Execute upload task
- POST /uploads/tasks/{task_id}/cancel - Cancel upload task
- POST /uploads/tasks/{task_id}/retry - Retry skipped items
- DELETE /uploads/tasks/{task_id} - Delete upload task
- GET /uploads/history - Get upload history
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from app.database.session import get_db
from app.services.shot_upload_service import ShotUploadService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["uploads"])


# ============================================================================
# Request/Response Schemas
# ============================================================================

class UploadItemRequest(BaseModel):
    """Single file item for upload."""
    episode: str = Field(..., description="Episode name")
    sequence: str = Field(..., description="Sequence name")
    shot: str = Field(..., description="Shot name")
    department: str = Field(..., description="Department name")
    filename: str = Field(..., description="Filename")
    source_path: str = Field(..., description="Full local path")
    version: Optional[str] = Field(None, description="File version")
    size: int = Field(0, description="File size in bytes")


class CreateUploadTaskRequest(BaseModel):
    """Request to create upload task."""
    source_endpoint_id: UUID = Field(..., description="Local source endpoint UUID")
    target_endpoint_id: UUID = Field(..., description="FTP/SFTP target endpoint UUID")
    task_name: str = Field(..., description="User-friendly task name")
    items: List[UploadItemRequest] = Field(..., description="List of files to upload")
    version_strategy: Optional[str] = Field('latest', description="Version strategy")
    specific_version: Optional[str] = Field(None, description="Specific version")
    conflict_strategy: Optional[str] = Field('skip', description="skip or overwrite")
    notes: Optional[str] = Field(None, description="Optional notes")


class UploadTaskResponse(BaseModel):
    """Upload task response."""
    id: str
    name: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    skipped_items: int
    total_size: int
    uploaded_size: int
    created_at: Optional[str]
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_by: Optional[str] = None


class UploadHistoryResponse(BaseModel):
    """Upload history item response."""
    id: str
    task_id: Optional[str]
    task_name: str
    episode: str
    sequence: str
    shot: str
    department: str
    filename: str
    version: Optional[str]
    file_size: int
    source_path: str
    target_path: str
    source_endpoint_name: str
    target_endpoint_name: str
    status: str
    error_message: Optional[str]
    uploaded_at: Optional[str]
    uploaded_by: Optional[str]


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/structure/{endpoint_id}")
async def get_local_structure(
    endpoint_id: UUID,
    episode: Optional[str] = Query(None, description="Filter by episode"),
    sequence: Optional[str] = Query(None, description="Filter by sequence"),
    department: Optional[str] = Query(None, description="Filter by department"),
    db: AsyncSession = Depends(get_db)
):
    """Scan local endpoint for shot structure."""
    try:
        service = ShotUploadService(db)
        structure = await service.scan_local_structure(
            endpoint_id=endpoint_id,
            episode_filter=episode,
            sequence_filter=sequence,
            department_filter=department
        )
        return structure
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error scanning structure: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan structure: {str(e)}"
        )


@router.post("/tasks")
async def create_upload_task(
    request: CreateUploadTaskRequest,
    db: AsyncSession = Depends(get_db)
):
    """Create a new upload task."""
    try:
        service = ShotUploadService(db)
        result = await service.create_upload_task(
            source_endpoint_id=request.source_endpoint_id,
            target_endpoint_id=request.target_endpoint_id,
            task_name=request.task_name,
            items=[item.dict() for item in request.items],
            version_strategy=request.version_strategy or 'latest',
            specific_version=request.specific_version,
            conflict_strategy=request.conflict_strategy or 'skip',
            notes=request.notes
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating upload task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/tasks")
async def list_upload_tasks(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List upload tasks."""
    try:
        service = ShotUploadService(db)
        result = await service.list_tasks(
            status=status_filter,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        logger.error(f"Error listing tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )


@router.get("/tasks/{task_id}")
async def get_upload_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get upload task details."""
    try:
        service = ShotUploadService(db)
        result = await service.get_task(task_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task: {str(e)}"
        )


@router.post("/tasks/{task_id}/execute")
async def execute_upload_task(
    task_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Execute an upload task."""
    try:
        service = ShotUploadService(db)

        # Verify task exists
        task = await service.get_task(task_id)
        if not task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )

        # Execute in background
        background_tasks.add_task(
            _execute_upload_background,
            task_id,
            db
        )

        return {
            "success": True,
            "message": f"Upload task {task_id} started",
            "task_id": str(task_id)
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error executing task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute task: {str(e)}"
        )


async def _execute_upload_background(task_id: UUID, db: AsyncSession):
    """Background task executor."""
    try:
        service = ShotUploadService(db)
        await service.execute_upload_task(task_id)
    except Exception as e:
        logger.error(f"Background upload failed: {e}")


@router.post("/tasks/{task_id}/cancel")
async def cancel_upload_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Cancel a running upload task."""
    try:
        service = ShotUploadService(db)
        result = await service.cancel_task(task_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        return {"success": True, "message": f"Task {task_id} cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


@router.post("/tasks/{task_id}/retry")
async def retry_skipped_items(
    task_id: UUID,
    overwrite: bool = Query(True, description="Overwrite existing files"),
    db: AsyncSession = Depends(get_db)
):
    """Retry skipped items in a task."""
    try:
        service = ShotUploadService(db)
        result = await service.retry_skipped_items(task_id, overwrite=overwrite)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrying task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry task: {str(e)}"
        )


@router.delete("/tasks/{task_id}")
async def delete_upload_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete an upload task."""
    try:
        service = ShotUploadService(db)
        result = await service.delete_task(task_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task {task_id} not found"
            )
        return {"success": True, "message": f"Task {task_id} deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}"
        )


@router.get("/history")
async def get_upload_history(
    episode: Optional[str] = Query(None),
    sequence: Optional[str] = Query(None),
    shot: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get upload history."""
    try:
        service = ShotUploadService(db)
        result = await service.get_upload_history(
            episode=episode,
            sequence=sequence,
            shot=shot,
            status=status_filter,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        return result
    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history: {str(e)}"
        )

