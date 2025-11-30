"""
Sync Engine - Core synchronization logic for F2L Web Refactor.
Orchestrates file synchronization between different endpoint types.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable
from uuid import UUID
import os
import time

from app.database.models import SyncSession, SyncExecution, SyncOperation, OperationType, ExecutionStatus
from app.repositories.endpoint_repository import EndpointRepository
from app.repositories.execution_repository import ExecutionRepository
from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.sftp_manager import SFTPManager, SFTPConfig
from app.core.s3_manager import S3Manager, S3Config
from app.core.metadata_engine import MetadataEngine, SyncDirection, FileMetadata
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    Core synchronization engine.
    
    Handles file synchronization between different endpoint types:
    - FTP ↔ Local
    - SFTP ↔ Local  
    - S3 ↔ Local
    - FTP ↔ S3
    - SFTP ↔ S3
    """

    def __init__(self):
        """Initialize sync engine."""
        self.metadata_engine = MetadataEngine()
        logger.info("SyncEngine initialized")

    async def execute_session_sync(
        self,
        session: SyncSession,
        execution: SyncExecution,
        dry_run: bool = False,
        force_overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        db: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Execute synchronization for a session.
        
        Args:
            session: SyncSession to execute
            execution: SyncExecution record for tracking
            dry_run: If True, don't perform actual file operations
            force_overwrite: If True, overwrite files regardless of metadata
            progress_callback: Optional callback for progress updates
            db: Database session
            
        Returns:
            Dictionary with sync results
        """
        start_time = time.time()
        
        try:
            logger.info(f"Starting sync for session {session.id} ({session.name})")
            
            if progress_callback:
                progress_callback(0, 100, "Initializing sync...")
            
            # Get endpoint configurations
            endpoint_repo = EndpointRepository(db)
            
            source_endpoint_data = await endpoint_repo.get_with_decrypted_password(session.source_endpoint_id)
            dest_endpoint_data = await endpoint_repo.get_with_decrypted_password(session.destination_endpoint_id)
            
            if not source_endpoint_data or not dest_endpoint_data:
                raise ValueError("Source or destination endpoint not found")
            
            # Initialize endpoint managers
            source_manager = await self._get_endpoint_manager(source_endpoint_data)
            dest_manager = await self._get_endpoint_manager(dest_endpoint_data)
            
            if progress_callback:
                progress_callback(10, 100, "Connecting to endpoints...")
            
            # Connect to endpoints
            await self._connect_manager(source_manager)
            await self._connect_manager(dest_manager)
            
            if progress_callback:
                progress_callback(20, 100, "Scanning source directory...")
            
            # Get file lists from both endpoints
            # Note: Filtering parameters (folder_filter, file_filter, exclude_patterns)
            # will be implemented in Phase 5. For now, pass None.
            source_files = await self._get_file_list(
                source_manager,
                session.source_path,
                None,  # folder_filter - Phase 5
                None,  # file_filter - Phase 5
                None   # exclude_patterns - Phase 5
            )

            if progress_callback:
                progress_callback(40, 100, "Scanning destination directory...")

            dest_files = await self._get_file_list(
                dest_manager,
                session.destination_path,
                None,  # folder_filter - Phase 5
                None,  # file_filter - Phase 5
                None   # exclude_patterns - Phase 5
            )
            
            if progress_callback:
                progress_callback(60, 100, "Analyzing file differences...")
            
            # Analyze sync operations needed
            sync_operations = await self._analyze_sync_operations(
                source_files=source_files,
                dest_files=dest_files,
                sync_direction=session.sync_direction,
                force_overwrite=force_overwrite,
                delete_extra_files=session.delete_missing  # Use delete_missing from model
            )
            
            if progress_callback:
                progress_callback(70, 100, f"Executing {len(sync_operations)} operations...")
            
            # Execute sync operations
            results = await self._execute_sync_operations(
                sync_operations=sync_operations,
                source_manager=source_manager,
                dest_manager=dest_manager,
                session=session,
                execution=execution,
                dry_run=dry_run,
                progress_callback=progress_callback,
                db=db
            )
            
            # Cleanup connections
            await self._disconnect_manager(source_manager)
            await self._disconnect_manager(dest_manager)
            
            duration = time.time() - start_time
            
            if progress_callback:
                progress_callback(100, 100, "Sync completed successfully")
            
            logger.info(f"Sync completed for session {session.id} in {duration:.2f}s")
            
            return {
                'success': True,
                'files_processed': results['files_processed'],
                'files_transferred': results['files_transferred'],
                'bytes_transferred': results['bytes_transferred'],
                'errors_count': results['errors_count'],
                'duration_seconds': duration,
                'summary': {
                    'operations_planned': len(sync_operations),
                    'operations_executed': results['operations_executed'],
                    'downloads': results.get('downloads', 0),
                    'uploads': results.get('uploads', 0),
                    'skipped': results.get('skipped', 0),
                    'errors': results.get('errors', [])
                }
            }
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Sync failed for session {session.id}: {e}")
            
            # Cleanup connections on error
            try:
                if 'source_manager' in locals():
                    await self._disconnect_manager(source_manager)
                if 'dest_manager' in locals():
                    await self._disconnect_manager(dest_manager)
            except:
                pass
            
            return {
                'success': False,
                'error_message': str(e),
                'duration_seconds': duration,
                'files_processed': 0,
                'files_transferred': 0,
                'bytes_transferred': 0,
                'errors_count': 1
            }

    async def _get_endpoint_manager(self, endpoint_data: dict):
        """Get appropriate manager for endpoint type."""
        endpoint_type = endpoint_data['endpoint_type']
        
        if endpoint_type.value == 'ftp':
            config = FTPConfig(
                host=endpoint_data['host'],
                username=endpoint_data['username'],
                password=endpoint_data.get('password', ''),
                port=endpoint_data.get('port', 21)
            )
            return FTPManager(config)
            
        elif endpoint_type.value == 'sftp':
            config = SFTPConfig(
                host=endpoint_data['host'],
                username=endpoint_data['username'],
                password=endpoint_data.get('password', ''),
                port=endpoint_data.get('port', 22)
            )
            return SFTPManager(config)
            
        elif endpoint_type.value == 's3':
            config = S3Config(
                bucket=endpoint_data['s3_bucket'],
                region=endpoint_data.get('s3_region', 'us-east-1'),
                access_key=endpoint_data.get('s3_access_key'),
                secret_key=endpoint_data.get('s3_secret_key')
            )
            return S3Manager(config)
            
        elif endpoint_type.value == 'local':
            from app.core.local_manager import LocalManager, LocalConfig
            import os

            # If path is relative, join with /mnt (the base mount point)
            local_path = endpoint_data['local_path']
            if not local_path.startswith('/'):
                full_path = os.path.join('/mnt', local_path)
            else:
                full_path = local_path

            config = LocalConfig(
                base_path=full_path
            )
            return LocalManager(config)
            
        else:
            raise ValueError(f"Unsupported endpoint type: {endpoint_type}")

    async def _connect_manager(self, manager):
        """Connect to endpoint manager."""
        if hasattr(manager, 'connect'):
            success = await manager.connect_async() if hasattr(manager, 'connect_async') else manager.connect()
            if not success:
                raise ConnectionError(f"Failed to connect to {type(manager).__name__}")

    async def _disconnect_manager(self, manager):
        """Disconnect from endpoint manager."""
        if hasattr(manager, 'close'):
            if hasattr(manager, 'close_async'):
                await manager.close_async()
            else:
                manager.close()

    async def _get_file_list(
        self,
        manager,
        path: str,
        folder_filter: Optional[str] = None,
        file_filter: Optional[str] = None,
        exclude_patterns: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get file list from endpoint with filtering."""
        try:
            if hasattr(manager, 'list_directory'):
                files = await manager.list_directory_async(path, recursive=True) if hasattr(manager, 'list_directory_async') else manager.list_directory(path, recursive=True)
            else:
                # Fallback for managers without list_directory
                files = []
            
            # Apply filters
            filtered_files = []
            for file_info in files:
                if self._should_include_file(file_info, folder_filter, file_filter, exclude_patterns):
                    filtered_files.append(file_info)
            
            return filtered_files
            
        except Exception as e:
            logger.error(f"Failed to get file list from {type(manager).__name__}: {e}")
            return []

    def _should_include_file(
        self,
        file_info: Dict[str, Any],
        folder_filter: Optional[str],
        file_filter: Optional[str],
        exclude_patterns: Optional[str]
    ) -> bool:
        """Check if file should be included based on filters."""
        # TODO: Implement pattern matching logic
        # For now, include all files
        return True

    async def _analyze_sync_operations(
        self,
        source_files: List[Dict[str, Any]],
        dest_files: List[Dict[str, Any]],
        sync_direction: SyncDirection,
        force_overwrite: bool,
        delete_extra_files: bool
    ) -> List[Dict[str, Any]]:
        """Analyze what sync operations are needed."""
        operations = []
        
        # Create lookup for destination files
        dest_file_map = {f['path']: f for f in dest_files}
        
        # Analyze source files
        for source_file in source_files:
            if not source_file.get('is_file', True):
                continue  # Skip directories
            
            source_path = source_file['path']
            dest_file = dest_file_map.get(source_path)
            
            # Convert to FileMetadata objects
            source_metadata = FileMetadata(
                path=source_path,
                size=source_file.get('size', 0),
                modified=source_file.get('modified'),
                exists=True
            )
            
            dest_metadata = None
            if dest_file:
                dest_metadata = FileMetadata(
                    path=source_path,
                    size=dest_file.get('size', 0),
                    modified=dest_file.get('modified'),
                    exists=True
                )
            
            # Use metadata engine to determine operation
            comparison = self.metadata_engine.compare_files(
                source_metadata=source_metadata,
                destination_metadata=dest_metadata,
                sync_direction=sync_direction,
                source_is_main=True,
                force_overwrite=force_overwrite
            )
            
            if comparison.operation.value != 'skip':
                operations.append({
                    'operation': comparison.operation.value,
                    'source_path': source_path,
                    'dest_path': source_path,
                    'source_metadata': source_metadata,
                    'dest_metadata': dest_metadata,
                    'reason': comparison.reason
                })
        
        return operations

    async def _execute_sync_operations(
        self,
        sync_operations: List[Dict[str, Any]],
        source_manager,
        dest_manager,
        session: SyncSession,
        execution: SyncExecution,
        dry_run: bool,
        progress_callback: Optional[Callable[[int, int, str], None]],
        db: Optional[AsyncSession]
    ) -> Dict[str, Any]:
        """Execute the planned sync operations."""
        results = {
            'files_processed': 0,
            'files_transferred': 0,
            'bytes_transferred': 0,
            'errors_count': 0,
            'operations_executed': 0,
            'downloads': 0,
            'uploads': 0,
            'skipped': 0,
            'errors': []
        }
        
        total_operations = len(sync_operations)
        
        for i, operation in enumerate(sync_operations):
            try:
                if progress_callback:
                    progress = 70 + int((i / total_operations) * 25)  # 70-95% range
                    progress_callback(progress, 100, f"Processing {operation['source_path']}")
                
                # Execute operation based on type
                if operation['operation'] == 'download':
                    if not dry_run:
                        success = await self._execute_download(
                            source_manager=source_manager,
                            dest_manager=dest_manager,
                            source_path=operation['source_path'],
                            dest_path=operation['dest_path']
                        )
                        if success:
                            results['bytes_transferred'] += operation.get('source_metadata', {}).get('size', 0) if operation.get('source_metadata') else 0
                    results['downloads'] += 1
                    results['files_transferred'] += 1

                elif operation['operation'] == 'upload':
                    if not dry_run:
                        success = await self._execute_upload(
                            source_manager=source_manager,
                            dest_manager=dest_manager,
                            source_path=operation['source_path'],
                            dest_path=operation['dest_path']
                        )
                        if success:
                            results['bytes_transferred'] += operation.get('source_metadata', {}).get('size', 0) if operation.get('source_metadata') else 0
                    results['uploads'] += 1
                    results['files_transferred'] += 1

                elif operation['operation'] == 'delete':
                    if not dry_run:
                        success = await self._execute_delete(
                            dest_manager=dest_manager,
                            file_path=operation['dest_path']
                        )
                    results['deletes'] = results.get('deletes', 0) + 1

                else:
                    results['skipped'] += 1
                
                results['files_processed'] += 1
                results['operations_executed'] += 1
                
                # Record operation in database
                if db:
                    await self._record_sync_operation(
                        execution_id=execution.id,
                        operation=operation,
                        success=True,
                        db=db
                    )
                
            except Exception as e:
                logger.error(f"Failed to execute operation {operation}: {e}")
                results['errors_count'] += 1
                results['errors'].append({
                    'operation': operation,
                    'error': str(e)
                })
                
                # Record failed operation
                if db:
                    await self._record_sync_operation(
                        execution_id=execution.id,
                        operation=operation,
                        success=False,
                        error_message=str(e),
                        db=db
                    )
        
        return results

    async def _record_sync_operation(
        self,
        execution_id: UUID,
        operation: Dict[str, Any],
        success: bool,
        error_message: Optional[str] = None,
        db: Optional[AsyncSession] = None
    ):
        """Record sync operation in database."""
        if not db:
            return
        
        try:
            operation_data = {
                'execution_id': execution_id,
                'operation_type': OperationType(operation['operation'].upper()),
                'source_path': operation['source_path'],
                'destination_path': operation['dest_path'],
                'file_size': operation.get('source_metadata', {}).get('size', 0) if operation.get('source_metadata') else 0,
                'success': success,
                'error_message': error_message,
                'completed_at': datetime.now(timezone.utc)
            }
            
            sync_operation = SyncOperation(**operation_data)
            db.add(sync_operation)
            await db.commit()
            
        except Exception as e:
            logger.error(f"Failed to record sync operation: {e}")
            await db.rollback()

    async def _execute_download(
        self,
        source_manager,
        dest_manager,
        source_path: str,
        dest_path: str
    ) -> bool:
        """Execute download operation from source to destination."""
        try:
            # Create temporary file for transfer
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            try:
                # Download from source to temp file
                if hasattr(source_manager, 'download_file'):
                    success = source_manager.download_file(source_path, temp_path)
                    if not success:
                        return False
                else:
                    logger.error(f"Source manager {type(source_manager).__name__} does not support download")
                    return False

                # Upload from temp file to destination
                if hasattr(dest_manager, 'upload_file'):
                    success = dest_manager.upload_file(temp_path, dest_path)
                    return success
                else:
                    logger.error(f"Destination manager {type(dest_manager).__name__} does not support upload")
                    return False

            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Failed to execute download {source_path} -> {dest_path}: {e}")
            return False

    async def _execute_upload(
        self,
        source_manager,
        dest_manager,
        source_path: str,
        dest_path: str
    ) -> bool:
        """Execute upload operation from source to destination."""
        try:
            # Create temporary file for transfer
            import tempfile
            import os

            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name

            try:
                # Download from source to temp file
                if hasattr(source_manager, 'download_file'):
                    success = source_manager.download_file(source_path, temp_path)
                    if not success:
                        return False
                else:
                    logger.error(f"Source manager {type(source_manager).__name__} does not support download")
                    return False

                # Upload from temp file to destination
                if hasattr(dest_manager, 'upload_file'):
                    success = dest_manager.upload_file(temp_path, dest_path)
                    return success
                else:
                    logger.error(f"Destination manager {type(dest_manager).__name__} does not support upload")
                    return False

            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

        except Exception as e:
            logger.error(f"Failed to execute upload {source_path} -> {dest_path}: {e}")
            return False

    async def _execute_delete(
        self,
        dest_manager,
        file_path: str
    ) -> bool:
        """Execute delete operation on destination."""
        try:
            if hasattr(dest_manager, 'delete_file'):
                success = dest_manager.delete_file(file_path)
                return success
            else:
                logger.error(f"Destination manager {type(dest_manager).__name__} does not support delete")
                return False

        except Exception as e:
            logger.error(f"Failed to execute delete {file_path}: {e}")
            return False
