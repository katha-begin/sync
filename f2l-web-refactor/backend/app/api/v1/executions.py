"""
Executions API - Monitor sync executions.
"""
from fastapi import APIRouter, HTTPException, Query, Depends, status
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.repositories.execution_repository import ExecutionRepository
from app.database.models import ExecutionStatus

router = APIRouter()


class ExecutionResponse(BaseModel):
    """Execution response schema."""
    id: UUID
    session_id: UUID
    status: str
    progress_percentage: float
    files_synced: int
    total_files: int
    files_failed: int
    files_skipped: int
    bytes_transferred: int
    queued_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    current_file: Optional[str] = None
    current_operation: Optional[str] = None
    error_message: Optional[str] = None
    celery_task_id: Optional[str] = None
    is_dry_run: bool = False
    force_overwrite: bool = False

    class Config:
        from_attributes = True


class OperationResponse(BaseModel):
    """Operation response schema."""
    id: UUID
    execution_id: UUID
    operation_type: str
    source_path: str
    destination_path: str
    file_size: int
    success: bool
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ExecutionResponse])
async def list_executions(
    session_id: Optional[UUID] = Query(None, description="Filter by session ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records"),
    db: AsyncSession = Depends(get_db)
):
    """List sync executions with filtering."""
    try:
        repo = ExecutionRepository(db)

        # Convert status string to enum if provided
        status_enum = None
        if status:
            try:
                status_enum = ExecutionStatus[status.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}"
                )

        executions = await repo.get_all(
            session_id=session_id,
            status=status_enum,
            skip=skip,
            limit=limit
        )

        return executions

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list executions: {str(e)}"
        )


@router.get("/{execution_id}", response_model=ExecutionResponse)
async def get_execution(execution_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get execution by ID."""
    try:
        repo = ExecutionRepository(db)
        execution = await repo.get_by_id(execution_id)

        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found"
            )

        return execution

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get execution: {str(e)}"
        )


@router.get("/{execution_id}/operations", response_model=List[OperationResponse])
async def get_execution_operations(
    execution_id: UUID,
    operation_type: Optional[str] = Query(None, description="Filter by operation type"),
    success_only: Optional[bool] = Query(None, description="Filter by success status"),
    db: AsyncSession = Depends(get_db)
):
    """Get operations for a specific execution."""
    try:
        repo = ExecutionRepository(db)

        # Verify execution exists
        execution = await repo.get_by_id(execution_id)
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found"
            )

        # Convert operation_type string to enum if provided
        from app.database.models import OperationType
        operation_type_enum = None
        if operation_type:
            try:
                operation_type_enum = OperationType[operation_type.upper()]
            except KeyError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operation type: {operation_type}"
                )

        operations = await repo.get_execution_operations(
            execution_id=execution_id,
            operation_type=operation_type_enum,
            success_only=success_only
        )

        return operations

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get operations: {str(e)}"
        )


@router.post("/{execution_id}/cancel")
async def cancel_execution(execution_id: UUID, db: AsyncSession = Depends(get_db)):
    """Cancel running execution."""
    try:
        repo = ExecutionRepository(db)

        # Verify execution exists
        execution = await repo.get_by_id(execution_id)
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execution not found"
            )

        # Check if execution can be cancelled
        if execution.status not in [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel execution with status: {execution.status.value}"
            )

        # Cancel the execution
        success = await repo.cancel_execution(execution_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to cancel execution"
            )

        # Cancel Celery task if exists
        if execution.celery_task_id:
            from app.tasks.sync_tasks import cancel_sync_execution
            cancel_sync_execution.delay(execution.celery_task_id)

        await db.commit()

        return {
            "message": "Execution cancelled successfully",
            "execution_id": str(execution_id),
            "status": "cancelled"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel execution: {str(e)}"
        )
