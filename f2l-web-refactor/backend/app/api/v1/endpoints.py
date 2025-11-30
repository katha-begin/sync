"""
Endpoints API - Manage FTP/SFTP/S3/Local endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

from app.database.models import EndpointType
from app.repositories.endpoint_repository import EndpointRepository
from app.core.security import encrypt_password
from app.database.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class EndpointBase(BaseModel):
    """Base endpoint schema."""
    name: str
    endpoint_type: EndpointType
    notes: Optional[str] = None

    # FTP/SFTP fields
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    remote_path: Optional[str] = "/"

    # S3 fields
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None

    # Local fields
    local_path: Optional[str] = None


class EndpointCreate(EndpointBase):
    """Endpoint creation schema."""
    pass


class EndpointUpdate(BaseModel):
    """Endpoint update schema."""
    name: Optional[str] = None
    notes: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    remote_path: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    local_path: Optional[str] = None
    is_active: Optional[bool] = None


class EndpointResponse(BaseModel):
    """Endpoint response schema."""
    id: UUID
    name: str
    endpoint_type: EndpointType
    connection_status: Optional[str] = None
    is_active: bool
    notes: Optional[str] = None

    # Connection details (passwords excluded)
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    remote_path: Optional[str] = None
    s3_bucket: Optional[str] = None
    s3_region: Optional[str] = None
    s3_access_key: Optional[str] = None
    local_path: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime
    last_health_check: Optional[datetime] = None

    class Config:
        from_attributes = True


class ConnectionTestResponse(BaseModel):
    """Connection test response schema."""
    success: bool
    message: str
    details: Optional[dict] = None


@router.get("/", response_model=List[EndpointResponse])
async def list_endpoints(
    endpoint_type: Optional[EndpointType] = Query(None, description="Filter by endpoint type"),
    active_only: bool = Query(True, description="Only return active endpoints"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records"),
    db: AsyncSession = Depends(get_db)
):
    """List all endpoints with optional filtering."""
    try:
        repo = EndpointRepository(db)
        endpoints = await repo.get_all(
            endpoint_type=endpoint_type,
            active_only=active_only,
            skip=skip,
            limit=limit
        )
        return endpoints
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve endpoints: {str(e)}"
        )


@router.post("/", response_model=EndpointResponse, status_code=status.HTTP_201_CREATED)
async def create_endpoint(endpoint: EndpointCreate, db: AsyncSession = Depends(get_db)):
    """Create new endpoint."""
    try:
        repo = EndpointRepository(db)

        # Check if endpoint name already exists
        existing = await repo.get_by_name(endpoint.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Endpoint with name '{endpoint.name}' already exists"
            )

        # Prepare endpoint data
        endpoint_data = endpoint.dict(exclude_unset=True)

        # Convert endpoint_type to lowercase string value for database
        # Pydantic may serialize enum as string name (FTP) instead of value (ftp)
        if 'endpoint_type' in endpoint_data:
            endpoint_type = endpoint_data['endpoint_type']
            if isinstance(endpoint_type, EndpointType):
                # If it's an enum, get its value
                endpoint_data['endpoint_type'] = endpoint_type.value
            elif isinstance(endpoint_type, str):
                # If it's already a string, convert to lowercase
                endpoint_data['endpoint_type'] = endpoint_type.lower()

        # Encrypt passwords if provided
        if endpoint_data.get('password'):
            endpoint_data['password_encrypted'] = encrypt_password(endpoint_data.pop('password'))

        if endpoint_data.get('s3_secret_key'):
            endpoint_data['s3_secret_key_encrypted'] = encrypt_password(endpoint_data.pop('s3_secret_key'))

        # Set default values
        endpoint_data['is_active'] = True
        endpoint_data['connection_status'] = 'not_tested'

        # Create endpoint
        new_endpoint = await repo.create(endpoint_data)
        return new_endpoint

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create endpoint: {str(e)}"
        )


@router.get("/{endpoint_id}", response_model=EndpointResponse)
async def get_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get endpoint by ID."""
    try:
        repo = EndpointRepository(db)
        endpoint = await repo.get_by_id(endpoint_id)

        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint not found"
            )

        return endpoint

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve endpoint: {str(e)}"
        )


@router.put("/{endpoint_id}", response_model=EndpointResponse)
async def update_endpoint(
    endpoint_id: UUID,
    endpoint_update: EndpointUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update endpoint."""
    try:
        repo = EndpointRepository(db)

        # Check if endpoint exists
        existing = await repo.get_by_id(endpoint_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint not found"
            )

        # Prepare update data
        update_data = endpoint_update.dict(exclude_unset=True)

        # Encrypt passwords if provided
        if 'password' in update_data and update_data['password']:
            update_data['password_encrypted'] = encrypt_password(update_data.pop('password'))

        if 's3_secret_key' in update_data and update_data['s3_secret_key']:
            update_data['s3_secret_key_encrypted'] = encrypt_password(update_data.pop('s3_secret_key'))

        # Update endpoint
        updated_endpoint = await repo.update(endpoint_id, update_data)
        return updated_endpoint

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update endpoint: {str(e)}"
        )


@router.delete("/{endpoint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    """Delete endpoint."""
    try:
        repo = EndpointRepository(db)

        success = await repo.delete(endpoint_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint not found"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete endpoint: {str(e)}"
        )


@router.post("/test-config", response_model=ConnectionTestResponse)
async def test_endpoint_config(config: EndpointCreate):
    """Test endpoint connection without saving it."""
    try:
        from app.services.endpoint_service import EndpointService
        from app.core.ftp_manager import FTPManager
        from app.core.sftp_manager import SFTPManager
        from app.core.local_manager import LocalManager

        # Create appropriate manager based on endpoint type
        if config.endpoint_type == EndpointType.FTP:
            from app.core.ftp_manager import FTPConfig
            ftp_config = FTPConfig(
                host=config.host,
                port=config.port or 21,
                username=config.username,
                password=config.password
            )
            manager = FTPManager(config=ftp_config)
        elif config.endpoint_type == EndpointType.SFTP:
            from app.core.sftp_manager import SFTPConfig
            sftp_config = SFTPConfig(
                host=config.host,
                port=config.port or 22,
                username=config.username,
                password=config.password
            )
            manager = SFTPManager(config=sftp_config)
        elif config.endpoint_type == EndpointType.LOCAL:
            from app.core.local_manager import LocalConfig
            local_config = LocalConfig(base_path=config.local_path or "/")
            manager = LocalManager(config=local_config)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported endpoint type: {config.endpoint_type}"
            )

        # Test connection
        if manager.connect():
            manager.disconnect()
            return ConnectionTestResponse(
                success=True,
                message="Connection successful!"
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message="Connection failed"
            )
    except Exception as e:
        return ConnectionTestResponse(
            success=False,
            message=str(e)
        )


@router.post("/{endpoint_id}/connect", response_model=ConnectionTestResponse)
async def connect_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    """Connect to endpoint and update status."""
    try:
        repo = EndpointRepository(db)

        # Get endpoint with decrypted credentials
        endpoint_data = await repo.get_with_decrypted_password(endpoint_id)
        if not endpoint_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint not found"
            )

        # Test connection based on endpoint type
        if endpoint_data['endpoint_type'] == EndpointType.FTP:
            result = await test_ftp_connection(endpoint_data)
        elif endpoint_data['endpoint_type'] == EndpointType.SFTP:
            result = await test_sftp_connection(endpoint_data)
        elif endpoint_data['endpoint_type'] == EndpointType.S3:
            result = await test_s3_connection(endpoint_data)
        elif endpoint_data['endpoint_type'] == EndpointType.LOCAL:
            result = await test_local_connection(endpoint_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported endpoint type: {endpoint_data['endpoint_type']}"
            )

        # Update connection status in database
        status_value = "connected" if result['success'] else "error"
        await repo.update_connection_status(
            endpoint_id,
            status_value,
            result['message']
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Connection failed: {str(e)}"
        )


@router.post("/{endpoint_id}/disconnect", response_model=ConnectionTestResponse)
async def disconnect_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    """Disconnect endpoint and update status."""
    try:
        repo = EndpointRepository(db)

        # Get endpoint
        endpoint = await repo.get_by_id(endpoint_id)
        if not endpoint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint not found"
            )

        # Update connection status to disconnected
        await repo.update_connection_status(
            endpoint_id,
            "disconnected",
            "Manually disconnected"
        )

        return {
            "success": True,
            "message": "Disconnected successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Disconnect failed: {str(e)}"
        )


@router.post("/{endpoint_id}/restart", response_model=ConnectionTestResponse)
async def restart_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    """Restart endpoint connection (disconnect then connect)."""
    try:
        repo = EndpointRepository(db)

        # Get endpoint with decrypted credentials
        endpoint_data = await repo.get_with_decrypted_password(endpoint_id)
        if not endpoint_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Endpoint not found"
            )

        # First disconnect
        await repo.update_connection_status(
            endpoint_id,
            "restarting",
            "Restarting connection..."
        )

        # Then reconnect
        if endpoint_data['endpoint_type'] == EndpointType.FTP:
            result = await test_ftp_connection(endpoint_data)
        elif endpoint_data['endpoint_type'] == EndpointType.SFTP:
            result = await test_sftp_connection(endpoint_data)
        elif endpoint_data['endpoint_type'] == EndpointType.S3:
            result = await test_s3_connection(endpoint_data)
        elif endpoint_data['endpoint_type'] == EndpointType.LOCAL:
            result = await test_local_connection(endpoint_data)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported endpoint type: {endpoint_data['endpoint_type']}"
            )

        # Update connection status
        status_value = "connected" if result['success'] else "error"
        await repo.update_connection_status(
            endpoint_id,
            status_value,
            result['message']
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restart failed: {str(e)}"
        )


# Helper functions for connection testing

async def test_ftp_connection(endpoint_data: dict) -> dict:
    """Test FTP connection."""
    from app.services.ftp_service import ftp_service

    try:
        result = await ftp_service.test_connection(
            host=endpoint_data['host'],
            port=endpoint_data.get('port', 21),
            username=endpoint_data['username'],
            password=endpoint_data.get('password', ''),
            timeout=10
        )

        return {
            "success": result['success'],
            "message": result['message'],
            "details": result.get('details', {})
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"FTP connection error: {str(e)}",
            "details": {"endpoint_type": "FTP"}
        }


async def test_sftp_connection(endpoint_data: dict) -> dict:
    """Test SFTP connection."""
    from app.core.sftp_manager import SFTPManager, SFTPConfig

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

            return {
                "success": health_result['success'],
                "message": health_result['message'],
                "details": {
                    "endpoint_type": "SFTP",
                    "host": endpoint_data['host'],
                    "port": endpoint_data.get('port', 22)
                }
            }
        else:
            return {
                "success": False,
                "message": "Failed to establish SFTP connection",
                "details": {"endpoint_type": "SFTP"}
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"SFTP connection error: {str(e)}",
            "details": {"endpoint_type": "SFTP"}
        }


async def test_s3_connection(endpoint_data: dict) -> dict:
    """Test S3 connection."""
    from app.core.s3_manager import S3Manager, S3Config

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
            "success": result['success'],
            "message": result['message'],
            "details": {
                "endpoint_type": "S3",
                "bucket": endpoint_data['s3_bucket'],
                "region": endpoint_data.get('s3_region', 'us-east-1')
            }
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"S3 connection error: {str(e)}",
            "details": {"endpoint_type": "S3"}
        }


async def test_local_connection(endpoint_data: dict) -> dict:
    """Test local path connection."""
    import os

    try:
        local_path = endpoint_data.get('local_path')
        if not local_path:
            return {
                "success": False,
                "message": "Local path not specified",
                "details": {"endpoint_type": "LOCAL"}
            }

        # If path is relative, join with /mnt (the base mount point)
        if not local_path.startswith('/'):
            full_path = os.path.join('/mnt', local_path)
        else:
            full_path = local_path

        if os.path.exists(full_path) and os.path.isdir(full_path):
            # Test read/write permissions
            test_file = os.path.join(full_path, '.f2l_test')
            try:
                with open(test_file, 'w') as f:
                    f.write('test')
                os.remove(test_file)

                return {
                    "success": True,
                    "message": "Local path accessible with read/write permissions",
                    "details": {
                        "endpoint_type": "LOCAL",
                        "path": full_path
                    }
                }
            except Exception as perm_error:
                return {
                    "success": False,
                    "message": f"Local path exists but no write permissions: {str(perm_error)}",
                    "details": {"endpoint_type": "LOCAL", "path": full_path}
                }
        else:
            return {
                "success": False,
                "message": f"Local path does not exist or is not a directory: {full_path}",
                "details": {"endpoint_type": "LOCAL", "path": full_path}
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"Local path error: {str(e)}",
            "details": {"endpoint_type": "LOCAL"}
        }
