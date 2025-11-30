"""
Endpoint Repository - Database operations for endpoint management.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select

from app.database.models import Endpoint, EndpointType
from app.core.security import decrypt_password


class EndpointRepository:
    """Repository for endpoint database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_all(
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
        query = select(Endpoint)

        if endpoint_type:
            query = query.filter(Endpoint.endpoint_type == endpoint_type)

        if active_only:
            query = query.filter(Endpoint.is_active == True)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, endpoint_id: UUID) -> Optional[Endpoint]:
        """
        Get endpoint by ID.

        Args:
            endpoint_id: Endpoint UUID

        Returns:
            Endpoint object or None if not found
        """
        query = select(Endpoint).filter(Endpoint.id == endpoint_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[Endpoint]:
        """
        Get endpoint by name.

        Args:
            name: Endpoint name

        Returns:
            Endpoint object or None if not found
        """
        query = select(Endpoint).filter(Endpoint.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, endpoint_data: dict) -> Endpoint:
        """
        Create new endpoint.

        Args:
            endpoint_data: Dictionary with endpoint data

        Returns:
            Created Endpoint object
        """
        endpoint = Endpoint(**endpoint_data)
        self.db.add(endpoint)
        await self.db.commit()
        await self.db.refresh(endpoint)
        return endpoint

    async def update(self, endpoint_id: UUID, update_data: dict) -> Optional[Endpoint]:
        """
        Update endpoint.

        Args:
            endpoint_id: Endpoint UUID
            update_data: Dictionary with fields to update

        Returns:
            Updated Endpoint object or None if not found
        """
        endpoint = await self.get_by_id(endpoint_id)
        if not endpoint:
            return None

        for field, value in update_data.items():
            if hasattr(endpoint, field):
                setattr(endpoint, field, value)

        await self.db.commit()
        await self.db.refresh(endpoint)
        return endpoint

    async def delete(self, endpoint_id: UUID) -> bool:
        """
        Delete endpoint.

        Args:
            endpoint_id: Endpoint UUID

        Returns:
            True if deleted, False if not found
        """
        endpoint = await self.get_by_id(endpoint_id)
        if not endpoint:
            return False

        await self.db.delete(endpoint)
        await self.db.commit()
        return True

    async def update_connection_status(
        self,
        endpoint_id: UUID,
        status: str,
        message: Optional[str] = None
    ) -> Optional[Endpoint]:
        """
        Update endpoint connection status.

        Args:
            endpoint_id: Endpoint UUID
            status: Connection status
            message: Optional status message

        Returns:
            Updated Endpoint object or None if not found
        """
        from datetime import datetime

        endpoint = await self.get_by_id(endpoint_id)
        if not endpoint:
            return None

        endpoint.connection_status = status
        endpoint.last_health_check = datetime.utcnow()
        if message:
            endpoint.health_check_message = message

        await self.db.commit()
        await self.db.refresh(endpoint)
        return endpoint

    async def get_active_by_type(self, endpoint_type: EndpointType) -> List[Endpoint]:
        """
        Get all active endpoints of specific type.

        Args:
            endpoint_type: Type of endpoints to retrieve

        Returns:
            List of active Endpoint objects
        """
        query = select(Endpoint).filter(
            and_(
                Endpoint.endpoint_type == endpoint_type,
                Endpoint.is_active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def search(self, query: str, limit: int = 50) -> List[Endpoint]:
        """
        Search endpoints by name or host.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching Endpoint objects
        """
        search_pattern = f"%{query}%"
        stmt = select(Endpoint).filter(
            or_(
                Endpoint.name.ilike(search_pattern),
                Endpoint.host.ilike(search_pattern)
            )
        ).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_with_decrypted_password(self, endpoint_id: UUID) -> Optional[dict]:
        """
        Get endpoint with decrypted password for connection.

        Args:
            endpoint_id: Endpoint UUID

        Returns:
            Dictionary with endpoint data and decrypted password
        """
        endpoint = await self.get_by_id(endpoint_id)
        if not endpoint:
            return None

        # Convert to dict
        endpoint_dict = {
            'id': endpoint.id,
            'name': endpoint.name,
            'endpoint_type': endpoint.endpoint_type,
            'host': endpoint.host,
            'port': endpoint.port,
            'username': endpoint.username,
            'remote_path': endpoint.remote_path,
            'local_path': endpoint.local_path,
            's3_bucket': endpoint.s3_bucket,
            's3_region': endpoint.s3_region,
            's3_access_key': endpoint.s3_access_key,
            'connection_status': endpoint.connection_status,
            'is_active': endpoint.is_active,
            'notes': endpoint.notes
        }

        # Decrypt passwords if they exist
        if endpoint.password_encrypted:
            try:
                endpoint_dict['password'] = decrypt_password(endpoint.password_encrypted)
            except Exception:
                endpoint_dict['password'] = None

        if endpoint.s3_secret_key_encrypted:
            try:
                endpoint_dict['s3_secret_key'] = decrypt_password(endpoint.s3_secret_key_encrypted)
            except Exception:
                endpoint_dict['s3_secret_key'] = None

        return endpoint_dict

    async def count_by_type(self) -> dict:
        """
        Count endpoints by type.

        Returns:
            Dictionary with counts by endpoint type
        """
        from sqlalchemy import func

        stmt = select(
            Endpoint.endpoint_type,
            func.count(Endpoint.id).label('count')
        ).group_by(Endpoint.endpoint_type)

        result = await self.db.execute(stmt)
        rows = result.all()

        return {str(endpoint_type): count for endpoint_type, count in rows}

    async def get_health_status_summary(self) -> dict:
        """
        Get summary of endpoint health statuses.

        Returns:
            Dictionary with health status counts
        """
        from sqlalchemy import func

        stmt = select(
            Endpoint.connection_status,
            func.count(Endpoint.id).label('count')
        ).group_by(Endpoint.connection_status)

        result = await self.db.execute(stmt)
        rows = result.all()

        return {status or 'unknown': count for status, count in rows}

    async def get_recently_updated(self, hours: int = 24, limit: int = 10) -> List[Endpoint]:
        """
        Get recently updated endpoints.

        Args:
            hours: Number of hours to look back
            limit: Maximum results

        Returns:
            List of recently updated Endpoint objects
        """
        from datetime import datetime, timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        stmt = select(Endpoint).filter(
            Endpoint.updated_at >= cutoff_time
        ).order_by(Endpoint.updated_at.desc()).limit(limit)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def bulk_update_status(self, endpoint_ids: List[UUID], status: str) -> int:
        """
        Bulk update connection status for multiple endpoints.

        Args:
            endpoint_ids: List of endpoint UUIDs
            status: New connection status

        Returns:
            Number of updated endpoints
        """
        from datetime import datetime
        from sqlalchemy import update

        stmt = update(Endpoint).where(
            Endpoint.id.in_(endpoint_ids)
        ).values(
            connection_status=status,
            last_health_check=datetime.utcnow()
        )

        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount
