"""
Shots API - Manage shot downloads for animation production.

Endpoints:
- GET /shots/structure/{endpoint_id} - Get cached shot structure
- POST /shots/structure/{endpoint_id}/scan - Trigger structure scan
- POST /shots/compare - Compare selected shots
- POST /shots/tasks - Create download task
- GET /shots/tasks - List download tasks
- GET /shots/tasks/{task_id} - Get task details
- POST /shots/tasks/{task_id}/execute - Execute download task
- POST /shots/tasks/{task_id}/cancel - Cancel download task
- DELETE /shots/tasks/{task_id} - Delete download task
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

from app.database.session import get_db
from app.services.shot_structure_scanner import ShotStructureScanner
from app.services.shot_comparison_service import ShotComparisonService
from app.services.shot_download_service import ShotDownloadService
from app.database.models import ShotDownloadTaskStatus
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(tags=["shots"])


# ============================================================================
# Request/Response Schemas
# ============================================================================

class ShotSelection(BaseModel):
    """Shot selection for comparison/download."""
    episode: str = Field(..., description="Episode name (e.g., 'Ep01')")
    sequence: str = Field(..., description="Sequence name (e.g., 'sq0010')")
    shot: str = Field(..., description="Shot name (e.g., 'SH0010')")


class CompareRequest(BaseModel):
    """Request to compare shots."""
    endpoint_id: UUID = Field(..., description="Endpoint UUID")
    shots: List[ShotSelection] = Field(..., description="List of shots to compare")
    departments: List[str] = Field(default=["anim", "lighting"], description="Departments to compare")


class ComparisonResult(BaseModel):
    """Comparison result for a single shot/department."""
    episode: str
    sequence: str
    shot: str
    department: str
    ftp_version: Optional[str]
    local_version: Optional[str]
    available_versions: Optional[List[str]] = None
    latest_version: Optional[str] = None
    needs_update: bool
    status: str
    file_count: int
    total_size: int
    error_message: Optional[str] = None


class CreateTaskRequest(BaseModel):
    """Request to create download task."""
    endpoint_id: UUID = Field(..., description="Endpoint UUID")
    task_name: str = Field(..., description="User-friendly task name")
    shots: List[ShotSelection] = Field(..., description="List of shots to download")
    departments: List[str] = Field(default=["anim", "lighting"], description="Departments to download")
    version_strategy: Optional[str] = Field('latest', description="Version strategy: latest, specific, all, custom")
    specific_version: Optional[str] = Field(None, description="Specific version to download (e.g., v005)")
    custom_versions: Optional[dict] = Field(None, description="Custom version per shot (shot-department: version)")
    conflict_strategy: Optional[str] = Field('skip', description="Conflict strategy: skip, overwrite, compare, keep_both")
    notes: Optional[str] = Field(None, description="Optional notes")
    created_by: Optional[str] = Field(None, description="Username who created the task")


class TaskResponse(BaseModel):
    """Download task response."""
    task_id: str
    name: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    total_size: int
    downloaded_size: int
    progress_percent: int
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    created_by: Optional[str]
    notes: Optional[str]


class TaskSummary(BaseModel):
    """Task summary for list view."""
    task_id: str
    name: str
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    progress_percent: int
    created_at: Optional[str]
    created_by: Optional[str]


class StructureResponse(BaseModel):
    """Shot structure response."""
    episodes: List[str]
    sequences: List[dict]
    shots: List[dict]
    cache_valid: bool
    last_scan: Optional[str]


class ScanResponse(BaseModel):
    """Structure scan response."""
    status: str
    message: str
    total_episodes: int
    total_sequences: int
    total_shots: int
    scan_duration_seconds: Optional[int] = None
    last_scan: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/structure/{endpoint_id}", response_model=StructureResponse)
async def get_shot_structure(
    endpoint_id: UUID,
    episodes: Optional[List[str]] = Query(None, description="Filter by episodes"),
    sequences: Optional[List[str]] = Query(None, description="Filter by sequences"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cached shot structure (Episodes/Sequences/Shots).
    
    Returns cached data if available, otherwise returns empty structure.
    Use POST /shots/structure/{endpoint_id}/scan to populate cache.
    """
    scanner = ShotStructureScanner(db)
    
    # Check if cache is valid
    cache_valid = await scanner.is_cache_valid(endpoint_id)
    
    # Get metadata
    metadata = await scanner.get_cache_metadata(endpoint_id)
    
    # Get structure
    episodes_list = await scanner.get_cached_episodes(endpoint_id)
    sequences_list = await scanner.get_cached_sequences(endpoint_id, episodes)
    shots_list = await scanner.get_cached_shots(endpoint_id, episodes, sequences)
    
    return {
        "episodes": episodes_list,
        "sequences": sequences_list,
        "shots": shots_list,
        "cache_valid": cache_valid,
        "last_scan": metadata.last_full_scan.isoformat() if metadata and metadata.last_full_scan else None
    }


@router.post("/structure/{endpoint_id}/scan", response_model=ScanResponse)
async def scan_shot_structure(
    endpoint_id: UUID,
    force_refresh: bool = Query(False, description="Force rescan even if cache is valid"),
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger shot structure scan for an endpoint.

    Scans FTP/Local to discover Episodes/Sequences/Shots and caches the structure.
    If cache is valid and force_refresh=False, returns cached data without scanning.
    """
    scanner = ShotStructureScanner(db)

    try:
        result = await scanner.scan_endpoint_structure(endpoint_id, force_refresh)

        return {
            "status": result["status"],
            "message": result["message"],
            "total_episodes": result["total_episodes"],
            "total_sequences": result["total_sequences"],
            "total_shots": result["total_shots"],
            "scan_duration_seconds": result.get("scan_duration_seconds"),
            "last_scan": result.get("last_scan").isoformat() if result.get("last_scan") else None
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan structure: {str(e)}"
        )


@router.post("/compare", response_model=List[ComparisonResult])
async def compare_shots(
    request: CompareRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Compare selected shots between FTP and Local.

    Returns comparison results showing which shots need updates.
    """
    comparison_service = ShotComparisonService(db)

    try:
        # Convert shots to dict format
        shots = [shot.dict() for shot in request.shots]

        # Compare all shots
        results = []
        for shot in shots:
            for department in request.departments:
                comparison = await comparison_service.compare_shot(
                    endpoint_id=request.endpoint_id,
                    episode=shot["episode"],
                    sequence=shot["sequence"],
                    shot=shot["shot"],
                    department=department
                )

                results.append({
                    "episode": comparison.episode,
                    "sequence": comparison.sequence,
                    "shot": comparison.shot,
                    "department": comparison.department,
                    "ftp_version": comparison.ftp_version,
                    "local_version": comparison.local_version,
                    "available_versions": comparison.available_versions,  # Added
                    "latest_version": comparison.latest_version,  # Added
                    "needs_update": comparison.needs_update,
                    "status": comparison.status,
                    "file_count": comparison.file_count,
                    "total_size": comparison.total_size,
                    "error_message": comparison.error_message
                })

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compare shots: {str(e)}"
        )


@router.post("/tasks", response_model=dict)
async def create_download_task(
    request: CreateTaskRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a download task from selected shots.

    Compares shots and creates a task with items that need downloading.
    """
    download_service = ShotDownloadService(db)

    try:
        # Convert shots to dict format
        shots = [shot.dict() for shot in request.shots]

        result = await download_service.create_download_task(
            endpoint_id=request.endpoint_id,
            task_name=request.task_name,
            shots=shots,
            departments=request.departments,
            version_strategy=request.version_strategy or 'latest',
            specific_version=request.specific_version,
            custom_versions=request.custom_versions,
            conflict_strategy=request.conflict_strategy or 'skip',
            created_by=request.created_by,
            notes=request.notes
        )

        return result

    except Exception as e:
        logger.error(f"Failed to create download task: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create download task: {str(e)}"
        )


@router.get("/tasks", response_model=List[TaskSummary])
async def list_download_tasks(
    endpoint_id: Optional[UUID] = Query(None, description="Filter by endpoint"),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_db)
):
    """
    List download tasks with optional filters.

    Returns paginated list of task summaries.
    """
    download_service = ShotDownloadService(db)

    try:
        # Convert status string to enum if provided
        status_enum = None
        if status_filter:
            try:
                status_enum = ShotDownloadTaskStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}"
                )

        tasks = await download_service.list_tasks(
            endpoint_id=endpoint_id,
            status=status_enum,
            limit=limit,
            offset=offset
        )

        return tasks

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tasks: {str(e)}"
        )


@router.get("/tasks/{task_id}", response_model=dict)
async def get_task_details(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed information about a download task.

    Returns task summary and all items with their status.
    """
    download_service = ShotDownloadService(db)

    try:
        details = await download_service.get_task_details(task_id)
        return details

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task details: {str(e)}"
        )


@router.post("/tasks/{task_id}/execute", response_model=dict)
async def execute_download_task(
    task_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Execute a download task.

    Starts downloading all items in the task.
    Task execution runs in the background.
    """
    download_service = ShotDownloadService(db)

    try:
        # Execute in background
        background_tasks.add_task(
            download_service.execute_download_task,
            task_id
        )

        return {
            "success": True,
            "task_id": str(task_id),
            "message": "Download task started in background"
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute task: {str(e)}"
        )


@router.post("/tasks/{task_id}/cancel", response_model=dict)
async def cancel_download_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a running download task.

    Only running tasks can be cancelled.
    """
    download_service = ShotDownloadService(db)

    try:
        result = await download_service.cancel_task(task_id)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel task: {str(e)}"
        )


@router.delete("/tasks/{task_id}", response_model=dict)
async def delete_download_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a download task.

    Cannot delete running tasks. Cancel them first.
    """
    download_service = ShotDownloadService(db)

    try:
        result = await download_service.delete_task(task_id)
        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}"
        )


@router.get("/tasks/{task_id}/status", response_model=TaskResponse)
async def get_task_status(
    task_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get current status of a download task.

    Returns real-time progress information.
    Useful for polling during task execution.
    """
    download_service = ShotDownloadService(db)

    try:
        status_info = await download_service.get_task_status(task_id)
        return status_info

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task status: {str(e)}"
        )



