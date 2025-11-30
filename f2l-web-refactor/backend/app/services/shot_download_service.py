"""
Shot Download Service - Manage shot download tasks and execution.

This service provides:
- Create download tasks from user selections
- Execute downloads using existing SyncEngine
- Track download progress and status
- Manage download queue
"""
import logging
import asyncio
from typing import List, Dict, Optional, Callable
from uuid import UUID, uuid4
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database.models import (
    Endpoint,
    ShotDownloadTask, ShotDownloadTaskStatus,
    ShotDownloadItem, ShotDownloadItemStatus
)
from app.repositories.endpoint_repository import EndpointRepository
from app.core.sync_engine import SyncEngine
from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.local_manager import LocalManager, LocalConfig
from app.services.shot_comparison_service import ShotComparisonService, ShotComparison
from app.utils.shot_path_utils import ShotPathUtils

logger = logging.getLogger(__name__)


class ShotDownloadService:
    """
    Service for managing shot download tasks.
    
    Features:
    - Create tasks from comparison results
    - Execute downloads using SyncEngine
    - Track progress in real-time
    - Handle errors gracefully
    """
    
    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.endpoint_repo = EndpointRepository(db)
        self.comparison_service = ShotComparisonService(db)
        self.sync_engine = SyncEngine()
    
    async def create_download_task(
        self,
        endpoint_id: UUID,
        task_name: str,
        shots: List[Dict[str, str]],
        departments: List[str],
        created_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Create a download task from user selections.
        
        Args:
            endpoint_id: Endpoint UUID
            task_name: User-friendly task name
            shots: List of dicts with 'episode', 'sequence', 'shot' keys
            departments: List of departments to download ('anim', 'lighting')
            created_by: Username who created the task
            notes: Optional notes
        
        Returns:
            Dict with task information
        """
        logger.info(f"Creating download task '{task_name}' for {len(shots)} shots")
        
        # Create task record
        task = ShotDownloadTask(
            id=uuid4(),
            name=task_name,
            endpoint_id=endpoint_id,
            status=ShotDownloadTaskStatus.PENDING,
            total_items=0,
            completed_items=0,
            failed_items=0,
            total_size=0,
            downloaded_size=0,
            created_by=created_by,
            notes=notes
        )
        self.db.add(task)
        await self.db.flush()
        
        # Compare shots and create download items
        items_to_create = []
        total_size = 0
        
        for shot in shots:
            for department in departments:
                # Compare shot
                comparison = await self.comparison_service.compare_shot(
                    endpoint_id=endpoint_id,
                    episode=shot["episode"],
                    sequence=shot["sequence"],
                    shot=shot["shot"],
                    department=department
                )
                
                # Only add if needs update
                if comparison.needs_update:
                    item = ShotDownloadItem(
                        id=uuid4(),
                        task_id=task.id,
                        episode=comparison.episode,
                        sequence=comparison.sequence,
                        shot=comparison.shot,
                        department=comparison.department,
                        ftp_version=comparison.ftp_version,
                        local_version=comparison.local_version,
                        ftp_path=comparison.ftp_path,
                        local_path=comparison.local_path,
                        status=ShotDownloadItemStatus.PENDING,
                        file_count=comparison.file_count,
                        total_size=comparison.total_size,
                        downloaded_size=0
                    )
                    items_to_create.append(item)
                    total_size += comparison.total_size
        
        # Update task totals
        task.total_items = len(items_to_create)
        task.total_size = total_size
        
        # Add all items
        for item in items_to_create:
            self.db.add(item)
        
        await self.db.commit()
        
        logger.info(
            f"Created task {task.id} with {task.total_items} items "
            f"({task.total_size / (1024**3):.2f} GB)"
        )
        
        return {
            "success": True,
            "task_id": str(task.id),
            "task_name": task.name,
            "total_items": task.total_items,
            "total_size": task.total_size,
            "status": task.status.value
        }

    async def execute_download_task(
        self,
        task_id: UUID,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, any]:
        """
        Execute a download task.

        Args:
            task_id: Task UUID to execute
            progress_callback: Optional callback(completed, total, message)

        Returns:
            Dict with execution results
        """
        logger.info(f"Executing download task {task_id}")

        # Get task
        result = await self.db.execute(
            select(ShotDownloadTask).where(ShotDownloadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status == ShotDownloadTaskStatus.RUNNING:
            raise ValueError(f"Task {task_id} is already running")

        # Update task status
        task.status = ShotDownloadTaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        try:
            # Get endpoint
            endpoint = await self.endpoint_repo.get_with_decrypted_password(task.endpoint_id)
            if not endpoint:
                raise ValueError(f"Endpoint {task.endpoint_id} not found")

            # Get all pending items
            items_result = await self.db.execute(
                select(ShotDownloadItem)
                .where(ShotDownloadItem.task_id == task_id)
                .where(ShotDownloadItem.status == ShotDownloadItemStatus.PENDING)
                .order_by(ShotDownloadItem.episode, ShotDownloadItem.sequence, ShotDownloadItem.shot)
            )
            items = items_result.scalars().all()

            logger.info(f"Found {len(items)} items to download")

            # Execute each item
            completed = 0
            failed = 0

            for item in items:
                try:
                    if progress_callback:
                        progress_callback(
                            completed,
                            len(items),
                            f"Downloading {item.episode}/{item.sequence}/{item.shot}/{item.department}"
                        )

                    # Download item
                    await self._download_item(endpoint, item)

                    # Update item status
                    item.status = ShotDownloadItemStatus.COMPLETED
                    item.completed_at = datetime.now(timezone.utc)
                    completed += 1

                except Exception as e:
                    logger.error(f"Failed to download item {item.id}: {e}")
                    item.status = ShotDownloadItemStatus.FAILED
                    item.error_message = str(e)
                    item.completed_at = datetime.now(timezone.utc)
                    failed += 1

                await self.db.commit()

            # Update task status
            task.completed_items = completed
            task.failed_items = failed
            task.status = ShotDownloadTaskStatus.COMPLETED if failed == 0 else ShotDownloadTaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            await self.db.commit()

            if progress_callback:
                progress_callback(completed, len(items), "Download completed")

            logger.info(
                f"Task {task_id} completed: {completed} succeeded, {failed} failed"
            )

            return {
                "success": True,
                "task_id": str(task.id),
                "completed_items": completed,
                "failed_items": failed,
                "status": task.status.value
            }

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            task.status = ShotDownloadTaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            await self.db.commit()

            return {
                "success": False,
                "task_id": str(task.id),
                "error": str(e),
                "status": task.status.value
            }

    async def _download_item(
        self,
        endpoint: Dict[str, any],
        item: ShotDownloadItem
    ):
        """
        Download a single shot/department item.

        Args:
            endpoint: Endpoint configuration dict
            item: ShotDownloadItem to download
        """
        logger.info(
            f"Downloading {item.episode}/{item.sequence}/{item.shot}/{item.department} "
            f"from {item.ftp_path} to {item.local_path}"
        )

        # Update item status
        item.status = ShotDownloadItemStatus.DOWNLOADING
        item.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        # Create FTP manager
        ftp_config = FTPConfig(
            host=endpoint['host'],
            username=endpoint['username'],
            password=endpoint.get('password', ''),
            port=endpoint.get('port', 21)
        )
        ftp_manager = FTPManager(ftp_config)

        # Create Local manager
        local_config = LocalConfig(base_path=endpoint['local_path'])
        local_manager = LocalManager(local_config)

        try:
            # Connect
            if not ftp_manager.connect():
                raise ConnectionError("Failed to connect to FTP")

            if not local_manager.connect():
                raise ConnectionError("Failed to access local path")

            # Download based on department
            if item.department == "anim":
                await self._download_anim_version(ftp_manager, local_manager, item)
            elif item.department == "lighting":
                await self._download_lighting_files(ftp_manager, local_manager, item)
            else:
                raise ValueError(f"Unsupported department: {item.department}")

            # Update downloaded size
            item.downloaded_size = item.total_size

        finally:
            ftp_manager.close()
            local_manager.close()

    async def _download_anim_version(
        self,
        ftp_manager: FTPManager,
        local_manager: LocalManager,
        item: ShotDownloadItem
    ):
        """Download animation version directory."""
        import os

        # Build version path
        version_path = f"{item.ftp_path}/{item.ftp_version}"
        local_version_path = os.path.join(item.local_path, item.ftp_version)

        # Create local directory
        os.makedirs(local_version_path, exist_ok=True)

        # List all files in version directory (recursive)
        loop = asyncio.get_event_loop()
        files = await loop.run_in_executor(None, ftp_manager.list_files, version_path, True)

        logger.info(f"Downloading {len(files)} files from {version_path}")

        # Download each file
        for file_info in files:
            if file_info.get("is_file", True):
                remote_file = f"{version_path}/{file_info['name']}"
                local_file = os.path.join(local_version_path, file_info['name'])

                # Create subdirectories if needed
                local_dir = os.path.dirname(local_file)
                os.makedirs(local_dir, exist_ok=True)

                # Download file
                await loop.run_in_executor(
                    None,
                    ftp_manager.download_file,
                    remote_file,
                    local_file
                )

                logger.debug(f"Downloaded {remote_file} -> {local_file}")

    async def _download_lighting_files(
        self,
        ftp_manager: FTPManager,
        local_manager: LocalManager,
        item: ShotDownloadItem
    ):
        """Download lighting files."""
        import os

        # Create local directory
        os.makedirs(item.local_path, exist_ok=True)

        # Get comparison to know which files to download
        comparison = await self.comparison_service.compare_shot(
            endpoint_id=item.task.endpoint_id,
            episode=item.episode,
            sequence=item.sequence,
            shot=item.shot,
            department=item.department
        )

        logger.info(f"Downloading {len(comparison.files_to_download)} lighting files")

        # Download each file
        loop = asyncio.get_event_loop()
        for file_info in comparison.files_to_download:
            remote_file = f"{item.ftp_path}/{file_info['name']}"
            local_file = os.path.join(item.local_path, file_info['name'])

            # Download file
            await loop.run_in_executor(
                None,
                ftp_manager.download_file,
                remote_file,
                local_file
            )

            logger.debug(f"Downloaded {remote_file} -> {local_file}")

    async def get_task_status(self, task_id: UUID) -> Dict[str, any]:
        """
        Get current status of a download task.

        Args:
            task_id: Task UUID

        Returns:
            Dict with task status and progress
        """
        result = await self.db.execute(
            select(ShotDownloadTask).where(ShotDownloadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Calculate progress
        progress_percent = 0
        if task.total_items > 0:
            progress_percent = int((task.completed_items / task.total_items) * 100)

        return {
            "task_id": str(task.id),
            "name": task.name,
            "status": task.status.value,
            "total_items": task.total_items,
            "completed_items": task.completed_items,
            "failed_items": task.failed_items,
            "total_size": task.total_size,
            "downloaded_size": task.downloaded_size,
            "progress_percent": progress_percent,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_by": task.created_by,
            "notes": task.notes
        }

    async def get_task_details(self, task_id: UUID) -> Dict[str, any]:
        """
        Get detailed information about a task including all items.

        Args:
            task_id: Task UUID

        Returns:
            Dict with task and items details
        """
        # Get task
        result = await self.db.execute(
            select(ShotDownloadTask).where(ShotDownloadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Get all items
        items_result = await self.db.execute(
            select(ShotDownloadItem)
            .where(ShotDownloadItem.task_id == task_id)
            .order_by(ShotDownloadItem.episode, ShotDownloadItem.sequence, ShotDownloadItem.shot)
        )
        items = items_result.scalars().all()

        # Format items
        items_data = []
        for item in items:
            items_data.append({
                "id": str(item.id),
                "episode": item.episode,
                "sequence": item.sequence,
                "shot": item.shot,
                "department": item.department,
                "ftp_version": item.ftp_version,
                "local_version": item.local_version,
                "status": item.status.value,
                "file_count": item.file_count,
                "total_size": item.total_size,
                "downloaded_size": item.downloaded_size,
                "error_message": item.error_message,
                "started_at": item.started_at.isoformat() if item.started_at else None,
                "completed_at": item.completed_at.isoformat() if item.completed_at else None
            })

        return {
            "task": await self.get_task_status(task_id),
            "items": items_data
        }

    async def list_tasks(
        self,
        endpoint_id: Optional[UUID] = None,
        status: Optional[ShotDownloadTaskStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, any]]:
        """
        List download tasks with optional filters.

        Args:
            endpoint_id: Filter by endpoint
            status: Filter by status
            limit: Max results
            offset: Pagination offset

        Returns:
            List of task summaries
        """
        query = select(ShotDownloadTask).order_by(ShotDownloadTask.created_at.desc())

        if endpoint_id:
            query = query.where(ShotDownloadTask.endpoint_id == endpoint_id)

        if status:
            query = query.where(ShotDownloadTask.status == status)

        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        tasks_data = []
        for task in tasks:
            progress_percent = 0
            if task.total_items > 0:
                progress_percent = int((task.completed_items / task.total_items) * 100)

            tasks_data.append({
                "task_id": str(task.id),
                "name": task.name,
                "status": task.status.value,
                "total_items": task.total_items,
                "completed_items": task.completed_items,
                "failed_items": task.failed_items,
                "progress_percent": progress_percent,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "created_by": task.created_by
            })

        return tasks_data

    async def delete_task(self, task_id: UUID) -> Dict[str, any]:
        """
        Delete a download task and all its items.

        Args:
            task_id: Task UUID to delete

        Returns:
            Dict with deletion result
        """
        # Get task
        result = await self.db.execute(
            select(ShotDownloadTask).where(ShotDownloadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        # Don't delete running tasks
        if task.status == ShotDownloadTaskStatus.RUNNING:
            raise ValueError("Cannot delete a running task")

        # Delete task (items will be cascade deleted)
        await self.db.delete(task)
        await self.db.commit()

        logger.info(f"Deleted task {task_id}")

        return {
            "success": True,
            "task_id": str(task_id),
            "message": "Task deleted successfully"
        }

    async def cancel_task(self, task_id: UUID) -> Dict[str, any]:
        """
        Cancel a running download task.

        Args:
            task_id: Task UUID to cancel

        Returns:
            Dict with cancellation result
        """
        # Get task
        result = await self.db.execute(
            select(ShotDownloadTask).where(ShotDownloadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status != ShotDownloadTaskStatus.RUNNING:
            raise ValueError("Can only cancel running tasks")

        # Update task status
        task.status = ShotDownloadTaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)
        await self.db.commit()

        logger.info(f"Cancelled task {task_id}")

        return {
            "success": True,
            "task_id": str(task_id),
            "status": task.status.value,
            "message": "Task cancelled successfully"
        }



