"""
Shot Upload Service - Manage shot upload tasks and execution.

This service provides:
- Scan local source directory for shots
- Create upload tasks from user selections
- Execute uploads to FTP/SFTP target
- Track upload progress and status
- Record upload history
"""
import logging
import asyncio
import os
import re
from typing import List, Dict, Optional, Callable
from uuid import UUID, uuid4
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from app.database.models import (
    Endpoint, EndpointType,
    ShotUploadTask, ShotUploadTaskStatus,
    ShotUploadItem, ShotUploadItemStatus,
    ShotUploadHistory
)
from app.repositories.endpoint_repository import EndpointRepository
from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.sftp_manager import SFTPManager, SFTPConfig
from app.core.local_manager import LocalManager, LocalConfig

logger = logging.getLogger(__name__)


class ShotUploadService:
    """
    Service for managing shot upload tasks.

    Features:
    - Scan local directories for shot files
    - Create upload tasks from selections
    - Execute uploads to target endpoints
    - Track progress in real-time
    - Handle file conflicts
    - Record upload history
    """

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.endpoint_repo = EndpointRepository(db)

    async def scan_local_structure(
        self,
        endpoint_id: UUID,
        episode_filter: Optional[str] = None,
        sequence_filter: Optional[str] = None,
        department_filter: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Scan local endpoint for shot structure.

        Args:
            endpoint_id: Local endpoint UUID
            episode_filter: Optional episode to filter
            sequence_filter: Optional sequence to filter
            department_filter: Optional department to filter

        Returns:
            Dict with hierarchical structure of episodes/sequences/shots/files
        """
        logger.info(f"Scanning local structure for endpoint {endpoint_id}")

        endpoint = await self.endpoint_repo.get_by_id(endpoint_id)
        if not endpoint:
            raise ValueError(f"Endpoint {endpoint_id} not found")

        if endpoint.endpoint_type != EndpointType.LOCAL:
            raise ValueError(f"Endpoint {endpoint_id} is not a local endpoint")

        local_path = endpoint.local_path
        if not local_path or not os.path.exists(local_path):
            raise ValueError(f"Local path '{local_path}' does not exist")

        structure = {
            "endpoint_id": str(endpoint_id),
            "endpoint_name": endpoint.name,
            "root_path": local_path,
            "episodes": []
        }

        # Scan episodes
        try:
            for ep_name in sorted(os.listdir(local_path)):
                ep_path = os.path.join(local_path, ep_name)
                if not os.path.isdir(ep_path):
                    continue
                if episode_filter and ep_name != episode_filter:
                    continue

                episode_data = {
                    "name": ep_name,
                    "path": ep_path,
                    "sequences": []
                }

                # Scan sequences
                for seq_name in sorted(os.listdir(ep_path)):
                    seq_path = os.path.join(ep_path, seq_name)
                    if not os.path.isdir(seq_path):
                        continue
                    if sequence_filter and seq_name != sequence_filter:
                        continue

                    sequence_data = {
                        "name": seq_name,
                        "path": seq_path,
                        "shots": []
                    }

                    # Scan shots
                    for shot_name in sorted(os.listdir(seq_path)):
                        shot_path = os.path.join(seq_path, shot_name)
                        if not os.path.isdir(shot_path):
                            continue

                        shot_data = {
                            "name": shot_name,
                            "path": shot_path,
                            "departments": []
                        }

                        # Scan departments
                        for dept_name in sorted(os.listdir(shot_path)):
                            dept_path = os.path.join(shot_path, dept_name)
                            if not os.path.isdir(dept_path):
                                continue
                            if department_filter and dept_name != department_filter:
                                continue

                            # Check for output folder
                            output_path = os.path.join(dept_path, "output")
                            if not os.path.exists(output_path):
                                continue

                            files = self._scan_output_files(output_path)
                            if files:
                                shot_data["departments"].append({
                                    "name": dept_name,
                                    "path": dept_path,
                                    "output_path": output_path,
                                    "files": files
                                })

                        if shot_data["departments"]:
                            sequence_data["shots"].append(shot_data)

                    if sequence_data["shots"]:
                        episode_data["sequences"].append(sequence_data)

                if episode_data["sequences"]:
                    structure["episodes"].append(episode_data)

        except Exception as e:
            logger.error(f"Error scanning local structure: {e}")
            raise

        return structure

    def _scan_output_files(self, output_path: str) -> List[Dict]:
        """Scan output directory for uploadable files."""
        files = []
        try:
            for filename in os.listdir(output_path):
                file_path = os.path.join(output_path, filename)
                if not os.path.isfile(file_path):
                    continue

                # Extract version from filename (e.g., Ep02_sq0010_SH0010_v001.mov)
                version = self._extract_version(filename)

                stat = os.stat(file_path)
                files.append({
                    "filename": filename,
                    "path": file_path,
                    "version": version,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
                })
        except Exception as e:
            logger.warning(f"Error scanning output files in {output_path}: {e}")

        return sorted(files, key=lambda x: x.get("version", ""), reverse=True)

    def _extract_version(self, filename: str) -> Optional[str]:
        """Extract version number from filename."""
        match = re.search(r'_v(\d+)', filename, re.IGNORECASE)
        if match:
            return f"v{match.group(1)}"
        return None

    async def create_upload_task(
        self,
        source_endpoint_id: UUID,
        target_endpoint_id: UUID,
        task_name: str,
        items: List[Dict],
        version_strategy: str = 'latest',
        specific_version: Optional[str] = None,
        conflict_strategy: str = 'skip',
        created_by: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Create an upload task from user selections.

        Args:
            source_endpoint_id: Local source endpoint UUID
            target_endpoint_id: FTP/SFTP target endpoint UUID
            task_name: User-friendly task name
            items: List of file items to upload
            version_strategy: 'latest', 'specific', 'custom'
            specific_version: Version when strategy is 'specific'
            conflict_strategy: 'skip', 'overwrite'
            created_by: Username who created the task
            notes: Optional notes

        Returns:
            Dict with task information
        """
        logger.info(f"Creating upload task '{task_name}' with {len(items)} items")

        # Validate endpoints
        source_endpoint = await self.endpoint_repo.get_by_id(source_endpoint_id)
        target_endpoint = await self.endpoint_repo.get_by_id(target_endpoint_id)

        if not source_endpoint:
            raise ValueError(f"Source endpoint {source_endpoint_id} not found")
        if not target_endpoint:
            raise ValueError(f"Target endpoint {target_endpoint_id} not found")
        if source_endpoint.endpoint_type != EndpointType.LOCAL:
            raise ValueError("Source endpoint must be a local endpoint")
        if target_endpoint.endpoint_type not in [EndpointType.FTP, EndpointType.SFTP]:
            raise ValueError("Target endpoint must be FTP or SFTP")

        source_root = source_endpoint.local_path
        target_root = target_endpoint.remote_path

        # Create task
        task = ShotUploadTask(
            id=uuid4(),
            name=task_name,
            source_endpoint_id=source_endpoint_id,
            target_endpoint_id=target_endpoint_id,
            status=ShotUploadTaskStatus.PENDING,
            version_strategy=version_strategy,
            specific_version=specific_version,
            conflict_strategy=conflict_strategy,
            total_items=0,
            completed_items=0,
            failed_items=0,
            skipped_items=0,
            total_size=0,
            uploaded_size=0,
            created_by=created_by,
            notes=notes
        )
        self.db.add(task)
        await self.db.flush()

        # Create upload items
        upload_items = []
        total_size = 0

        for item_data in items:
            source_path = item_data["source_path"]
            relative_path = source_path.replace(source_root, "").lstrip("/\\")
            target_path = os.path.join(target_root, relative_path).replace("\\", "/")

            upload_item = ShotUploadItem(
                id=uuid4(),
                task_id=task.id,
                episode=item_data.get("episode", ""),
                sequence=item_data.get("sequence", ""),
                shot=item_data.get("shot", ""),
                department=item_data.get("department", ""),
                filename=item_data.get("filename", os.path.basename(source_path)),
                version=item_data.get("version"),
                source_path=source_path,
                target_path=target_path,
                relative_path=relative_path,
                status=ShotUploadItemStatus.PENDING,
                file_size=item_data.get("size", 0),
                uploaded_size=0,
                target_exists=False
            )
            upload_items.append(upload_item)
            total_size += upload_item.file_size

        # Update task totals
        task.total_items = len(upload_items)
        task.total_size = total_size

        for item in upload_items:
            self.db.add(item)

        await self.db.commit()

        logger.info(
            f"Created upload task {task.id} with {task.total_items} items "
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

    async def execute_upload_task(
        self,
        task_id: UUID,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, any]:
        """
        Execute an upload task.

        Args:
            task_id: Task UUID to execute
            progress_callback: Optional callback(completed, total, message)

        Returns:
            Dict with execution results
        """
        logger.info(f"Executing upload task {task_id}")

        # Get task
        result = await self.db.execute(
            select(ShotUploadTask).where(ShotUploadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status == ShotUploadTaskStatus.RUNNING:
            raise ValueError(f"Task {task_id} is already running")

        # Update task status
        task.status = ShotUploadTaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        await self.db.commit()

        ftp_manager = None
        sftp_manager = None

        try:
            # Get endpoints
            source_endpoint = await self.endpoint_repo.get_by_id(task.source_endpoint_id)
            target_endpoint = await self.endpoint_repo.get_with_decrypted_password(task.target_endpoint_id)

            if not source_endpoint or not target_endpoint:
                raise ValueError("Source or target endpoint not found")

            # Create target manager (FTP or SFTP)
            if target_endpoint.endpoint_type == EndpointType.FTP:
                ftp_config = FTPConfig(
                    host=target_endpoint.host,
                    port=target_endpoint.port or 21,
                    username=target_endpoint.username,
                    password=target_endpoint.password,
                    remote_path=target_endpoint.remote_path or "/"
                )
                ftp_manager = FTPManager(ftp_config)
                ftp_manager.connect()
            else:
                sftp_config = SFTPConfig(
                    host=target_endpoint.host,
                    port=target_endpoint.port or 22,
                    username=target_endpoint.username,
                    password=target_endpoint.password,
                    remote_path=target_endpoint.remote_path or "/"
                )
                sftp_manager = SFTPManager(sftp_config)
                sftp_manager.connect()

            # Get pending items
            items_result = await self.db.execute(
                select(ShotUploadItem)
                .where(ShotUploadItem.task_id == task_id)
                .where(ShotUploadItem.status == ShotUploadItemStatus.PENDING)
                .order_by(ShotUploadItem.episode, ShotUploadItem.sequence, ShotUploadItem.shot)
            )
            items = items_result.scalars().all()

            logger.info(f"Found {len(items)} items to upload")

            completed = 0
            failed = 0
            skipped = 0

            for item in items:
                try:
                    # Check if target file exists
                    target_exists = await self._check_file_exists(
                        ftp_manager, sftp_manager, item.target_path
                    )
                    item.target_exists = target_exists

                    if target_exists and task.conflict_strategy == 'skip':
                        item.status = ShotUploadItemStatus.SKIPPED
                        item.completed_at = datetime.now(timezone.utc)
                        skipped += 1
                        logger.info(f"Skipped existing file: {item.filename}")
                    else:
                        # Upload file
                        item.status = ShotUploadItemStatus.UPLOADING
                        item.started_at = datetime.now(timezone.utc)
                        await self.db.commit()

                        await self._upload_file(
                            ftp_manager, sftp_manager,
                            item.source_path, item.target_path
                        )

                        item.status = ShotUploadItemStatus.COMPLETED
                        item.uploaded_size = item.file_size
                        item.completed_at = datetime.now(timezone.utc)
                        completed += 1
                        logger.info(f"Uploaded: {item.filename}")

                    # Record history
                    await self._record_history(task, item, source_endpoint.name, target_endpoint.name)

                except Exception as e:
                    item.status = ShotUploadItemStatus.FAILED
                    item.error_message = str(e)
                    item.completed_at = datetime.now(timezone.utc)
                    failed += 1
                    logger.error(f"Failed to upload {item.filename}: {e}")

                    # Record failed history
                    await self._record_history(
                        task, item, source_endpoint.name, target_endpoint.name, str(e)
                    )

                # Update task progress
                task.completed_items = completed
                task.failed_items = failed
                task.skipped_items = skipped
                task.uploaded_size += item.uploaded_size
                await self.db.commit()

                if progress_callback:
                    progress_callback(
                        completed + failed + skipped,
                        task.total_items,
                        f"Processed: {item.filename}"
                    )

            # Update final task status
            if failed == task.total_items:
                task.status = ShotUploadTaskStatus.FAILED
            else:
                task.status = ShotUploadTaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            await self.db.commit()

            return {
                "success": True,
                "task_id": str(task.id),
                "completed": completed,
                "failed": failed,
                "skipped": skipped,
                "total": task.total_items
            }

        except Exception as e:
            task.status = ShotUploadTaskStatus.FAILED
            task.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            logger.error(f"Upload task failed: {e}")
            raise

        finally:
            if ftp_manager:
                ftp_manager.disconnect()
            if sftp_manager:
                sftp_manager.disconnect()



    async def _check_file_exists(
        self,
        ftp_manager: Optional[FTPManager],
        sftp_manager: Optional[SFTPManager],
        remote_path: str
    ) -> bool:
        """Check if file exists on target."""
        try:
            if ftp_manager:
                file_info = ftp_manager.get_file_info(remote_path)
                return file_info is not None and file_info.get('exists', False)
            elif sftp_manager:
                return sftp_manager.file_exists(remote_path)
            return False
        except Exception:
            return False

    async def _upload_file(
        self,
        ftp_manager: Optional[FTPManager],
        sftp_manager: Optional[SFTPManager],
        source_path: str,
        target_path: str
    ) -> None:
        """Upload a file to target."""
        loop = asyncio.get_event_loop()

        if ftp_manager:
            # Ensure target directory exists
            target_dir = os.path.dirname(target_path)
            await loop.run_in_executor(
                None, ftp_manager.ensure_remote_directory, target_dir
            )
            # Upload file
            result = await loop.run_in_executor(
                None, ftp_manager.upload_file, source_path, target_path
            )
            if not result.get('success', False):
                raise Exception(result.get('error', 'Upload failed'))
        elif sftp_manager:
            result = await loop.run_in_executor(
                None, sftp_manager.upload_file, source_path, target_path
            )
            if not result.get('success', False):
                raise Exception(result.get('error', 'Upload failed'))

    async def _record_history(
        self,
        task: ShotUploadTask,
        item: ShotUploadItem,
        source_name: str,
        target_name: str,
        error_message: Optional[str] = None
    ) -> None:
        """Record upload history."""
        history = ShotUploadHistory(
            id=uuid4(),
            task_id=task.id,
            item_id=item.id,
            task_name=task.name,
            episode=item.episode,
            sequence=item.sequence,
            shot=item.shot,
            department=item.department,
            filename=item.filename,
            version=item.version,
            file_size=item.file_size,
            source_path=item.source_path,
            target_path=item.target_path,
            source_endpoint_name=source_name,
            target_endpoint_name=target_name,
            status=item.status.value,
            error_message=error_message,
            uploaded_by=task.created_by
        )
        self.db.add(history)

    async def get_task(self, task_id: UUID) -> Optional[Dict]:
        """Get task by ID with items."""
        result = await self.db.execute(
            select(ShotUploadTask).where(ShotUploadTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return None

        items_result = await self.db.execute(
            select(ShotUploadItem).where(ShotUploadItem.task_id == task_id)
        )
        items = items_result.scalars().all()

        return {
            "id": str(task.id),
            "name": task.name,
            "source_endpoint_id": str(task.source_endpoint_id),
            "target_endpoint_id": str(task.target_endpoint_id),
            "status": task.status.value,
            "version_strategy": task.version_strategy,
            "conflict_strategy": task.conflict_strategy,
            "total_items": task.total_items,
            "completed_items": task.completed_items,
            "failed_items": task.failed_items,
            "skipped_items": task.skipped_items,
            "total_size": task.total_size,
            "uploaded_size": task.uploaded_size,
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "created_by": task.created_by,
            "notes": task.notes,
            "items": [
                {
                    "id": str(item.id),
                    "episode": item.episode,
                    "sequence": item.sequence,
                    "shot": item.shot,
                    "department": item.department,
                    "filename": item.filename,
                    "version": item.version,
                    "source_path": item.source_path,
                    "target_path": item.target_path,
                    "status": item.status.value,
                    "file_size": item.file_size,
                    "uploaded_size": item.uploaded_size,
                    "target_exists": item.target_exists,
                    "error_message": item.error_message
                }
                for item in items
            ]
        }

    async def list_tasks(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, any]:
        """List upload tasks."""
        query = select(ShotUploadTask)

        if status:
            query = query.where(ShotUploadTask.status == ShotUploadTaskStatus(status))

        query = query.order_by(ShotUploadTask.created_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        # Get total count
        count_query = select(func.count(ShotUploadTask.id))
        if status:
            count_query = count_query.where(ShotUploadTask.status == ShotUploadTaskStatus(status))
        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        return {
            "tasks": [
                {
                    "id": str(task.id),
                    "name": task.name,
                    "status": task.status.value,
                    "total_items": task.total_items,
                    "completed_items": task.completed_items,
                    "failed_items": task.failed_items,
                    "skipped_items": task.skipped_items,
                    "total_size": task.total_size,
                    "uploaded_size": task.uploaded_size,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                    "created_by": task.created_by
                }
                for task in tasks
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }


    async def delete_task(self, task_id: UUID) -> bool:
        """Delete a task and its items."""
        result = await self.db.execute(
            select(ShotUploadTask).where(ShotUploadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            return False

        if task.status == ShotUploadTaskStatus.RUNNING:
            raise ValueError("Cannot delete a running task")

        await self.db.delete(task)
        await self.db.commit()
        return True

    async def cancel_task(self, task_id: UUID) -> bool:
        """Cancel a running task."""
        result = await self.db.execute(
            select(ShotUploadTask).where(ShotUploadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            return False

        if task.status != ShotUploadTaskStatus.RUNNING:
            raise ValueError("Task is not running")

        task.status = ShotUploadTaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        return True

    async def get_upload_history(
        self,
        episode: Optional[str] = None,
        sequence: Optional[str] = None,
        shot: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, any]:
        """Get upload history with filters."""
        query = select(ShotUploadHistory)

        if episode:
            query = query.where(ShotUploadHistory.episode == episode)
        if sequence:
            query = query.where(ShotUploadHistory.sequence == sequence)
        if shot:
            query = query.where(ShotUploadHistory.shot == shot)
        if status:
            query = query.where(ShotUploadHistory.status == status)
        if start_date:
            query = query.where(ShotUploadHistory.uploaded_at >= start_date)
        if end_date:
            query = query.where(ShotUploadHistory.uploaded_at <= end_date)

        query = query.order_by(ShotUploadHistory.uploaded_at.desc())
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        history_items = result.scalars().all()

        # Get total count
        count_query = select(func.count(ShotUploadHistory.id))
        if episode:
            count_query = count_query.where(ShotUploadHistory.episode == episode)
        if sequence:
            count_query = count_query.where(ShotUploadHistory.sequence == sequence)
        if shot:
            count_query = count_query.where(ShotUploadHistory.shot == shot)
        if status:
            count_query = count_query.where(ShotUploadHistory.status == status)
        if start_date:
            count_query = count_query.where(ShotUploadHistory.uploaded_at >= start_date)
        if end_date:
            count_query = count_query.where(ShotUploadHistory.uploaded_at <= end_date)

        count_result = await self.db.execute(count_query)
        total = count_result.scalar()

        return {
            "history": [
                {
                    "id": str(h.id),
                    "task_id": str(h.task_id) if h.task_id else None,
                    "task_name": h.task_name,
                    "episode": h.episode,
                    "sequence": h.sequence,
                    "shot": h.shot,
                    "department": h.department,
                    "filename": h.filename,
                    "version": h.version,
                    "file_size": h.file_size,
                    "source_path": h.source_path,
                    "target_path": h.target_path,
                    "source_endpoint_name": h.source_endpoint_name,
                    "target_endpoint_name": h.target_endpoint_name,
                    "status": h.status,
                    "error_message": h.error_message,
                    "uploaded_at": h.uploaded_at.isoformat() if h.uploaded_at else None,
                    "uploaded_by": h.uploaded_by
                }
                for h in history_items
            ],
            "total": total,
            "limit": limit,
            "offset": offset
        }

    async def retry_skipped_items(
        self,
        task_id: UUID,
        overwrite: bool = True
    ) -> Dict[str, any]:
        """Retry skipped items with overwrite option."""
        # Get task
        result = await self.db.execute(
            select(ShotUploadTask).where(ShotUploadTask.id == task_id)
        )
        task = result.scalar_one_or_none()

        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status == ShotUploadTaskStatus.RUNNING:
            raise ValueError("Task is already running")

        # Reset skipped items to pending
        items_result = await self.db.execute(
            select(ShotUploadItem)
            .where(ShotUploadItem.task_id == task_id)
            .where(ShotUploadItem.status == ShotUploadItemStatus.SKIPPED)
        )
        skipped_items = items_result.scalars().all()

        if not skipped_items:
            return {"success": True, "message": "No skipped items to retry", "count": 0}

        for item in skipped_items:
            item.status = ShotUploadItemStatus.PENDING
            item.error_message = None
            item.started_at = None
            item.completed_at = None

        # Update task for retry
        task.status = ShotUploadTaskStatus.PENDING
        task.conflict_strategy = 'overwrite' if overwrite else task.conflict_strategy
        task.skipped_items = 0
        await self.db.commit()

        return {
            "success": True,
            "message": f"Reset {len(skipped_items)} skipped items for retry",
            "count": len(skipped_items)
        }
