"""
Sessions API - Manage sync sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from app.database.models import SyncDirection
from app.repositories.session_repository import SessionRepository
from app.database.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionBase(BaseModel):
    """Base session schema."""
    name: str
    source_endpoint_id: UUID
    destination_endpoint_id: UUID
    sync_direction: SyncDirection
    notes: Optional[str] = None

    # Sync configuration
    source_path: str = "/"
    destination_path: str = "/"
    # Note: folder_filter, file_filter, exclude_patterns will be added in Phase 5

    # Sync options
    force_overwrite: bool = False
    # Note: delete_extra_files, preserve_timestamps, verify_checksums not yet in database model
    # Note: max_parallel_transfers will be added in Phase 5

    # Scheduling
    schedule_enabled: bool = False
    schedule_interval: Optional[int] = None
    schedule_unit: Optional[str] = None  # "minutes", "hours", "days"
    auto_start_enabled: bool = False


class SessionCreate(SessionBase):
    """Session creation schema."""
    pass


class SessionUpdate(BaseModel):
    """Session update schema."""
    name: Optional[str] = None
    notes: Optional[str] = None
    source_path: Optional[str] = None
    destination_path: Optional[str] = None
    # Note: folder_filter, file_filter, exclude_patterns will be added in Phase 5
    force_overwrite: Optional[bool] = None
    # Note: delete_extra_files, preserve_timestamps, verify_checksums not yet in database model
    # Note: max_parallel_transfers will be added in Phase 5
    schedule_enabled: Optional[bool] = None
    schedule_interval: Optional[int] = None
    schedule_unit: Optional[str] = None
    auto_start_enabled: Optional[bool] = None
    is_active: Optional[bool] = None


class SessionResponse(BaseModel):
    """Session response schema."""
    id: UUID
    name: str
    source_endpoint_id: UUID
    destination_endpoint_id: UUID
    sync_direction: SyncDirection
    is_active: bool
    notes: Optional[str] = None

    # Sync configuration
    source_path: str
    destination_path: str
    # Note: folder_filter, file_filter, exclude_patterns will be added in Phase 5

    # Sync options
    force_overwrite: bool
    # Note: delete_extra_files, preserve_timestamps, verify_checksums not yet in database model
    # Note: max_parallel_transfers will be added in Phase 5

    # Scheduling
    schedule_enabled: bool
    schedule_interval: Optional[int] = None
    schedule_unit: Optional[str] = None
    auto_start_enabled: bool

    # Status
    is_running: bool
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionExecutionResponse(BaseModel):
    """Session execution response schema."""
    execution_id: UUID
    status: str
    message: str


@router.get("/", response_model=List[SessionResponse])
async def list_sessions(
    active_only: bool = Query(True, description="Only return active sessions"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records"),
    db: AsyncSession = Depends(get_db)
):
    """List all sync sessions."""
    try:
        repo = SessionRepository(db)
        sessions = await repo.get_all(
            active_only=active_only,
            skip=skip,
            limit=limit
        )
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve sessions: {str(e)}"
        )


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(session: SessionCreate, db: AsyncSession = Depends(get_db)):
    """Create new sync session."""
    try:
        repo = SessionRepository(db)

        # Check if session name already exists
        existing = await repo.get_by_name(session.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session with name '{session.name}' already exists"
            )

        # Prepare session data
        session_data = session.dict()
        session_data['is_active'] = True

        # Create session
        new_session = await repo.create(session_data)
        return new_session

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get session by ID."""
    try:
        repo = SessionRepository(db)
        session = await repo.get_by_id(session_id)

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        return session

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session: {str(e)}"
        )


@router.put("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: UUID,
    session_update: SessionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update session."""
    try:
        repo = SessionRepository(db)

        # Check if session exists
        existing = await repo.get_by_id(session_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

        # Update session
        update_data = session_update.dict(exclude_unset=True)
        updated_session = await repo.update(session_id, update_data)
        return updated_session

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}"
        )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete session."""
    try:
        repo = SessionRepository(db)

        success = await repo.delete(session_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.post("/{session_id}/start", response_model=SessionExecutionResponse)
async def start_session(
    session_id: UUID,
    dry_run: bool = Query(False, description="Perform dry run without actual file operations"),
    force_overwrite: bool = Query(False, description="Force overwrite existing files"),
    db: AsyncSession = Depends(get_db)
):
    """Start sync session."""
    try:
        from app.services.session_service import SessionService

        service = SessionService(db)
        result = await service.start_session(
            session_id=session_id,
            dry_run=dry_run,
            force_overwrite=force_overwrite
        )

        return SessionExecutionResponse(
            execution_id=UUID(result['execution_id']),
            status=result['status'],
            message=f"Sync session queued for execution (dry_run={dry_run}, force_overwrite={force_overwrite})"
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start session: {str(e)}"
        )


@router.post("/{session_id}/stop")
async def stop_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """Stop running sync session."""
    try:
        from app.services.session_service import SessionService

        service = SessionService(db)
        result = await service.stop_session(session_id)

        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['message']
            )

        return {
            "message": result['message'],
            "status": "stopped",
            "stopped_executions": result.get('stopped_executions', [])
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop session: {str(e)}"
        )
