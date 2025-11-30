"""
Sync tasks for background file synchronization operations.
"""
from celery import current_task
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
import logging
import asyncio

from app.tasks.celery_app import celery_app
from app.database.models import SyncExecution, ExecutionStatus, SyncOperation, OperationType
from app.repositories.session_repository import SessionRepository
from app.repositories.execution_repository import ExecutionRepository
from app.core.sync_engine import SyncEngine
from app.database.session import async_session_maker

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.sync_tasks.execute_sync_session")
def execute_sync_session(
    self,
    session_id: str,
    dry_run: bool = False,
    force_overwrite: bool = False,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Execute a sync session with progress tracking.
    
    Args:
        session_id: UUID of the sync session
        dry_run: If True, don't perform actual file operations
        force_overwrite: If True, overwrite files regardless of metadata
        user_id: Optional user ID who initiated the sync
        
    Returns:
        Dictionary with execution results
    """
    task_id = self.request.id
    session_uuid = UUID(session_id)
    
    logger.info(f"Starting sync execution for session {session_id}, task {task_id}")
    
    try:
        # Run the async sync operation
        result = asyncio.run(_execute_sync_session_async(
            task_id=task_id,
            session_id=session_uuid,
            dry_run=dry_run,
            force_overwrite=force_overwrite,
            user_id=user_id
        ))
        
        logger.info(f"Sync execution completed for session {session_id}")
        return result
        
    except Exception as e:
        logger.error(f"Sync execution failed for session {session_id}: {e}")
        
        # Update execution status to failed
        asyncio.run(_update_execution_status(
            task_id=task_id,
            status=ExecutionStatus.FAILED,
            error_message=str(e)
        ))
        
        raise


async def _execute_sync_session_async(
    task_id: str,
    session_id: UUID,
    dry_run: bool,
    force_overwrite: bool,
    user_id: Optional[str]
) -> Dict[str, Any]:
    """Async implementation of sync session execution."""
    
    async with async_session_maker() as db:
        try:
            # Get session details
            session_repo = SessionRepository(db)
            session = await session_repo.get_by_id(session_id)
            
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            if not session.is_active:
                raise ValueError(f"Session {session_id} is not active")
            
            # Create execution record
            execution_repo = ExecutionRepository(db)
            execution_data = {
                'id': UUID(task_id),
                'session_id': session_id,
                'status': ExecutionStatus.RUNNING,
                'is_dry_run': dry_run,
                'started_at': datetime.now(timezone.utc)
            }
            
            execution = await execution_repo.create(execution_data)
            await db.commit()
            
            # Initialize sync engine
            sync_engine = SyncEngine()
            
            # Update task progress
            current_task.update_state(
                state='PROGRESS',
                meta={
                    'current': 0,
                    'total': 100,
                    'status': 'Initializing sync...',
                    'execution_id': str(execution.id)
                }
            )
            
            # Execute sync with progress callback
            def progress_callback(current: int, total: int, message: str):
                current_task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': current,
                        'total': total,
                        'status': message,
                        'execution_id': str(execution.id)
                    }
                )
            
            # Perform the actual sync
            sync_result = await sync_engine.execute_session_sync(
                session=session,
                execution=execution,
                dry_run=dry_run,
                force_overwrite=force_overwrite,
                progress_callback=progress_callback,
                db=db
            )
            
            # Update execution with results
            execution_update = {
                'status': ExecutionStatus.COMPLETED if sync_result['success'] else ExecutionStatus.FAILED,
                'completed_at': datetime.now(timezone.utc),
                'files_processed': sync_result.get('files_processed', 0),
                'files_transferred': sync_result.get('files_transferred', 0),
                'bytes_transferred': sync_result.get('bytes_transferred', 0),
                'errors_count': sync_result.get('errors_count', 0),
                'summary': sync_result.get('summary', {})
            }
            
            if not sync_result['success']:
                execution_update['error_message'] = sync_result.get('error_message', 'Unknown error')
            
            await execution_repo.update(execution.id, execution_update)
            await db.commit()
            
            return {
                'success': sync_result['success'],
                'execution_id': str(execution.id),
                'files_processed': sync_result.get('files_processed', 0),
                'files_transferred': sync_result.get('files_transferred', 0),
                'bytes_transferred': sync_result.get('bytes_transferred', 0),
                'duration_seconds': sync_result.get('duration_seconds', 0),
                'summary': sync_result.get('summary', {}),
                'error_message': sync_result.get('error_message') if not sync_result['success'] else None
            }
            
        except Exception as e:
            logger.error(f"Error in sync execution: {e}")
            raise


async def _update_execution_status(
    task_id: str,
    status: ExecutionStatus,
    error_message: Optional[str] = None
):
    """Update execution status in database."""
    async with async_session_maker() as db:
        try:
            execution_repo = ExecutionRepository(db)
            update_data = {
                'status': status,
                'updated_at': datetime.now(timezone.utc)
            }
            
            if error_message:
                update_data['error_message'] = error_message
            
            if status in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
                update_data['completed_at'] = datetime.now(timezone.utc)
            
            await execution_repo.update(UUID(task_id), update_data)
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to update execution status: {e}")


@celery_app.task(name="app.tasks.sync_tasks.cancel_sync_execution")
def cancel_sync_execution(execution_id: str) -> Dict[str, Any]:
    """
    Cancel a running sync execution.
    
    Args:
        execution_id: UUID of the execution to cancel
        
    Returns:
        Dictionary with cancellation result
    """
    logger.info(f"Cancelling sync execution {execution_id}")
    
    try:
        # Update execution status
        asyncio.run(_update_execution_status(
            task_id=execution_id,
            status=ExecutionStatus.CANCELLED
        ))
        
        # Revoke the Celery task
        celery_app.control.revoke(execution_id, terminate=True)
        
        return {
            'success': True,
            'message': f'Execution {execution_id} cancelled successfully'
        }
        
    except Exception as e:
        logger.error(f"Failed to cancel execution {execution_id}: {e}")
        return {
            'success': False,
            'message': f'Failed to cancel execution: {str(e)}'
        }


@celery_app.task(name="app.tasks.sync_tasks.process_scheduled_sessions")
def process_scheduled_sessions() -> Dict[str, Any]:
    """
    Process sessions that are due for scheduled execution.
    
    Returns:
        Dictionary with processing results
    """
    logger.info("Processing scheduled sessions")
    
    try:
        result = asyncio.run(_process_scheduled_sessions_async())
        return result
        
    except Exception as e:
        logger.error(f"Failed to process scheduled sessions: {e}")
        return {
            'success': False,
            'message': str(e),
            'sessions_processed': 0
        }


async def _process_scheduled_sessions_async() -> Dict[str, Any]:
    """Async implementation of scheduled session processing."""
    async with async_session_maker() as db:
        try:
            session_repo = SessionRepository(db)
            
            # Get sessions due for execution
            due_sessions = await session_repo.get_sessions_due_for_execution()
            
            sessions_queued = 0
            
            for session in due_sessions:
                try:
                    # Check if session is already running
                    if await session_repo.is_session_running(session.id):
                        logger.info(f"Session {session.id} is already running, skipping")
                        continue
                    
                    # Queue sync task
                    execute_sync_session.delay(
                        session_id=str(session.id),
                        dry_run=False,
                        force_overwrite=False
                    )
                    
                    sessions_queued += 1
                    logger.info(f"Queued scheduled session {session.id} ({session.name})")
                    
                except Exception as e:
                    logger.error(f"Failed to queue session {session.id}: {e}")
            
            return {
                'success': True,
                'sessions_processed': len(due_sessions),
                'sessions_queued': sessions_queued
            }
            
        except Exception as e:
            logger.error(f"Error processing scheduled sessions: {e}")
            raise


@celery_app.task(name="app.tasks.sync_tasks.get_sync_progress")
def get_sync_progress(execution_id: str) -> Dict[str, Any]:
    """
    Get progress information for a sync execution.
    
    Args:
        execution_id: UUID of the execution
        
    Returns:
        Dictionary with progress information
    """
    try:
        # Get task result
        result = celery_app.AsyncResult(execution_id)
        
        if result.state == 'PROGRESS':
            return {
                'status': 'running',
                'progress': result.info
            }
        elif result.state == 'SUCCESS':
            return {
                'status': 'completed',
                'result': result.result
            }
        elif result.state == 'FAILURE':
            return {
                'status': 'failed',
                'error': str(result.info)
            }
        else:
            return {
                'status': result.state.lower(),
                'info': result.info
            }
            
    except Exception as e:
        logger.error(f"Failed to get sync progress for {execution_id}: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }
