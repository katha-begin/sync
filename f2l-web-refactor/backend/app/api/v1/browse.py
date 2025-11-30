"""
Browse API - Interactive directory browsing with metadata comparison.
Provides endpoints for FTP/SFTP/Local directory navigation and file metadata operations.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.sftp_manager import SFTPManager, SFTPConfig
from app.core.metadata_engine import MetadataEngine, SyncDirection, FileMetadata, ComparisonResult
from app.database.models import Endpoint, EndpointType
from app.database.session import get_db

router = APIRouter()


class DirectoryItem(BaseModel):
    """Directory item response schema."""
    name: str
    path: str
    size: int
    modified: Optional[datetime] = None
    is_file: bool
    permissions: Optional[str] = None


class DirectoryListing(BaseModel):
    """Directory listing response schema."""
    path: str
    items: List[DirectoryItem]
    total_items: int
    total_files: int
    total_directories: int


class FileMetadataResponse(BaseModel):
    """File metadata response schema."""
    path: str
    size: int
    modified: Optional[datetime] = None
    exists: bool
    permissions: Optional[str] = None


class MetadataComparisonRequest(BaseModel):
    """Metadata comparison request schema."""
    source_endpoint_id: UUID
    destination_endpoint_id: UUID
    source_path: str
    destination_path: str
    sync_direction: str = Field(..., pattern="^(ftp_to_local|local_to_ftp|bidirectional)$")
    source_is_main: bool = True
    force_overwrite: bool = False


class MetadataComparisonResponse(BaseModel):
    """Metadata comparison response schema."""
    operation: str
    reason: str
    source_metadata: Optional[FileMetadataResponse] = None
    destination_metadata: Optional[FileMetadataResponse] = None


class EndpointConfig(BaseModel):
    """Temporary endpoint configuration for browsing without saving."""
    endpoint_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    remote_path: Optional[str] = "/"
    local_path: Optional[str] = None


@router.post("/config", response_model=DirectoryListing)
async def browse_directory_with_config(
    config: EndpointConfig,
    path: str = Query("/", description="Directory path to browse"),
    recursive: bool = Query(False, description="List recursively"),
    max_depth: int = Query(5, ge=1, le=10, description="Maximum recursion depth"),
    max_items: int = Query(1000, ge=1, le=10000, description="Maximum items to return"),
):
    """
    Browse directory contents using temporary endpoint configuration.

    This allows browsing without saving the endpoint first.
    """
    from app.core.local_manager import LocalManager, LocalConfig

    try:
        # Create appropriate manager based on endpoint type
        if config.endpoint_type.lower() == 'ftp':
            manager = FTPManager(
                host=config.host,
                port=config.port or 21,
                username=config.username,
                password=config.password,
                remote_path=config.remote_path or "/"
            )
        elif config.endpoint_type.lower() == 'sftp':
            manager = SFTPManager(
                host=config.host,
                port=config.port or 22,
                username=config.username,
                password=config.password,
                remote_path=config.remote_path or "/"
            )
        elif config.endpoint_type.lower() == 'local':
            # Always use /mnt as base_path (the mount point)
            # The 'path' parameter will be relative to /mnt
            local_config = LocalConfig(base_path="/mnt")
            manager = LocalManager(config=local_config)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported endpoint type: {config.endpoint_type}"
            )

        # Connect to endpoint
        if not manager.connect():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to connect to endpoint"
            )

        try:
            # List directory - LocalManager uses 'path' parameter, FTP/SFTP use 'remote_path'
            if config.endpoint_type.lower() == 'local':
                files = manager.list_directory(
                    path=path,
                    recursive=recursive,
                    max_depth=max_depth
                )
            else:
                files = manager.list_directory(
                    remote_path=path,
                    recursive=recursive,
                    max_depth=max_depth
                )

            # Limit results
            if len(files) > max_items:
                files = files[:max_items]

            # Convert to response format
            items = []
            total_files = 0
            total_directories = 0

            for file_info in files:
                # Handle both dict (LocalManager) and object (FTP/SFTP) formats
                if isinstance(file_info, dict):
                    name = file_info.get('name') or file_info.get('path', '').split('/')[-1]
                    path = file_info.get('path', '')
                    size = file_info.get('size', 0)
                    modified = file_info.get('modified')
                    is_file = file_info.get('is_file', False)
                    permissions = file_info.get('permissions')
                else:
                    name = file_info.path.split('/')[-1] or file_info.path
                    path = file_info.path
                    size = file_info.size
                    modified = file_info.modified
                    is_file = file_info.is_file
                    permissions = file_info.permissions

                items.append(DirectoryItem(
                    name=name,
                    path=path,
                    size=size,
                    modified=modified,
                    is_file=is_file,
                    permissions=permissions
                ))

                if is_file:
                    total_files += 1
                else:
                    total_directories += 1

            return DirectoryListing(
                path=path,
                items=items,
                total_items=len(items),
                total_files=total_files,
                total_directories=total_directories
            )
        finally:
            # LocalManager uses close() instead of disconnect()
            if hasattr(manager, 'disconnect'):
                manager.disconnect()
            elif hasattr(manager, 'close'):
                manager.close()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to browse directory: {str(e)}"
        )


@router.get("/{endpoint_id}", response_model=DirectoryListing)
async def browse_directory(
    endpoint_id: UUID,
    path: str = Query("/", description="Directory path to browse"),
    recursive: bool = Query(False, description="List recursively"),
    max_depth: int = Query(5, ge=1, le=10, description="Maximum recursion depth"),
    max_items: int = Query(1000, ge=1, le=10000, description="Maximum items to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Browse directory contents on an endpoint.

    Supports FTP, SFTP, and Local endpoints with configurable depth control.
    """
    from app.repositories.endpoint_repository import EndpointRepository

    # Get endpoint with decrypted password
    endpoint_repo = EndpointRepository(db)
    endpoint_data = await endpoint_repo.get_with_decrypted_password(endpoint_id)

    if not endpoint_data:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    endpoint_type = EndpointType(endpoint_data['endpoint_type'])

    if endpoint_type not in [EndpointType.FTP, EndpointType.SFTP, EndpointType.LOCAL]:
        raise HTTPException(
            status_code=400,
            detail=f"Endpoint type {endpoint_type} does not support directory browsing"
        )

    try:
        # Create appropriate manager based on endpoint type
        from app.core.local_manager import LocalManager, LocalConfig

        if endpoint_type == EndpointType.FTP:
            config = FTPConfig(
                host=endpoint_data['host'],
                port=endpoint_data.get('port') or 21,
                username=endpoint_data['username'],
                password=endpoint_data.get('password', '')
            )
            manager = FTPManager(config)
        elif endpoint_type == EndpointType.SFTP:
            config = SFTPConfig(
                host=endpoint_data['host'],
                port=endpoint_data.get('port') or 22,
                username=endpoint_data['username'],
                password=endpoint_data.get('password', '')
            )
            manager = SFTPManager(config)
        elif endpoint_type == EndpointType.LOCAL:
            # For LOCAL endpoints, use /mnt as base_path (the mount point)
            local_config = LocalConfig(base_path="/mnt")
            manager = LocalManager(config=local_config)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported endpoint type: {endpoint_type}"
            )

        # Connect
        if not manager.connect():
            raise HTTPException(
                status_code=503,
                detail="Failed to connect to endpoint"
            )

        # List directory - LocalManager uses 'path' parameter, FTP/SFTP use 'remote_path'
        if endpoint_type == EndpointType.LOCAL:
            files = manager.list_directory(
                path=path,
                recursive=recursive,
                max_depth=max_depth
            )
        else:
            files = manager.list_directory(
                remote_path=path,
                recursive=recursive,
                max_depth=max_depth
            )

        # Disconnect - LocalManager uses close() instead of disconnect()
        if hasattr(manager, 'disconnect'):
            manager.disconnect()
        elif hasattr(manager, 'close'):
            manager.close()

        # Convert to response format
        items = []
        total_files = 0
        total_directories = 0

        for file_info in files[:max_items]:  # Limit items
            # Handle both FTPFileInfo/SFTPFileInfo and dict (LocalManager)
            if isinstance(file_info, dict):
                is_file = file_info.get('is_file', True)
                is_directory = file_info.get('is_directory', False)
                name = file_info.get('name', file_info['path'].split('/')[-1])
                file_path = file_info['path']
                size = file_info.get('size', 0)
                modified = file_info.get('modified')
                permissions = file_info.get('permissions')
            else:
                is_file = getattr(file_info, 'is_file', True)
                is_directory = not is_file
                name = file_info.path.split('/')[-1]
                file_path = file_info.path
                size = file_info.size
                modified = file_info.modified
                permissions = file_info.permissions

            if is_file:
                total_files += 1
            else:
                total_directories += 1

            items.append(DirectoryItem(
                name=name,
                path=file_path,
                size=size,
                modified=modified,
                is_file=is_file,
                permissions=permissions
            ))

        return DirectoryListing(
            path=path,
            items=items,
            total_items=len(items),
            total_files=total_files,
            total_directories=total_directories
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to browse directory: {str(e)}"
        )


@router.get("/{endpoint_id}/metadata", response_model=FileMetadataResponse)
async def get_file_metadata(
    endpoint_id: UUID,
    path: str = Query(..., description="File path to get metadata for"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get file metadata from an endpoint.

    Returns file size, modification time, and other metadata.
    """
    from app.repositories.endpoint_repository import EndpointRepository

    # Get endpoint with decrypted password
    endpoint_repo = EndpointRepository(db)
    endpoint_data = await endpoint_repo.get_with_decrypted_password(endpoint_id)

    if not endpoint_data:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    endpoint_type = EndpointType(endpoint_data['endpoint_type'])

    try:
        # Create appropriate manager based on endpoint type
        from app.core.local_manager import LocalManager

        if endpoint_type == EndpointType.FTP:
            config = FTPConfig(
                host=endpoint_data['host'],
                port=endpoint_data.get('port') or 21,
                username=endpoint_data['username'],
                password=endpoint_data.get('password', '')
            )
            manager = FTPManager(config)
        elif endpoint_type == EndpointType.SFTP:
            config = SFTPConfig(
                host=endpoint_data['host'],
                port=endpoint_data.get('port') or 22,
                username=endpoint_data['username'],
                password=endpoint_data.get('password', '')
            )
            manager = SFTPManager(config)
        elif endpoint_type == EndpointType.LOCAL:
            manager = LocalManager(local_path=endpoint_data.get('local_path') or "/")
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported endpoint type: {endpoint_type}"
            )

        # Connect
        if not manager.connect():
            raise HTTPException(
                status_code=503,
                detail="Failed to connect to endpoint"
            )

        # Get file info
        file_info = manager.get_file_info(path)

        # Disconnect - LocalManager uses close() instead of disconnect()
        if hasattr(manager, 'disconnect'):
            manager.disconnect()
        elif hasattr(manager, 'close'):
            manager.close()

        if not file_info:
            raise HTTPException(status_code=404, detail="File not found")

        return FileMetadataResponse(
            path=path,
            size=file_info.get('size', 0),
            modified=file_info.get('modified'),
            exists=file_info.get('exists', True),
            permissions=file_info.get('permissions')
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get file metadata: {str(e)}"
        )


@router.post("/compare-metadata", response_model=MetadataComparisonResponse)
async def compare_file_metadata(request: MetadataComparisonRequest):
    """
    Compare file metadata between two endpoints.
    
    Determines what sync operation should be performed based on file sizes,
    modification times, and sync direction preferences.
    """
    try:
        # TODO: Get endpoints from database
        # TODO: Get file metadata from both endpoints
        # TODO: Use MetadataEngine to compare
        
        # For now, return mock comparison
        metadata_engine = MetadataEngine()
        
        # Mock metadata for demonstration
        source_metadata = FileMetadata(
            path=request.source_path,
            size=1024,
            modified=datetime.now(),
            exists=True
        )
        
        destination_metadata = FileMetadata(
            path=request.destination_path,
            size=1024,
            modified=datetime.now(),
            exists=True
        )
        
        # Convert string to enum
        sync_direction_enum = {
            "ftp_to_local": SyncDirection.FTP_TO_LOCAL,
            "local_to_ftp": SyncDirection.LOCAL_TO_FTP,
            "bidirectional": SyncDirection.BIDIRECTIONAL
        }[request.sync_direction]
        
        # Perform comparison
        result = metadata_engine.compare_files(
            source_metadata=source_metadata,
            destination_metadata=destination_metadata,
            sync_direction=sync_direction_enum,
            source_is_main=request.source_is_main,
            force_overwrite=request.force_overwrite
        )
        
        # Convert to response format
        def metadata_to_response(metadata: Optional[FileMetadata]) -> Optional[FileMetadataResponse]:
            if not metadata:
                return None
            return FileMetadataResponse(
                path=metadata.path,
                size=metadata.size,
                modified=metadata.modified,
                exists=metadata.exists
            )
        
        return MetadataComparisonResponse(
            operation=result.operation.value,
            reason=result.reason,
            source_metadata=metadata_to_response(result.source_metadata),
            destination_metadata=metadata_to_response(result.destination_metadata)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Metadata comparison failed: {str(e)}"
        )


@router.get("/{endpoint_id}/tree", response_model=Dict[str, Any])
async def get_directory_tree(
    endpoint_id: UUID,
    path: str = Query("/", description="Root path for tree"),
    max_depth: int = Query(3, ge=1, le=5, description="Maximum tree depth"),
    include_files: bool = Query(False, description="Include files in tree (directories only by default)")
):
    """
    Get directory tree structure for navigation.
    
    Returns hierarchical directory structure suitable for tree UI components.
    Optimized for large directory structures by limiting depth and optionally excluding files.
    """
    # TODO: Implement tree structure generation
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Directory tree not implemented yet"
    )


@router.post("/{endpoint_id}/scan")
async def scan_directory_with_cache(
    endpoint_id: UUID,
    path: str = Query("/", description="Directory path to scan"),
    recursive: bool = Query(True, description="Scan recursively"),
    max_depth: int = Query(5, ge=1, le=10, description="Maximum recursion depth"),
    use_cache: bool = Query(True, description="Use cached results if available"),
    cache_ttl_hours: int = Query(24, ge=1, le=168, description="Cache TTL in hours")
):
    """
    Scan directory with caching support.
    
    Performs comprehensive directory scan with results cached for performance.
    Useful for large directory structures that don't change frequently.
    """
    # TODO: Implement directory scanning with cache
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Directory scanning with cache not implemented yet"
    )


@router.get("/{endpoint_id}/search")
async def search_files(
    endpoint_id: UUID,
    query: str = Query(..., description="Search query (filename pattern)"),
    path: str = Query("/", description="Search root path"),
    recursive: bool = Query(True, description="Search recursively"),
    max_results: int = Query(100, ge=1, le=1000, description="Maximum results to return"),
    file_pattern: Optional[str] = Query(None, description="File pattern filter (e.g., *.jpg)")
):
    """
    Search for files matching criteria.
    
    Supports filename pattern matching and file extension filtering.
    Useful for finding specific files in large directory structures.
    """
    # TODO: Implement file search
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="File search not implemented yet"
    )


@router.post("/batch-compare")
async def batch_compare_metadata(
    source_endpoint_id: UUID,
    destination_endpoint_id: UUID,
    file_paths: List[str],
    sync_direction: str = Query(..., pattern="^(ftp_to_local|local_to_ftp|bidirectional)$"),
    source_is_main: bool = Query(True),
    force_overwrite: bool = Query(False)
):
    """
    Compare metadata for multiple files in batch.
    
    Efficient way to compare many files at once for sync planning.
    Returns list of comparison results for each file.
    """
    # TODO: Implement batch metadata comparison
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Batch metadata comparison not implemented yet"
    )


# Helper functions for endpoint management (to be moved to service layer)

async def get_endpoint_manager(endpoint: Endpoint):
    """
    Get appropriate manager (FTP/SFTP/Local) for endpoint.
    
    Args:
        endpoint: Endpoint database model
        
    Returns:
        Manager instance (FTPManager, SFTPManager, or LocalManager)
    """
    if endpoint.endpoint_type == EndpointType.FTP:
        config = FTPConfig(
            host=endpoint.host,
            username=endpoint.username,
            password=endpoint.password_encrypted,  # TODO: Decrypt
            port=endpoint.port or 21
        )
        return FTPManager(config)
    
    elif endpoint.endpoint_type == EndpointType.SFTP:
        config = SFTPConfig(
            host=endpoint.host,
            username=endpoint.username,
            password=endpoint.password_encrypted,  # TODO: Decrypt
            port=endpoint.port or 22
        )
        return SFTPManager(config)
    
    elif endpoint.endpoint_type == EndpointType.LOCAL:
        # TODO: Implement LocalManager
        raise NotImplementedError("LocalManager not implemented yet")
    
    elif endpoint.endpoint_type == EndpointType.S3:
        # S3 browsing would use existing S3Manager
        raise NotImplementedError("S3 browsing not implemented in this endpoint")
    
    else:
        raise ValueError(f"Unsupported endpoint type: {endpoint.endpoint_type}")


async def get_file_metadata_from_endpoint(endpoint: Endpoint, file_path: str) -> Optional[FileMetadata]:
    """
    Get file metadata from any endpoint type.
    
    Args:
        endpoint: Endpoint database model
        file_path: File path to get metadata for
        
    Returns:
        FileMetadata object or None if not found
    """
    manager = await get_endpoint_manager(endpoint)
    
    try:
        if hasattr(manager, 'get_file_info'):
            info = manager.get_file_info(file_path)
            if info:
                return FileMetadata(
                    path=file_path,
                    size=info.get('size', 0),
                    modified=info.get('modified'),
                    exists=info.get('exists', True)
                )
        return None
    finally:
        if hasattr(manager, 'close'):
            manager.close()
