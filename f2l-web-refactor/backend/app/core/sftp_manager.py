"""
SFTPManager - Modern SFTP operations manager for F2L Web Refactor.
Built using paramiko with async support and enhanced error handling.
"""
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timezone
import os
import stat
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    import paramiko
except ImportError:
    paramiko = None

logger = logging.getLogger(__name__)


@dataclass
class SFTPConfig:
    """SFTP configuration dataclass."""
    host: str
    username: str
    password: Optional[str] = None
    private_key_path: Optional[str] = None
    private_key_passphrase: Optional[str] = None
    port: int = 22
    timeout: int = 60
    connection_timeout: int = 300  # 5 minutes


@dataclass
class SFTPFileInfo:
    """SFTP file metadata."""
    path: str
    size: int
    modified: Optional[datetime]
    is_file: bool = True
    permissions: Optional[str] = None
    owner: Optional[str] = None
    group: Optional[str] = None


class SFTPManager:
    """
    Production-ready SFTP Manager with async support.
    
    Features:
    - SSH key and password authentication
    - Recursive directory listing with depth control
    - File metadata retrieval and comparison
    - Progress tracking for transfers
    - Async-friendly with ThreadPoolExecutor
    """

    def __init__(self, config: SFTPConfig):
        """
        Initialize SFTPManager with configuration.
        
        Args:
            config: SFTPConfig instance with connection details
        """
        if paramiko is None:
            raise ImportError("paramiko is required for SFTP operations. Install with: pip install paramiko")
        
        self.config = config
        self.ssh_client = None
        self.sftp_client = None
        self.last_activity = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        logger.info(f"SFTPManager initialized for {config.host}:{config.port}")

    def connect(self) -> bool:
        """
        Establish SFTP connection with comprehensive error handling.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Clean up existing connections
            if self.sftp_client:
                try:
                    self.sftp_client.close()
                except:
                    pass
            
            if self.ssh_client:
                try:
                    self.ssh_client.close()
                except:
                    pass

            # Create new SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            logger.info(f"Connecting to {self.config.host}:{self.config.port}...")

            # Prepare authentication
            connect_kwargs = {
                'hostname': self.config.host,
                'port': self.config.port,
                'username': self.config.username,
                'timeout': self.config.timeout
            }

            # Add authentication method
            if self.config.private_key_path:
                # SSH key authentication
                try:
                    private_key = paramiko.RSAKey.from_private_key_file(
                        self.config.private_key_path,
                        password=self.config.private_key_passphrase
                    )
                    connect_kwargs['pkey'] = private_key
                    logger.info("Using SSH key authentication")
                except Exception as e:
                    logger.warning(f"Failed to load SSH key, falling back to password: {e}")
                    if self.config.password:
                        connect_kwargs['password'] = self.config.password
            elif self.config.password:
                # Password authentication
                connect_kwargs['password'] = self.config.password
                logger.info("Using password authentication")
            else:
                raise ValueError("Either password or private_key_path must be provided")

            # Connect SSH
            self.ssh_client.connect(**connect_kwargs)

            # Create SFTP client
            self.sftp_client = self.ssh_client.open_sftp()

            logger.info("SFTP connection established successfully")
            self.last_activity = datetime.now()
            return True

        except Exception as e:
            logger.error(f"SFTP connection failed to {self.config.host}:{self.config.port} - {e}")
            self.ssh_client = None
            self.sftp_client = None
            return False

    def is_connected(self) -> bool:
        """
        Check if SFTP connection is active and healthy.
        
        Returns:
            bool: True if connected and healthy, False otherwise
        """
        if not self.ssh_client or not self.sftp_client:
            return False

        # Check connection timeout
        if self.last_activity and (datetime.now() - self.last_activity).seconds > self.config.connection_timeout:
            logger.warning(f"Connection timeout exceeded ({self.config.connection_timeout}s)")
            return False

        try:
            # Test connection by getting current directory
            self.sftp_client.getcwd()
            self.last_activity = datetime.now()
            return True
        except Exception as e:
            logger.warning(f"Connection test failed: {e}")
            return False

    def ensure_connected(self) -> bool:
        """
        Ensure SFTP connection is active, reconnect if necessary.
        
        Returns:
            bool: True if connected, False if connection failed
        """
        if not self.is_connected():
            return self.connect()
        return True

    def disconnect(self):
        """Properly disconnect from SFTP server with comprehensive cleanup."""
        if self.sftp_client:
            try:
                logger.info(f"Disconnecting SFTP from {self.config.host}...")
                self.sftp_client.close()
                logger.info("SFTP connection closed")
            except Exception as e:
                logger.warning(f"Error closing SFTP connection: {e}")
            finally:
                self.sftp_client = None

        if self.ssh_client:
            try:
                self.ssh_client.close()
                logger.info("SSH connection closed")
            except Exception as e:
                logger.warning(f"Error closing SSH connection: {e}")
            finally:
                self.ssh_client = None
                self.last_activity = None

    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check.
        
        Returns:
            Dict with health check results
        """
        try:
            if not self.ensure_connected():
                return {"success": False, "message": "Connection failed"}
            
            # Test basic operations
            try:
                current_dir = self.sftp_client.getcwd() or "/"
                # Test listing current directory
                self.sftp_client.listdir(current_dir)
                return {
                    "success": True, 
                    "message": "Connection healthy",
                    "current_directory": current_dir
                }
            except Exception as e:
                return {"success": False, "message": f"Health check failed: {str(e)}"}
                
        except Exception as e:
            return {"success": False, "message": f"Health check error: {str(e)}"}

    def list_directory(
        self, 
        remote_path: str = "/", 
        recursive: bool = False,
        max_depth: int = 5,
        current_depth: int = 0
    ) -> List[SFTPFileInfo]:
        """
        List directory contents with optional recursion.
        
        Args:
            remote_path: Remote directory path to list
            recursive: If True, list recursively
            max_depth: Maximum recursion depth
            current_depth: Current recursion depth (internal)
            
        Returns:
            List of SFTPFileInfo objects
        """
        if not self.ensure_connected():
            return []

        if recursive and current_depth >= max_depth:
            logger.warning(f"Maximum recursion depth ({max_depth}) reached for {remote_path}")
            return []

        files = []
        directories = []

        try:
            # Get directory listing with attributes
            items = self.sftp_client.listdir_attr(remote_path)
            
            for item in items:
                if item.filename in ['.', '..']:
                    continue
                
                full_path = f"{remote_path.rstrip('/')}/{item.filename}"
                
                # Convert modification time
                modified = None
                if item.st_mtime:
                    modified = datetime.fromtimestamp(item.st_mtime, tz=timezone.utc)
                
                # Convert permissions
                permissions = None
                if item.st_mode:
                    permissions = stat.filemode(item.st_mode)
                
                if stat.S_ISDIR(item.st_mode):
                    # Directory
                    directories.append(item.filename)
                    if not recursive:
                        # Add directory entry if not recursive
                        files.append(SFTPFileInfo(
                            path=full_path,
                            size=0,
                            modified=modified,
                            is_file=False,
                            permissions=permissions
                        ))
                else:
                    # File
                    files.append(SFTPFileInfo(
                        path=full_path,
                        size=item.st_size or 0,
                        modified=modified,
                        is_file=True,
                        permissions=permissions
                    ))

            # Handle recursive listing
            if recursive:
                for dirname in directories:
                    subdir_path = f"{remote_path.rstrip('/')}/{dirname}"
                    try:
                        logger.debug(f"Recursing into: {subdir_path} (depth: {current_depth + 1})")
                        subdir_files = self.list_directory(
                            subdir_path, recursive=True, max_depth=max_depth, current_depth=current_depth + 1
                        )
                        files.extend(subdir_files)
                    except Exception as e:
                        logger.error(f"Error recursing into {subdir_path}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error listing {remote_path}: {e}")

        self.last_activity = datetime.now()
        return files

    def get_file_info(self, remote_path: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata from SFTP server.

        Args:
            remote_path: Remote file path

        Returns:
            Dict with file metadata or None if not found
        """
        try:
            if not self.ensure_connected():
                return None

            # Get file attributes
            attrs = self.sftp_client.stat(remote_path)

            # Convert modification time
            modified = None
            if attrs.st_mtime:
                modified = datetime.fromtimestamp(attrs.st_mtime, tz=timezone.utc)

            # Convert permissions
            permissions = None
            if attrs.st_mode:
                permissions = stat.filemode(attrs.st_mode)

            return {
                'path': remote_path,
                'size': attrs.st_size or 0,
                'modified': modified,
                'permissions': permissions,
                'exists': True
            }

        except Exception as e:
            logger.warning(f"Cannot get file info for {remote_path}: {e}")
            return None

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Download file from SFTP to local path with progress tracking.

        Args:
            remote_path: Remote file path
            local_path: Local file path to save to
            progress_callback: Optional callback function(bytes_transferred, total_bytes)

        Returns:
            Dict with download results
        """
        try:
            if not self.ensure_connected():
                return {"success": False, "error": "Not connected to SFTP server"}

            # Ensure local directory exists
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Get file size for progress tracking
            file_size = 0
            try:
                attrs = self.sftp_client.stat(remote_path)
                file_size = attrs.st_size or 0
            except:
                pass

            # Progress tracking wrapper
            def progress_wrapper(transferred, total):
                if progress_callback:
                    progress_callback(transferred, total)

            # Download file
            if progress_callback and file_size > 0:
                self.sftp_client.get(remote_path, local_path, callback=progress_wrapper)
            else:
                self.sftp_client.get(remote_path, local_path)

            self.last_activity = datetime.now()

            logger.info(f"Downloaded {remote_path} to {local_path} ({file_size} bytes)")

            return {
                "success": True,
                "remote_path": remote_path,
                "local_path": local_path,
                "size": file_size
            }

        except Exception as e:
            logger.error(f"SFTP download failed for {remote_path}: {e}")
            return {
                "success": False,
                "remote_path": remote_path,
                "local_path": local_path,
                "error": str(e)
            }

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Upload file from local to SFTP with progress tracking.

        Args:
            local_path: Local file path
            remote_path: Remote file path
            progress_callback: Optional callback function(bytes_transferred, total_bytes)

        Returns:
            Dict with upload results
        """
        try:
            if not self.ensure_connected():
                return {"success": False, "error": "Not connected to SFTP server"}

            if not os.path.exists(local_path):
                return {"success": False, "error": f"Local file not found: {local_path}"}

            # Get file size
            file_size = os.path.getsize(local_path)

            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            self.ensure_remote_directory(remote_dir)

            # Progress tracking wrapper
            def progress_wrapper(transferred, total):
                if progress_callback:
                    progress_callback(transferred, total)

            # Upload file
            if progress_callback:
                self.sftp_client.put(local_path, remote_path, callback=progress_wrapper)
            else:
                self.sftp_client.put(local_path, remote_path)

            self.last_activity = datetime.now()

            logger.info(f"Uploaded {local_path} to {remote_path} ({file_size} bytes)")

            return {
                "success": True,
                "local_path": local_path,
                "remote_path": remote_path,
                "size": file_size
            }

        except Exception as e:
            logger.error(f"SFTP upload failed for {local_path}: {e}")
            return {
                "success": False,
                "local_path": local_path,
                "remote_path": remote_path,
                "error": str(e)
            }

    def ensure_remote_directory(self, remote_dir: str):
        """
        Create remote directory structure if it doesn't exist.

        Args:
            remote_dir: Remote directory path to create
        """
        if not remote_dir or remote_dir == '/':
            return

        try:
            # Check if directory exists
            try:
                self.sftp_client.stat(remote_dir)
                return  # Directory exists
            except:
                pass  # Directory doesn't exist, create it

            # Create parent directories first
            parent_dir = os.path.dirname(remote_dir)
            if parent_dir and parent_dir != remote_dir:
                self.ensure_remote_directory(parent_dir)

            # Create the directory
            self.sftp_client.mkdir(remote_dir)
            logger.debug(f"Created remote directory: {remote_dir}")

        except Exception as e:
            logger.error(f"Failed to create remote directory {remote_dir}: {e}")

    def delete_file(self, remote_path: str) -> Dict[str, Any]:
        """
        Delete file from SFTP server.

        Args:
            remote_path: Remote file path to delete

        Returns:
            Dict with deletion results
        """
        try:
            if not self.ensure_connected():
                return {"success": False, "error": "Not connected to SFTP server"}

            self.sftp_client.remove(remote_path)
            self.last_activity = datetime.now()

            logger.info(f"Deleted file: {remote_path}")

            return {
                "success": True,
                "remote_path": remote_path
            }

        except Exception as e:
            logger.error(f"Error deleting {remote_path}: {e}")
            return {
                "success": False,
                "remote_path": remote_path,
                "error": str(e)
            }

    async def async_list_directory(self, *args, **kwargs) -> List[SFTPFileInfo]:
        """Async wrapper for list_directory."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.list_directory, *args, **kwargs)

    async def async_download_file(self, *args, **kwargs) -> Dict[str, Any]:
        """Async wrapper for download_file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.download_file, *args, **kwargs)

    async def async_upload_file(self, *args, **kwargs) -> Dict[str, Any]:
        """Async wrapper for upload_file."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self.upload_file, *args, **kwargs)

    def close(self):
        """Close SFTP connection and thread pool."""
        self.disconnect()
        self.executor.shutdown(wait=True)
        logger.info("SFTPManager closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
