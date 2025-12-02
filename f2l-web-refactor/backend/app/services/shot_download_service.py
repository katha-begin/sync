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
        version_strategy: str = 'latest',
        specific_version: Optional[str] = None,
        custom_versions: Optional[Dict[str, any]] = None,  # Can be str or List[str]
        conflict_strategy: str = 'skip',
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
            version_strategy: 'latest', 'specific', 'all', 'custom'
            specific_version: Version to download when strategy is 'specific' (e.g., 'v005')
            custom_versions: Dict mapping shot_key to version when strategy is 'custom'
            conflict_strategy: 'skip', 'overwrite', 'compare', 'keep_both'
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
            version_strategy=version_strategy,
            specific_version=specific_version,
            conflict_strategy=conflict_strategy,
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

                # Only add if FTP has content (comparison has available versions)
                if comparison.needs_update or (comparison.available_versions and len(comparison.available_versions) > 0):
                    # Determine versions to download for custom strategy
                    versions_to_download = []

                    if version_strategy == 'custom' and custom_versions:
                        # Use the new key format: episode|sequence|shot|department
                        shot_key = f"{comparison.episode}|{comparison.sequence}|{comparison.shot}|{comparison.department}"
                        custom_value = custom_versions.get(shot_key)

                        if custom_value:
                            # Handle both single version (string) and multiple versions (list)
                            if isinstance(custom_value, list):
                                versions_to_download = custom_value
                            else:
                                versions_to_download = [custom_value]
                        else:
                            # Fallback to latest if no custom selection
                            versions_to_download = [comparison.latest_version] if comparison.latest_version else []
                    else:
                        # Non-custom strategy: single version
                        versions_to_download = [comparison.latest_version] if comparison.latest_version else []

                    # Create one item per version to download
                    for version in versions_to_download:
                        if not version:
                            continue

                        item = ShotDownloadItem(
                            id=uuid4(),
                            task_id=task.id,
                            episode=comparison.episode,
                            sequence=comparison.sequence,
                            shot=comparison.shot,
                            department=comparison.department,
                            ftp_version=comparison.ftp_version,
                            local_version=comparison.local_version,
                            selected_version=version,  # The specific version for this item
                            available_versions=comparison.available_versions,
                            latest_version=comparison.latest_version,
                            ftp_path=comparison.ftp_path,
                            local_path=comparison.local_path,
                            status=ShotDownloadItemStatus.PENDING,
                            file_count=comparison.file_count,
                            total_size=comparison.total_size,
                            downloaded_size=0,
                            files_skipped=0,
                            files_overwritten=0,
                            files_kept_both=0
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

        # If path is relative, join with /mnt (the base mount point)
        import os
        local_path = endpoint['local_path']
        if not local_path.startswith('/'):
            full_path = os.path.join('/mnt', local_path)
        else:
            full_path = local_path

        # Create Local manager
        local_config = LocalConfig(base_path=full_path)
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

    def _determine_version_to_download(self, item: ShotDownloadItem) -> Optional[str]:
        """
        Determine which version to download based on task's version strategy.

        Args:
            item: ShotDownloadItem with version information

        Returns:
            Version string (e.g., 'v005') or None if version not available
        """
        strategy = item.task.version_strategy

        if strategy == 'latest':
            # Download latest version
            return item.latest_version or item.ftp_version

        elif strategy == 'specific':
            # Download specific version if available
            specific_version = item.task.specific_version
            if specific_version in (item.available_versions or []):
                return specific_version
            else:
                logger.warning(
                    f"Version {specific_version} not available for {item.shot}/{item.department}, "
                    f"available: {item.available_versions}"
                )
                return None

        elif strategy == 'custom':
            # Download custom selected version
            return item.selected_version or item.latest_version

        elif strategy == 'all':
            # For 'all' strategy, this method shouldn't be called
            # Instead, _download_all_versions should be called
            logger.warning("_determine_version_to_download called with 'all' strategy")
            return item.latest_version

        # Default to latest
        return item.latest_version or item.ftp_version

    async def _download_anim_version(
        self,
        ftp_manager: FTPManager,
        local_manager: LocalManager,
        item: ShotDownloadItem
    ):
        """Download animation version directory with version selection and conflict handling."""
        import os

        # Determine which version to download based on strategy
        version_to_download = self._determine_version_to_download(item)

        if not version_to_download:
            logger.warning(f"No version to download for {item.shot}/{item.department}, skipping")
            item.status = ShotDownloadItemStatus.FAILED
            item.error_message = "No version available to download"
            await self.db.commit()
            return

        # Build version path
        version_path = f"{item.ftp_path}/{version_to_download}"

        # Convert relative local path to absolute path
        local_path = item.local_path
        if not local_path.startswith('/'):
            local_path = os.path.join('/mnt', local_path)

        local_version_path = os.path.join(local_path, version_to_download)

        # Create local directory
        os.makedirs(local_version_path, exist_ok=True)

        # List all files in version directory (recursive)
        loop = asyncio.get_event_loop()
        file_infos = await loop.run_in_executor(None, ftp_manager.list_directory, version_path, True)

        logger.info(f"Downloading {len(file_infos)} files from {version_path} (version: {version_to_download})")

        # Get conflict strategy
        conflict_strategy = item.task.conflict_strategy

        # Download each file with conflict handling
        for file_info in file_infos:
            if file_info.is_file:
                # Extract relative path from full path
                remote_file = file_info.path
                relative_path = remote_file.replace(version_path + '/', '')
                local_file = os.path.join(local_version_path, relative_path)

                # Create subdirectories if needed
                local_dir = os.path.dirname(local_file)
                os.makedirs(local_dir, exist_ok=True)

                # Download file with conflict handling
                result = await loop.run_in_executor(
                    None,
                    ftp_manager.download_file_with_conflict_handling,
                    remote_file,
                    local_file,
                    conflict_strategy
                )

                # Update statistics based on action
                if result.get('success'):
                    action = result.get('action', 'downloaded')
                    if action == 'skipped':
                        item.files_skipped += 1
                    elif action == 'overwritten':
                        item.files_overwritten += 1
                    elif action == 'kept_both':
                        item.files_kept_both += 1

                    await self.db.commit()
                    logger.debug(f"{action.capitalize()}: {remote_file} -> {local_file}")

    async def _download_lighting_files(
        self,
        ftp_manager: FTPManager,
        local_manager: LocalManager,
        item: ShotDownloadItem
    ):
        """Download lighting files with version selection and conflict handling."""
        import os
        import re

        # Convert relative local path to absolute path
        local_path = item.local_path
        if not local_path.startswith('/'):
            local_path = os.path.join('/mnt', local_path)

        # Create local directory
        os.makedirs(local_path, exist_ok=True)

        # Get comparison to know which files to download
        comparison = await self.comparison_service.compare_shot(
            endpoint_id=item.task.endpoint_id,
            episode=item.episode,
            sequence=item.sequence,
            shot=item.shot,
            department=item.department
        )

        # Get the selected version for this item
        selected_version = item.selected_version

        # Filter files by selected version if custom strategy
        files_to_download = comparison.files_to_download
        if selected_version and item.task.version_strategy == 'custom':
            # Filter to only files matching the selected version
            # Version pattern in filename: _v001, _v002, etc.
            version_pattern = f"_{selected_version}"
            files_to_download = [
                f for f in files_to_download
                if version_pattern in f.get('name', '')
            ]
            logger.info(f"Filtered to {len(files_to_download)} files for version {selected_version}")

        logger.info(f"Downloading {len(files_to_download)} lighting files")

        # Get conflict strategy
        conflict_strategy = item.task.conflict_strategy

        # Download each file with conflict handling
        loop = asyncio.get_event_loop()
        for file_info in files_to_download:
            remote_file = f"{item.ftp_path}/{file_info['name']}"
            local_file = os.path.join(local_path, file_info['name'])

            # Download file with conflict handling
            result = await loop.run_in_executor(
                None,
                ftp_manager.download_file_with_conflict_handling,
                remote_file,
                local_file,
                conflict_strategy
            )

            # Update statistics based on action
            if result.get('success'):
                action = result.get('action', 'downloaded')
                if action == 'skipped':
                    item.files_skipped += 1
                elif action == 'overwritten':
                    item.files_overwritten += 1
                elif action == 'kept_both':
                    item.files_kept_both += 1

                await self.db.commit()
                logger.debug(f"{action.capitalize()}: {remote_file} -> {local_file}")

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



