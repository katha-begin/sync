"""
Local File System Manager - Handles local file operations for F2L Web Refactor.
"""
import os
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LocalConfig:
    """Configuration for local file system operations."""
    base_path: str


class LocalManager:
    """
    Local file system manager.
    
    Provides consistent interface for local file operations
    to match FTP/SFTP/S3 managers.
    """

    def __init__(self, config: LocalConfig):
        """Initialize local manager with configuration."""
        self.config = config
        self.base_path = Path(config.base_path)
        self.connected = False
        logger.info(f"LocalManager initialized with base path: {self.base_path}")

    def connect(self) -> bool:
        """
        Connect to local file system (validate base path).

        Returns:
            True if base path is accessible, False otherwise
        """
        try:
            if not self.base_path.exists():
                logger.error(f"Base path does not exist: {self.base_path}")
                return False

            if not self.base_path.is_dir():
                logger.error(f"Base path is not a directory: {self.base_path}")
                return False

            # Test read permissions (write permissions not required for browsing)
            try:
                # Try to list the directory to verify read access
                list(self.base_path.iterdir())
            except PermissionError as e:
                logger.error(f"No read permissions for base path: {e}")
                return False
            except Exception as e:
                logger.warning(f"Could not list base path (may be empty): {e}")
                # Continue anyway - empty directories are valid

            self.connected = True
            logger.info(f"Connected to local file system: {self.base_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to local file system: {e}")
            return False

    async def connect_async(self) -> bool:
        """Async version of connect."""
        return self.connect()

    def close(self):
        """Close connection (no-op for local file system)."""
        self.connected = False
        logger.info("Disconnected from local file system")

    async def close_async(self):
        """Async version of close."""
        self.close()

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on local file system.
        
        Returns:
            Dictionary with health check results
        """
        try:
            if not self.connected:
                return {
                    'success': False,
                    'message': 'Not connected to local file system'
                }
            
            # Check if base path still exists and is accessible
            if not self.base_path.exists():
                return {
                    'success': False,
                    'message': 'Base path no longer exists'
                }
            
            # Test read/write permissions
            test_file = self.base_path / '.f2l_health_check'
            try:
                test_file.write_text('health_check')
                test_file.unlink()
            except Exception as e:
                return {
                    'success': False,
                    'message': f'No write permissions: {e}'
                }
            
            # Get disk space information
            stat = shutil.disk_usage(self.base_path)
            free_gb = stat.free / (1024**3)
            
            return {
                'success': True,
                'message': f'Local file system healthy, {free_gb:.2f} GB free',
                'free_space_gb': free_gb,
                'total_space_gb': stat.total / (1024**3),
                'used_space_gb': stat.used / (1024**3)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Health check failed: {e}'
            }

    def list_directory(
        self,
        path: str,
        recursive: bool = False,
        max_depth: int = 5
    ) -> List[Dict[str, Any]]:
        """
        List directory contents.
        
        Args:
            path: Directory path relative to base path
            recursive: Whether to list recursively
            max_depth: Maximum recursion depth
            
        Returns:
            List of file/directory information dictionaries
        """
        try:
            if not self.connected:
                raise ConnectionError("Not connected to local file system")
            
            # Resolve path relative to base path
            full_path = self._resolve_path(path)
            
            if not full_path.exists():
                logger.warning(f"Path does not exist: {full_path}")
                return []
            
            if not full_path.is_dir():
                logger.warning(f"Path is not a directory: {full_path}")
                return []
            
            files = []
            
            if recursive:
                files = self._list_recursive(full_path, max_depth, 0)
            else:
                files = self._list_single_level(full_path)
            
            logger.info(f"Listed {len(files)} items from {full_path}")
            return files
            
        except Exception as e:
            logger.error(f"Failed to list directory {path}: {e}")
            return []

    async def list_directory_async(
        self,
        path: str,
        recursive: bool = False,
        max_depth: int = 5
    ) -> List[Dict[str, Any]]:
        """Async version of list_directory."""
        return self.list_directory(path, recursive, max_depth)

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata.
        
        Args:
            file_path: File path relative to base path
            
        Returns:
            Dictionary with file metadata or None if not found
        """
        try:
            if not self.connected:
                raise ConnectionError("Not connected to local file system")
            
            full_path = self._resolve_path(file_path)
            
            if not full_path.exists():
                return None
            
            if not full_path.is_file():
                return None
            
            stat = full_path.stat()
            
            return {
                'path': file_path,
                'size': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                'exists': True,
                'is_file': True,
                'permissions': oct(stat.st_mode)[-3:]
            }
            
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return None

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Copy file from one local location to another.
        
        Args:
            remote_path: Source file path relative to base path
            local_path: Destination file path (absolute)
            progress_callback: Optional progress callback
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.connected:
                raise ConnectionError("Not connected to local file system")
            
            source_path = self._resolve_path(remote_path)
            dest_path = Path(local_path)
            
            if not source_path.exists():
                logger.error(f"Source file does not exist: {source_path}")
                return False
            
            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            if progress_callback:
                file_size = source_path.stat().st_size
                progress_callback(file_size, file_size)
            
            logger.info(f"Downloaded file: {source_path} -> {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download file {remote_path}: {e}")
            return False

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Optional[callable] = None
    ) -> bool:
        """
        Copy file from local location to base path location.
        
        Args:
            local_path: Source file path (absolute)
            remote_path: Destination file path relative to base path
            progress_callback: Optional progress callback
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.connected:
                raise ConnectionError("Not connected to local file system")
            
            source_path = Path(local_path)
            dest_path = self._resolve_path(remote_path)
            
            if not source_path.exists():
                logger.error(f"Source file does not exist: {source_path}")
                return False
            
            # Create destination directory if needed
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            if progress_callback:
                file_size = source_path.stat().st_size
                progress_callback(file_size, file_size)
            
            logger.info(f"Uploaded file: {source_path} -> {dest_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to upload file {local_path}: {e}")
            return False

    def delete_file(self, file_path: str) -> bool:
        """
        Delete file.
        
        Args:
            file_path: File path relative to base path
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.connected:
                raise ConnectionError("Not connected to local file system")
            
            full_path = self._resolve_path(file_path)
            
            if not full_path.exists():
                logger.warning(f"File does not exist: {full_path}")
                return True  # Already deleted
            
            if full_path.is_file():
                full_path.unlink()
            elif full_path.is_dir():
                shutil.rmtree(full_path)
            
            logger.info(f"Deleted: {full_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete {file_path}: {e}")
            return False

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base path."""
        if path.startswith('/'):
            path = path[1:]  # Remove leading slash
        
        resolved = self.base_path / path
        
        # Ensure path is within base path (security check)
        try:
            resolved.resolve().relative_to(self.base_path.resolve())
        except ValueError:
            raise ValueError(f"Path {path} is outside base path")
        
        return resolved

    def _list_single_level(self, directory: Path) -> List[Dict[str, Any]]:
        """List single directory level."""
        files = []
        
        try:
            for item in directory.iterdir():
                try:
                    stat = item.stat()
                    
                    # Get relative path from base path
                    rel_path = item.relative_to(self.base_path)
                    
                    file_info = {
                        'path': str(rel_path).replace('\\', '/'),
                        'name': item.name,
                        'size': stat.st_size if item.is_file() else 0,
                        'modified': datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                        'is_file': item.is_file(),
                        'is_directory': item.is_dir(),
                        'permissions': oct(stat.st_mode)[-3:]
                    }
                    
                    files.append(file_info)
                    
                except Exception as e:
                    logger.warning(f"Failed to get info for {item}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Failed to list directory {directory}: {e}")
        
        return files

    def _list_recursive(self, directory: Path, max_depth: int, current_depth: int) -> List[Dict[str, Any]]:
        """List directory recursively."""
        files = []
        
        if current_depth >= max_depth:
            return files
        
        # Add current level
        files.extend(self._list_single_level(directory))
        
        # Recurse into subdirectories
        try:
            for item in directory.iterdir():
                if item.is_dir():
                    try:
                        sub_files = self._list_recursive(item, max_depth, current_depth + 1)
                        files.extend(sub_files)
                    except Exception as e:
                        logger.warning(f"Failed to recurse into {item}: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Failed to recurse directory {directory}: {e}")
        
        return files
