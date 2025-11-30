"""
Session Service - Business logic for sync session management.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from app.repositories.session_repository import SessionRepository
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.endpoint_repository import EndpointRepository
from app.database.models import SyncSession, SyncExecution, ExecutionStatus
from app.tasks.sync_tasks import execute_sync_session, cancel_sync_execution
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SessionService:
    """Service for sync session business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.session_repo = SessionRepository(db)
        self.execution_repo = ExecutionRepository(db)
        self.endpoint_repo = EndpointRepository(db)

    async def get_all_sessions(
        self,
        user_id: Optional[UUID] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[SyncSession]:
        """
        Get all sync sessions with optional filtering.
        
        Args:
            user_id: Filter by user ID
            active_only: Only return active sessions
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of SyncSession objects
        """
        try:
            sessions = await self.session_repo.get_all(
                user_id=user_id,
                active_only=active_only,
                skip=skip,
                limit=limit
            )
            
            logger.info(f"Retrieved {len(sessions)} sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get sessions: {e}")
            raise

    async def get_session_by_id(self, session_id: UUID) -> Optional[SyncSession]:
        """
        Get session by ID.
        
        Args:
            session_id: Session UUID
            
        Returns:
            SyncSession object or None if not found
        """
        try:
            session = await self.session_repo.get_by_id(session_id)
            
            if session:
                logger.info(f"Retrieved session {session_id} ({session.name})")
            else:
                logger.warning(f"Session {session_id} not found")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            raise

    async def create_session(self, session_data: dict) -> SyncSession:
        """
        Create new sync session.
        
        Args:
            session_data: Dictionary with session data
            
        Returns:
            Created SyncSession object
        """
        try:
            # Validate session data
            await self._validate_session_data(session_data)
            
            # Create session
            session = await self.session_repo.create(session_data)
            
            logger.info(f"Created session {session.id} ({session.name})")
            return session
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise

    async def update_session(self, session_id: UUID, update_data: dict) -> Optional[SyncSession]:
        """
        Update sync session.
        
        Args:
            session_id: Session UUID
            update_data: Dictionary with fields to update
            
        Returns:
            Updated SyncSession object or None if not found
        """
        try:
            # Validate update data
            if update_data:
                await self._validate_session_data(update_data, is_update=True)
            
            # Update session
            session = await self.session_repo.update(session_id, update_data)
            
            if session:
                logger.info(f"Updated session {session_id} ({session.name})")
            else:
                logger.warning(f"Session {session_id} not found for update")
            
            return session
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            raise

    async def delete_session(self, session_id: UUID) -> bool:
        """
        Delete sync session.
        
        Args:
            session_id: Session UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            # Check if session has running executions
            running_executions = await self.execution_repo.get_all(
                session_id=session_id,
                status=ExecutionStatus.RUNNING
            )
            
            if running_executions:
                raise ValueError("Cannot delete session with running executions")
            
            # Delete session
            deleted = await self.session_repo.delete(session_id)
            
            if deleted:
                logger.info(f"Deleted session {session_id}")
            else:
                logger.warning(f"Session {session_id} not found for deletion")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            raise

    async def start_session(
        self,
        session_id: UUID,
        dry_run: bool = False,
        force_overwrite: bool = False,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Start sync session execution.
        
        Args:
            session_id: Session UUID
            dry_run: If True, don't perform actual file operations
            force_overwrite: If True, overwrite files regardless of metadata
            user_id: User ID starting the session
            
        Returns:
            Dictionary with execution details
        """
        try:
            # Get session
            session = await self.get_session_by_id(session_id)
            if not session:
                raise ValueError("Session not found")
            
            if not session.is_active:
                raise ValueError("Session is not active")
            
            # Check if session is already running
            running_executions = await self.execution_repo.get_all(
                session_id=session_id,
                status=ExecutionStatus.RUNNING
            )
            
            if running_executions:
                raise ValueError("Session is already running")
            
            # Validate endpoints exist and are accessible
            await self._validate_session_endpoints(session)
            
            # Create execution record
            execution_data = {
                'session_id': session_id,
                'status': ExecutionStatus.QUEUED,
                'is_dry_run': dry_run
            }
            
            execution = await self.execution_repo.create(execution_data)
            
            # Queue Celery task
            task = execute_sync_session.delay(
                session_id=str(session_id),
                dry_run=dry_run,
                force_overwrite=force_overwrite,
                user_id=str(user_id) if user_id else None
            )
            
            # Update execution with task ID
            await self.execution_repo.update(execution.id, {
                'celery_task_id': task.id,
                'status': ExecutionStatus.QUEUED
            })
            
            logger.info(f"Started session {session_id} execution {execution.id}")
            
            return {
                'success': True,
                'execution_id': str(execution.id),
                'task_id': task.id,
                'session_id': str(session_id),
                'session_name': session.name,
                'dry_run': dry_run,
                'force_overwrite': force_overwrite,
                'status': ExecutionStatus.QUEUED.value,
                'queued_at': execution.queued_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to start session {session_id}: {e}")
            raise

    async def stop_session(self, session_id: UUID) -> Dict[str, Any]:
        """
        Stop running session execution.
        
        Args:
            session_id: Session UUID
            
        Returns:
            Dictionary with stop results
        """
        try:
            # Get running executions for session
            running_executions = await self.execution_repo.get_all(
                session_id=session_id,
                status=ExecutionStatus.RUNNING
            )
            
            if not running_executions:
                return {
                    'success': False,
                    'message': 'No running executions found for session',
                    'session_id': str(session_id)
                }
            
            stopped_executions = []
            
            for execution in running_executions:
                try:
                    # Cancel Celery task
                    if execution.celery_task_id:
                        cancel_sync_execution.delay(execution.celery_task_id)
                    
                    # Update execution status
                    await self.execution_repo.update(execution.id, {
                        'status': ExecutionStatus.CANCELLED,
                        'completed_at': datetime.now(timezone.utc)
                    })
                    
                    stopped_executions.append(str(execution.id))
                    
                except Exception as e:
                    logger.error(f"Failed to stop execution {execution.id}: {e}")
            
            logger.info(f"Stopped {len(stopped_executions)} executions for session {session_id}")
            
            return {
                'success': True,
                'message': f'Stopped {len(stopped_executions)} executions',
                'session_id': str(session_id),
                'stopped_executions': stopped_executions
            }
            
        except Exception as e:
            logger.error(f"Failed to stop session {session_id}: {e}")
            raise

    async def get_session_status(self, session_id: UUID) -> Dict[str, Any]:
        """
        Get session execution status.
        
        Args:
            session_id: Session UUID
            
        Returns:
            Dictionary with session status
        """
        try:
            session = await self.get_session_by_id(session_id)
            if not session:
                raise ValueError("Session not found")
            
            # Get execution summary
            execution_summary = await self.execution_repo.get_execution_summary(session_id)
            
            # Get latest execution
            latest_execution = None
            if execution_summary['latest_execution']['id']:
                latest_execution = await self.execution_repo.get_by_id(
                    UUID(execution_summary['latest_execution']['id'])
                )
            
            # Get running executions
            running_executions = await self.execution_repo.get_all(
                session_id=session_id,
                status=ExecutionStatus.RUNNING
            )
            
            return {
                'session_id': str(session_id),
                'session_name': session.name,
                'is_active': session.is_active,
                'execution_summary': execution_summary,
                'is_running': len(running_executions) > 0,
                'running_executions': [str(exec.id) for exec in running_executions],
                'latest_execution': {
                    'id': str(latest_execution.id) if latest_execution else None,
                    'status': latest_execution.status.value if latest_execution else None,
                    'queued_at': latest_execution.queued_at.isoformat() if latest_execution else None,
                    'completed_at': latest_execution.completed_at.isoformat() if latest_execution and latest_execution.completed_at else None,
                    'is_dry_run': latest_execution.is_dry_run if latest_execution else None
                } if latest_execution else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id} status: {e}")
            raise

    async def get_session_executions(
        self,
        session_id: UUID,
        skip: int = 0,
        limit: int = 50
    ) -> List[SyncExecution]:
        """
        Get executions for a session.
        
        Args:
            session_id: Session UUID
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of SyncExecution objects
        """
        try:
            executions = await self.execution_repo.get_all(
                session_id=session_id,
                skip=skip,
                limit=limit
            )
            
            logger.info(f"Retrieved {len(executions)} executions for session {session_id}")
            return executions
            
        except Exception as e:
            logger.error(f"Failed to get executions for session {session_id}: {e}")
            raise

    async def get_execution_progress(self, execution_id: UUID) -> Dict[str, Any]:
        """
        Get execution progress.
        
        Args:
            execution_id: Execution UUID
            
        Returns:
            Dictionary with execution progress
        """
        try:
            execution = await self.execution_repo.get_by_id(execution_id)
            if not execution:
                raise ValueError("Execution not found")
            
            # Get execution statistics
            stats = await self.execution_repo.get_execution_statistics(execution_id)
            
            # Get progress from Celery task if running
            progress_info = None
            if execution.celery_task_id and execution.status == ExecutionStatus.RUNNING:
                from app.tasks.sync_tasks import get_sync_progress
                try:
                    progress_task = get_sync_progress.delay(execution.celery_task_id)
                    progress_info = progress_task.get(timeout=5)
                except:
                    progress_info = None
            
            return {
                'execution_id': str(execution_id),
                'status': execution.status.value,
                'progress_percentage': progress_info.get('progress_percentage', 0) if progress_info else 0,
                'current_operation': progress_info.get('current_operation', '') if progress_info else '',
                'statistics': stats,
                'queued_at': execution.queued_at.isoformat(),
                'started_at': execution.started_at.isoformat() if execution.started_at else None,
                'completed_at': execution.completed_at.isoformat() if execution.completed_at else None,
                'is_dry_run': execution.is_dry_run
            }
            
        except Exception as e:
            logger.error(f"Failed to get execution {execution_id} progress: {e}")
            raise

    async def _validate_session_data(self, data: dict, is_update: bool = False):
        """Validate session data."""
        if not is_update:
            required_fields = ['name', 'source_endpoint_id', 'destination_endpoint_id', 'sync_direction']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
        
        # Validate endpoints exist
        if 'source_endpoint_id' in data:
            source_endpoint = await self.endpoint_repo.get_by_id(data['source_endpoint_id'])
            if not source_endpoint:
                raise ValueError("Source endpoint not found")
        
        if 'destination_endpoint_id' in data:
            dest_endpoint = await self.endpoint_repo.get_by_id(data['destination_endpoint_id'])
            if not dest_endpoint:
                raise ValueError("Destination endpoint not found")
        
        # Validate paths
        if 'source_path' in data and not data['source_path']:
            raise ValueError("Source path cannot be empty")
        
        if 'destination_path' in data and not data['destination_path']:
            raise ValueError("Destination path cannot be empty")

    async def _validate_session_endpoints(self, session: SyncSession):
        """Validate that session endpoints are accessible."""
        # Get source endpoint
        source_endpoint = await self.endpoint_repo.get_by_id(session.source_endpoint_id)
        if not source_endpoint:
            raise ValueError("Source endpoint not found")
        
        if not source_endpoint.is_active:
            raise ValueError("Source endpoint is not active")
        
        # Get destination endpoint
        dest_endpoint = await self.endpoint_repo.get_by_id(session.destination_endpoint_id)
        if not dest_endpoint:
            raise ValueError("Destination endpoint not found")
        
        if not dest_endpoint.is_active:
            raise ValueError("Destination endpoint is not active")
        
        # Check connection status (optional - could test connections here)
        if source_endpoint.connection_status == "error":
            logger.warning(f"Source endpoint {source_endpoint.id} has error status")
        
        if dest_endpoint.connection_status == "error":
            logger.warning(f"Destination endpoint {dest_endpoint.id} has error status")
