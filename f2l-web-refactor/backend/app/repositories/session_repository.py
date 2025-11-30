"""
Session Repository - Database operations for sync session management.
"""
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select

from app.database.models import SyncSession, SyncExecution, ExecutionStatus


class SessionRepository:
    """Repository for sync session database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_all(
        self,
        active_only: bool = True,
        skip: int = 0,
        limit: int = 100
    ) -> List[SyncSession]:
        """
        Get all sync sessions with optional filtering.

        Args:
            active_only: Only return active sessions
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of SyncSession objects
        """
        query = select(SyncSession)

        if active_only:
            query = query.filter(SyncSession.is_active == True)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, session_id: UUID) -> Optional[SyncSession]:
        """
        Get sync session by ID.

        Args:
            session_id: Session UUID

        Returns:
            SyncSession object or None if not found
        """
        query = select(SyncSession).filter(SyncSession.id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> Optional[SyncSession]:
        """
        Get sync session by name.

        Args:
            name: Session name

        Returns:
            SyncSession object or None if not found
        """
        query = select(SyncSession).filter(SyncSession.name == name)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, session_data: dict) -> SyncSession:
        """
        Create new sync session.

        Args:
            session_data: Dictionary with session data

        Returns:
            Created SyncSession object
        """
        session = SyncSession(**session_data)
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def update(self, session_id: UUID, update_data: dict) -> Optional[SyncSession]:
        """
        Update sync session.

        Args:
            session_id: Session UUID
            update_data: Dictionary with fields to update

        Returns:
            Updated SyncSession object or None if not found
        """
        session = await self.get_by_id(session_id)
        if not session:
            return None

        for field, value in update_data.items():
            if hasattr(session, field):
                setattr(session, field, value)

        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete(self, session_id: UUID) -> bool:
        """
        Delete sync session.

        Args:
            session_id: Session UUID

        Returns:
            True if deleted, False if not found
        """
        session = await self.get_by_id(session_id)
        if not session:
            return False

        await self.db.delete(session)
        await self.db.commit()
        return True

    async def get_by_endpoint(self, endpoint_id: UUID) -> List[SyncSession]:
        """
        Get sessions that use a specific endpoint.

        Args:
            endpoint_id: Endpoint UUID

        Returns:
            List of SyncSession objects
        """
        query = select(SyncSession).filter(
            or_(
                SyncSession.source_endpoint_id == endpoint_id,
                SyncSession.destination_endpoint_id == endpoint_id
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_scheduled_sessions(self) -> List[SyncSession]:
        """
        Get all sessions with scheduling enabled.

        Returns:
            List of scheduled SyncSession objects
        """
        query = select(SyncSession).filter(
            and_(
                SyncSession.schedule_enabled == True,
                SyncSession.is_active == True
            )
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def is_session_running(self, session_id: UUID) -> bool:
        """
        Check if session is currently running.

        Args:
            session_id: Session UUID

        Returns:
            True if session is running, False otherwise
        """
        query = select(SyncExecution).filter(
            and_(
                SyncExecution.session_id == session_id,
                SyncExecution.status.in_([
                    ExecutionStatus.QUEUED,
                    ExecutionStatus.RUNNING,
                    ExecutionStatus.PAUSED
                ])
            )
        )
        result = await self.db.execute(query)
        running_execution = result.scalar_one_or_none()

        return running_execution is not None

    async def get_last_execution(self, session_id: UUID) -> Optional[SyncExecution]:
        """
        Get the last execution for a session.

        Args:
            session_id: Session UUID

        Returns:
            Last SyncExecution object or None
        """
        query = select(SyncExecution).filter(
            SyncExecution.session_id == session_id
        ).order_by(SyncExecution.created_at.desc())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_execution_history(
        self,
        session_id: UUID,
        limit: int = 50
    ) -> List[SyncExecution]:
        """
        Get execution history for a session.

        Args:
            session_id: Session UUID
            limit: Maximum number of executions to return

        Returns:
            List of SyncExecution objects
        """
        query = select(SyncExecution).filter(
            SyncExecution.session_id == session_id
        ).order_by(SyncExecution.created_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def search(self, query: str, limit: int = 50) -> List[SyncSession]:
        """
        Search sessions by name or notes.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of matching SyncSession objects
        """
        search_pattern = f"%{query}%"
        stmt = select(SyncSession).filter(
            or_(
                SyncSession.name.ilike(search_pattern),
                SyncSession.notes.ilike(search_pattern)
            )
        ).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_sessions_by_status(self, status: str) -> List[SyncSession]:
        """
        Get sessions by their last execution status.

        Args:
            status: Execution status to filter by

        Returns:
            List of SyncSession objects
        """
        # This would require a join with SyncExecution table
        # For now, return empty list as placeholder
        return []

    async def count_by_status(self) -> dict:
        """
        Count sessions by their activity status.

        Returns:
            Dictionary with counts by status
        """
        from sqlalchemy import func

        stmt = select(
            SyncSession.is_active,
            func.count(SyncSession.id).label('count')
        ).group_by(SyncSession.is_active)
        result = await self.db.execute(stmt)
        rows = result.all()

        return {
            'active' if is_active else 'inactive': count
            for is_active, count in rows
        }

    async def get_recently_updated(self, hours: int = 24, limit: int = 10) -> List[SyncSession]:
        """
        Get recently updated sessions.

        Args:
            hours: Number of hours to look back
            limit: Maximum results

        Returns:
            List of recently updated SyncSession objects
        """
        from datetime import datetime, timedelta

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = select(SyncSession).filter(
            SyncSession.updated_at >= cutoff_time
        ).order_by(SyncSession.updated_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def bulk_update_status(self, session_ids: List[UUID], is_active: bool) -> int:
        """
        Bulk update active status for multiple sessions.

        Args:
            session_ids: List of session UUIDs
            is_active: New active status

        Returns:
            Number of updated sessions
        """
        from sqlalchemy import update

        stmt = update(SyncSession).where(
            SyncSession.id.in_(session_ids)
        ).values(is_active=is_active)

        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def get_sessions_due_for_execution(self) -> List[SyncSession]:
        """
        Get sessions that are due for scheduled execution.

        This would implement cron parsing and interval checking.
        For now, returns empty list as placeholder.

        Returns:
            List of SyncSession objects due for execution
        """
        # TODO: Implement cron parsing and interval checking
        return []
