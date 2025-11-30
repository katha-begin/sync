"""
Execution Repository - Database operations for sync execution management.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, func, select
from datetime import datetime, timedelta

from app.database.models import SyncExecution, SyncOperation, ExecutionStatus, OperationType


class ExecutionRepository:
    """Repository for sync execution database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_all(
        self,
        session_id: Optional[UUID] = None,
        status: Optional[ExecutionStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SyncExecution]:
        """
        Get all sync executions with optional filtering.

        Args:
            session_id: Filter by session ID
            status: Filter by execution status
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of SyncExecution objects
        """
        query = select(SyncExecution)

        if session_id:
            query = query.filter(SyncExecution.session_id == session_id)

        if status:
            query = query.filter(SyncExecution.status == status)

        query = query.order_by(desc(SyncExecution.queued_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_by_id(self, execution_id: UUID) -> Optional[SyncExecution]:
        """
        Get sync execution by ID.

        Args:
            execution_id: Execution UUID

        Returns:
            SyncExecution object or None if not found
        """
        query = select(SyncExecution).filter(SyncExecution.id == execution_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, execution_data: dict) -> SyncExecution:
        """
        Create new sync execution.

        Args:
            execution_data: Dictionary with execution data

        Returns:
            Created SyncExecution object
        """
        execution = SyncExecution(**execution_data)
        self.db.add(execution)
        await self.db.flush()  # Get ID without committing
        await self.db.refresh(execution)
        return execution

    async def update(self, execution_id: UUID, update_data: dict) -> Optional[SyncExecution]:
        """
        Update sync execution.

        Args:
            execution_id: Execution UUID
            update_data: Dictionary with fields to update

        Returns:
            Updated SyncExecution object or None if not found
        """
        execution = await self.get_by_id(execution_id)
        if not execution:
            return None

        for field, value in update_data.items():
            if hasattr(execution, field):
                setattr(execution, field, value)

        await self.db.flush()
        await self.db.refresh(execution)
        return execution

    async def delete(self, execution_id: UUID) -> bool:
        """
        Delete sync execution.

        Args:
            execution_id: Execution UUID

        Returns:
            True if deleted, False if not found
        """
        execution = await self.get_by_id(execution_id)
        if not execution:
            return False

        await self.db.delete(execution)
        return True

    async def get_running_executions(self) -> List[SyncExecution]:
        """
        Get all currently running executions.

        Returns:
            List of running SyncExecution objects
        """
        query = select(SyncExecution).filter(
            SyncExecution.status.in_([
                ExecutionStatus.QUEUED,
                ExecutionStatus.RUNNING,
                ExecutionStatus.PAUSED
            ])
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_execution_operations(
        self,
        execution_id: UUID,
        operation_type: Optional[OperationType] = None,
        success_only: Optional[bool] = None
    ) -> List[SyncOperation]:
        """
        Get operations for a specific execution.

        Args:
            execution_id: Execution UUID
            operation_type: Filter by operation type
            success_only: Filter by success status

        Returns:
            List of SyncOperation objects
        """
        query = select(SyncOperation).filter(
            SyncOperation.execution_id == execution_id
        )

        if operation_type:
            query = query.filter(SyncOperation.operation_type == operation_type)

        if success_only is not None:
            query = query.filter(SyncOperation.success == success_only)

        query = query.order_by(SyncOperation.started_at)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_execution_statistics(self, execution_id: UUID) -> Dict[str, Any]:
        """
        Get statistics for a specific execution.

        Args:
            execution_id: Execution UUID

        Returns:
            Dictionary with execution statistics
        """
        # Get operation counts by type
        query = select(
            SyncOperation.operation_type,
            SyncOperation.success,
            func.count(SyncOperation.id).label('count'),
            func.sum(SyncOperation.file_size).label('total_size')
        ).filter(
            SyncOperation.execution_id == execution_id
        ).group_by(
            SyncOperation.operation_type,
            SyncOperation.success
        )

        result = await self.db.execute(query)
        operation_stats = result.all()

        stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'downloads': 0,
            'uploads': 0,
            'deletes': 0,
            'total_bytes': 0,
            'successful_bytes': 0
        }

        for op_type, success, count, total_size in operation_stats:
            stats['total_operations'] += count

            if success:
                stats['successful_operations'] += count
                stats['successful_bytes'] += total_size or 0
            else:
                stats['failed_operations'] += count

            stats['total_bytes'] += total_size or 0

            # Count by operation type
            if op_type == OperationType.DOWNLOAD:
                stats['downloads'] += count
            elif op_type == OperationType.UPLOAD:
                stats['uploads'] += count
            elif op_type == OperationType.DELETE:
                stats['deletes'] += count

        return stats

    async def get_recent_executions(
        self,
        hours: int = 24,
        limit: int = 50
    ) -> List[SyncExecution]:
        """
        Get recent executions within specified time window.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of executions

        Returns:
            List of recent SyncExecution objects
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        query = select(SyncExecution).filter(
            SyncExecution.queued_at >= cutoff_time
        ).order_by(desc(SyncExecution.queued_at)).limit(limit)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_execution_summary(self, session_id: UUID) -> Dict[str, Any]:
        """
        Get execution summary for a session.

        Args:
            session_id: Session UUID

        Returns:
            Dictionary with execution summary
        """
        # Get execution counts by status
        query = select(
            SyncExecution.status,
            func.count(SyncExecution.id).label('count')
        ).filter(
            SyncExecution.session_id == session_id
        ).group_by(SyncExecution.status)

        result = await self.db.execute(query)
        status_counts = result.all()

        # Get latest execution
        query2 = select(SyncExecution).filter(
            SyncExecution.session_id == session_id
        ).order_by(desc(SyncExecution.queued_at))

        result2 = await self.db.execute(query2)
        latest_execution = result2.scalars().first()

        summary = {
            'total_executions': sum(count for _, count in status_counts),
            'status_counts': {status.value: count for status, count in status_counts},
            'latest_execution': {
                'id': str(latest_execution.id) if latest_execution else None,
                'status': latest_execution.status.value if latest_execution else None,
                'queued_at': latest_execution.queued_at if latest_execution else None,
                'completed_at': latest_execution.completed_at if latest_execution else None
            } if latest_execution else None
        }

        return summary

    async def cleanup_old_executions(self, days: int = 30) -> int:
        """
        Clean up old execution records.

        Args:
            days: Number of days to keep

        Returns:
            Number of deleted executions
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # Delete old executions (operations will be cascade deleted)
        from sqlalchemy import delete as sql_delete

        query = sql_delete(SyncExecution).filter(
            and_(
                SyncExecution.queued_at < cutoff_date,
                SyncExecution.status.in_([
                    ExecutionStatus.COMPLETED,
                    ExecutionStatus.FAILED,
                    ExecutionStatus.CANCELLED
                ])
            )
        )

        result = await self.db.execute(query)
        return result.rowcount

    async def get_execution_logs(
        self, 
        execution_id: UUID,
        level: Optional[str] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get logs for a specific execution.
        
        Args:
            execution_id: Execution UUID
            level: Filter by log level
            limit: Maximum number of log entries
            
        Returns:
            List of log entries
        """
        # This would require a Log model with execution_id foreign key
        # For now, return empty list as placeholder
        return []

    async def cancel_execution(self, execution_id: UUID) -> bool:
        """
        Cancel a running execution.
        
        Args:
            execution_id: Execution UUID
            
        Returns:
            True if cancelled, False if not found or not cancellable
        """
        execution = await self.get_by_id(execution_id)
        if not execution:
            return False
        
        if execution.status not in [ExecutionStatus.QUEUED, ExecutionStatus.RUNNING, ExecutionStatus.PAUSED]:
            return False
        
        execution.status = ExecutionStatus.CANCELLED
        execution.completed_at = datetime.utcnow()
        
        await self.db.flush()
        return True

    async def get_active_executions_count(self) -> int:
        """
        Get count of active (running/queued) executions.

        Returns:
            Number of active executions
        """
        query = select(func.count(SyncExecution.id)).filter(
            SyncExecution.status.in_([
                ExecutionStatus.QUEUED,
                ExecutionStatus.RUNNING,
                ExecutionStatus.PAUSED
            ])
        )

        result = await self.db.execute(query)
        return result.scalar() or 0

    async def get_execution_duration_stats(self, session_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Get execution duration statistics.

        Args:
            session_id: Optional session ID to filter by

        Returns:
            Dictionary with duration statistics
        """
        query = select(
            func.avg(
                func.extract('epoch', SyncExecution.completed_at - SyncExecution.started_at)
            ).label('avg_duration'),
            func.min(
                func.extract('epoch', SyncExecution.completed_at - SyncExecution.started_at)
            ).label('min_duration'),
            func.max(
                func.extract('epoch', SyncExecution.completed_at - SyncExecution.started_at)
            ).label('max_duration')
        ).filter(
            and_(
                SyncExecution.status == ExecutionStatus.COMPLETED,
                SyncExecution.started_at.isnot(None),
                SyncExecution.completed_at.isnot(None)
            )
        )

        if session_id:
            query = query.filter(SyncExecution.session_id == session_id)

        result = await self.db.execute(query)
        row = result.first()

        return {
            'average_duration_seconds': float(row.avg_duration) if row and row.avg_duration else 0,
            'minimum_duration_seconds': float(row.min_duration) if row and row.min_duration else 0,
            'maximum_duration_seconds': float(row.max_duration) if row and row.max_duration else 0
        }
