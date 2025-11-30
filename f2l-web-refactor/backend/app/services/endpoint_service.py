"""
Endpoint Service - Business logic for endpoint management.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from app.repositories.endpoint_repository import EndpointRepository
from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.sftp_manager import SFTPManager, SFTPConfig
from app.core.s3_manager import S3Manager, S3Config
from app.database.models import Endpoint, EndpointType
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class EndpointService:
    """Service for endpoint business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.endpoint_repo = EndpointRepository(db)

    async def get_all_endpoints(
        self,
        endpoint_type: Optional[EndpointType] = None,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[Endpoint]:
        """
        Get all endpoints with optional filtering.
        
        Args:
            endpoint_type: Filter by endpoint type
            active_only: Only return active endpoints
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of Endpoint objects
        """
        try:
            endpoints = await self.endpoint_repo.get_all(
                endpoint_type=endpoint_type,
                active_only=active_only,
                skip=skip,
                limit=limit
            )
            
            logger.info(f"Retrieved {len(endpoints)} endpoints")
            return endpoints
            
        except Exception as e:
            logger.error(f"Failed to get endpoints: {e}")
            raise

    async def get_endpoint_by_id(self, endpoint_id: UUID) -> Optional[Endpoint]:
        """
        Get endpoint by ID.
        
        Args:
            endpoint_id: Endpoint UUID
            
        Returns:
            Endpoint object or None if not found
        """
        try:
            endpoint = await self.endpoint_repo.get_by_id(endpoint_id)
            
            if endpoint:
                logger.info(f"Retrieved endpoint {endpoint_id} ({endpoint.name})")
            else:
                logger.warning(f"Endpoint {endpoint_id} not found")
            
            return endpoint
            
        except Exception as e:
            logger.error(f"Failed to get endpoint {endpoint_id}: {e}")
            raise

    async def create_endpoint(self, endpoint_data: dict) -> Endpoint:
        """
        Create new endpoint.
        
        Args:
            endpoint_data: Dictionary with endpoint data
            
        Returns:
            Created Endpoint object
        """
        try:
            # Validate endpoint data
            self._validate_endpoint_data(endpoint_data)
            
            # Create endpoint
            endpoint = await self.endpoint_repo.create(endpoint_data)
            
            logger.info(f"Created endpoint {endpoint.id} ({endpoint.name})")
            return endpoint
            
        except Exception as e:
            logger.error(f"Failed to create endpoint: {e}")
            raise

    async def update_endpoint(self, endpoint_id: UUID, update_data: dict) -> Optional[Endpoint]:
        """
        Update endpoint.
        
        Args:
            endpoint_id: Endpoint UUID
            update_data: Dictionary with fields to update
            
        Returns:
            Updated Endpoint object or None if not found
        """
        try:
            # Validate update data
            if update_data:
                self._validate_endpoint_data(update_data, is_update=True)
            
            # Update endpoint
            endpoint = await self.endpoint_repo.update(endpoint_id, update_data)
            
            if endpoint:
                logger.info(f"Updated endpoint {endpoint_id} ({endpoint.name})")
            else:
                logger.warning(f"Endpoint {endpoint_id} not found for update")
            
            return endpoint
            
        except Exception as e:
            logger.error(f"Failed to update endpoint {endpoint_id}: {e}")
            raise

    async def delete_endpoint(self, endpoint_id: UUID) -> bool:
        """
        Delete endpoint.
        
        Args:
            endpoint_id: Endpoint UUID
            
        Returns:
            True if deleted, False if not found
        """
        try:
            # Check if endpoint is used in any sessions
            if await self._is_endpoint_in_use(endpoint_id):
                raise ValueError("Cannot delete endpoint that is used in sync sessions")
            
            # Delete endpoint
            deleted = await self.endpoint_repo.delete(endpoint_id)
            
            if deleted:
                logger.info(f"Deleted endpoint {endpoint_id}")
            else:
                logger.warning(f"Endpoint {endpoint_id} not found for deletion")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to delete endpoint {endpoint_id}: {e}")
            raise

    async def test_endpoint_connection(self, endpoint_id: UUID) -> Dict[str, Any]:
        """
        Test endpoint connection.
        
        Args:
            endpoint_id: Endpoint UUID
            
        Returns:
            Dictionary with connection test results
        """
        try:
            # Get endpoint with decrypted credentials
            endpoint_data = await self.endpoint_repo.get_with_decrypted_password(endpoint_id)
            
            if not endpoint_data:
                return {
                    'success': False,
                    'message': 'Endpoint not found',
                    'endpoint_id': str(endpoint_id)
                }
            
            # Test connection based on endpoint type
            test_result = await self._test_connection_by_type(endpoint_data)
            
            # Update connection status in database
            status = "connected" if test_result['success'] else "error"
            await self.endpoint_repo.update_connection_status(
                endpoint_id,
                status,
                test_result['message']
            )
            
            logger.info(f"Connection test for endpoint {endpoint_id}: {test_result['success']}")
            
            return {
                'success': test_result['success'],
                'message': test_result['message'],
                'endpoint_id': str(endpoint_id),
                'endpoint_name': endpoint_data['name'],
                'endpoint_type': endpoint_data['endpoint_type'].value,
                'response_time_ms': test_result.get('response_time_ms', 0),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to test endpoint {endpoint_id} connection: {e}")
            
            # Update status to error
            await self.endpoint_repo.update_connection_status(
                endpoint_id,
                "error",
                f"Connection test failed: {str(e)}"
            )
            
            return {
                'success': False,
                'message': f"Connection test failed: {str(e)}",
                'endpoint_id': str(endpoint_id)
            }

    async def browse_endpoint_directory(
        self,
        endpoint_id: UUID,
        path: str,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        Browse directory on endpoint.
        
        Args:
            endpoint_id: Endpoint UUID
            path: Directory path to browse
            max_depth: Maximum depth for recursive listing
            
        Returns:
            Dictionary with directory listing
        """
        try:
            # Get endpoint with decrypted credentials
            endpoint_data = await self.endpoint_repo.get_with_decrypted_password(endpoint_id)
            
            if not endpoint_data:
                raise ValueError("Endpoint not found")
            
            # Get appropriate manager
            manager = await self._get_endpoint_manager(endpoint_data)
            
            # Connect and browse
            await self._connect_manager(manager)
            
            try:
                # List directory contents
                if hasattr(manager, 'list_directory'):
                    files = await manager.list_directory_async(path, recursive=True, max_depth=max_depth) if hasattr(manager, 'list_directory_async') else manager.list_directory(path, recursive=True, max_depth=max_depth)
                else:
                    files = []
                
                # Organize into directories and files
                directories = [f for f in files if not f.get('is_file', True)]
                files_list = [f for f in files if f.get('is_file', True)]
                
                result = {
                    'success': True,
                    'path': path,
                    'directories': directories,
                    'files': files_list,
                    'total_directories': len(directories),
                    'total_files': len(files_list),
                    'endpoint_id': str(endpoint_id),
                    'endpoint_name': endpoint_data['name']
                }
                
                logger.info(f"Browsed {path} on endpoint {endpoint_id}: {len(files)} items")
                return result
                
            finally:
                await self._disconnect_manager(manager)
            
        except Exception as e:
            logger.error(f"Failed to browse endpoint {endpoint_id} path {path}: {e}")
            return {
                'success': False,
                'message': str(e),
                'path': path,
                'endpoint_id': str(endpoint_id)
            }

    async def get_file_metadata(self, endpoint_id: UUID, file_path: str) -> Dict[str, Any]:
        """
        Get file metadata from endpoint.
        
        Args:
            endpoint_id: Endpoint UUID
            file_path: Path to file
            
        Returns:
            Dictionary with file metadata
        """
        try:
            # Get endpoint with decrypted credentials
            endpoint_data = await self.endpoint_repo.get_with_decrypted_password(endpoint_id)
            
            if not endpoint_data:
                raise ValueError("Endpoint not found")
            
            # Get appropriate manager
            manager = await self._get_endpoint_manager(endpoint_data)
            
            # Connect and get metadata
            await self._connect_manager(manager)
            
            try:
                if hasattr(manager, 'get_file_info'):
                    metadata = manager.get_file_info(file_path)
                else:
                    metadata = None
                
                if metadata:
                    result = {
                        'success': True,
                        'file_path': file_path,
                        'metadata': metadata,
                        'endpoint_id': str(endpoint_id)
                    }
                else:
                    result = {
                        'success': False,
                        'message': 'File not found or metadata unavailable',
                        'file_path': file_path,
                        'endpoint_id': str(endpoint_id)
                    }
                
                logger.info(f"Retrieved metadata for {file_path} on endpoint {endpoint_id}")
                return result
                
            finally:
                await self._disconnect_manager(manager)
            
        except Exception as e:
            logger.error(f"Failed to get metadata for {file_path} on endpoint {endpoint_id}: {e}")
            return {
                'success': False,
                'message': str(e),
                'file_path': file_path,
                'endpoint_id': str(endpoint_id)
            }

    def _validate_endpoint_data(self, data: dict, is_update: bool = False):
        """Validate endpoint data."""
        if not is_update:
            required_fields = ['name', 'endpoint_type']
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
        
        # Validate endpoint type specific fields
        endpoint_type = data.get('endpoint_type')
        if endpoint_type:
            if endpoint_type in [EndpointType.FTP, EndpointType.SFTP]:
                if not is_update:
                    if not data.get('host'):
                        raise ValueError("Host is required for FTP/SFTP endpoints")
                    if not data.get('username'):
                        raise ValueError("Username is required for FTP/SFTP endpoints")
            elif endpoint_type == EndpointType.S3:
                if not is_update:
                    if not data.get('s3_bucket'):
                        raise ValueError("S3 bucket is required for S3 endpoints")
            elif endpoint_type == EndpointType.LOCAL:
                if not is_update:
                    if not data.get('local_path'):
                        raise ValueError("Local path is required for local endpoints")

    async def _is_endpoint_in_use(self, endpoint_id: UUID) -> bool:
        """Check if endpoint is used in any sync sessions."""
        # TODO: Implement check against sync sessions
        return False

    async def _test_connection_by_type(self, endpoint_data: dict) -> Dict[str, Any]:
        """Test connection based on endpoint type."""
        start_time = datetime.now()
        
        try:
            endpoint_type = endpoint_data['endpoint_type']
            
            if endpoint_type == EndpointType.FTP:
                result = await self._test_ftp_connection(endpoint_data)
            elif endpoint_type == EndpointType.SFTP:
                result = await self._test_sftp_connection(endpoint_data)
            elif endpoint_type == EndpointType.S3:
                result = await self._test_s3_connection(endpoint_data)
            elif endpoint_type == EndpointType.LOCAL:
                result = await self._test_local_connection(endpoint_data)
            else:
                result = {
                    'success': False,
                    'message': f"Unsupported endpoint type: {endpoint_type}"
                }
            
            # Calculate response time
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            result['response_time_ms'] = int(response_time)
            
            return result
            
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds() * 1000
            return {
                'success': False,
                'message': f"Connection test error: {str(e)}",
                'response_time_ms': int(response_time)
            }

    async def _test_ftp_connection(self, endpoint_data: dict) -> Dict[str, Any]:
        """Test FTP connection."""
        try:
            config = FTPConfig(
                host=endpoint_data['host'],
                username=endpoint_data['username'],
                password=endpoint_data.get('password', ''),
                port=endpoint_data.get('port', 21)
            )
            
            manager = FTPManager(config)
            
            if manager.connect():
                health_result = manager.health_check()
                manager.close()
                return health_result
            else:
                return {
                    'success': False,
                    'message': 'Failed to establish FTP connection'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'FTP connection test failed: {str(e)}'
            }

    async def _test_sftp_connection(self, endpoint_data: dict) -> Dict[str, Any]:
        """Test SFTP connection."""
        try:
            config = SFTPConfig(
                host=endpoint_data['host'],
                username=endpoint_data['username'],
                password=endpoint_data.get('password', ''),
                port=endpoint_data.get('port', 22)
            )
            
            manager = SFTPManager(config)
            
            if manager.connect():
                health_result = manager.health_check()
                manager.close()
                return health_result
            else:
                return {
                    'success': False,
                    'message': 'Failed to establish SFTP connection'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'SFTP connection test failed: {str(e)}'
            }

    async def _test_s3_connection(self, endpoint_data: dict) -> Dict[str, Any]:
        """Test S3 connection."""
        try:
            config = S3Config(
                bucket=endpoint_data['s3_bucket'],
                region=endpoint_data.get('s3_region', 'us-east-1'),
                access_key=endpoint_data.get('s3_access_key'),
                secret_key=endpoint_data.get('s3_secret_key')
            )
            
            manager = S3Manager(config)
            result = manager.test_connection()
            
            return {
                'success': result['success'],
                'message': result['message']
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'S3 connection test failed: {str(e)}'
            }

    async def _test_local_connection(self, endpoint_data: dict) -> Dict[str, Any]:
        """Test local connection."""
        import os
        
        try:
            local_path = endpoint_data.get('local_path')
            if not local_path:
                return {
                    'success': False,
                    'message': 'Local path not specified'
                }
            
            if os.path.exists(local_path) and os.path.isdir(local_path):
                return {
                    'success': True,
                    'message': 'Local path accessible'
                }
            else:
                return {
                    'success': False,
                    'message': 'Local path does not exist or is not a directory'
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Local connection test failed: {str(e)}'
            }

    async def _get_endpoint_manager(self, endpoint_data: dict):
        """Get appropriate manager for endpoint type."""
        endpoint_type = endpoint_data['endpoint_type']
        
        if endpoint_type == EndpointType.FTP:
            config = FTPConfig(
                host=endpoint_data['host'],
                username=endpoint_data['username'],
                password=endpoint_data.get('password', ''),
                port=endpoint_data.get('port', 21)
            )
            return FTPManager(config)
            
        elif endpoint_type == EndpointType.SFTP:
            config = SFTPConfig(
                host=endpoint_data['host'],
                username=endpoint_data['username'],
                password=endpoint_data.get('password', ''),
                port=endpoint_data.get('port', 22)
            )
            return SFTPManager(config)
            
        elif endpoint_type == EndpointType.S3:
            config = S3Config(
                bucket=endpoint_data['s3_bucket'],
                region=endpoint_data.get('s3_region', 'us-east-1'),
                access_key=endpoint_data.get('s3_access_key'),
                secret_key=endpoint_data.get('s3_secret_key')
            )
            return S3Manager(config)
            
        elif endpoint_type == EndpointType.LOCAL:
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
