"""
Operation Repository - Database operations for individual sync operations.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta

from app.database.models import SyncOperation, OperationType


class OperationRepository:
    """Repository for sync operation database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_all(
        self, 
        execution_id: Optional[UUID] = None,
        operation_type: Optional[OperationType] = None,
        success_only: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SyncOperation]:
        """
        Get all sync operations with optional filtering.
        
        Args:
            execution_id: Filter by execution ID
            operation_type: Filter by operation type
            success_only: Filter by success status
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of SyncOperation objects
        """
        query = self.db.query(SyncOperation)
        
        if execution_id:
            query = query.filter(SyncOperation.execution_id == execution_id)
        
        if operation_type:
            query = query.filter(SyncOperation.operation_type == operation_type)
        
        if success_only is not None:
            query = query.filter(SyncOperation.success == success_only)
        
        query = query.order_by(desc(SyncOperation.created_at))
        result = await query.offset(skip).limit(limit).all()
        return result

    async def get_by_id(self, operation_id: UUID) -> Optional[SyncOperation]:
        """
        Get sync operation by ID.
        
        Args:
            operation_id: Operation UUID
            
        Returns:
            SyncOperation object or None if not found
        """
        result = await self.db.query(SyncOperation).filter(SyncOperation.id == operation_id).first()
        return result

    async def create(self, operation_data: dict) -> SyncOperation:
        """
        Create new sync operation.
        
        Args:
            operation_data: Dictionary with operation data
            
        Returns:
            Created SyncOperation object
        """
        operation = SyncOperation(**operation_data)
        self.db.add(operation)
        await self.db.flush()  # Get ID without committing
        await self.db.refresh(operation)
        return operation

    async def create_batch(self, operations_data: List[dict]) -> List[SyncOperation]:
        """
        Create multiple sync operations in batch.
        
        Args:
            operations_data: List of operation data dictionaries
            
        Returns:
            List of created SyncOperation objects
        """
        operations = []
        for data in operations_data:
            operation = SyncOperation(**data)
            operations.append(operation)
            self.db.add(operation)
        
        await self.db.flush()
        
        for operation in operations:
            await self.db.refresh(operation)
        
        return operations

    async def update(self, operation_id: UUID, update_data: dict) -> Optional[SyncOperation]:
        """
        Update sync operation.
        
        Args:
            operation_id: Operation UUID
            update_data: Dictionary with fields to update
            
        Returns:
            Updated SyncOperation object or None if not found
        """
        operation = await self.get_by_id(operation_id)
        if not operation:
            return None
        
        for field, value in update_data.items():
            if hasattr(operation, field):
                setattr(operation, field, value)
        
        await self.db.flush()
        await self.db.refresh(operation)
        return operation

    async def delete(self, operation_id: UUID) -> bool:
        """
        Delete sync operation.
        
        Args:
            operation_id: Operation UUID
            
        Returns:
            True if deleted, False if not found
        """
        operation = await self.get_by_id(operation_id)
        if not operation:
            return False
        
        await self.db.delete(operation)
        return True

    async def get_operations_by_execution(
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
        return await self.get_all(
            execution_id=execution_id,
            operation_type=operation_type,
            success_only=success_only,
            limit=10000  # Large limit for execution operations
        )

    async def get_operation_statistics(
        self, 
        execution_id: Optional[UUID] = None,
        hours: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get operation statistics.
        
        Args:
            execution_id: Optional execution ID to filter by
            hours: Optional hours to look back
            
        Returns:
            Dictionary with operation statistics
        """
        query = self.db.query(
            SyncOperation.operation_type,
            SyncOperation.success,
            func.count(SyncOperation.id).label('count'),
            func.sum(SyncOperation.file_size).label('total_size'),
            func.avg(SyncOperation.file_size).label('avg_size')
        )
        
        if execution_id:
            query = query.filter(SyncOperation.execution_id == execution_id)
        
        if hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(SyncOperation.created_at >= cutoff_time)
        
        result = await query.group_by(
            SyncOperation.operation_type,
            SyncOperation.success
        ).all()
        
        stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'total_bytes': 0,
            'successful_bytes': 0,
            'operation_breakdown': {},
            'success_rate_percent': 0
        }
        
        for op_type, success, count, total_size, avg_size in result:
            stats['total_operations'] += count
            
            op_type_str = op_type.value
            if op_type_str not in stats['operation_breakdown']:
                stats['operation_breakdown'][op_type_str] = {
                    'total': 0,
                    'successful': 0,
                    'failed': 0,
                    'total_bytes': 0,
                    'avg_size_bytes': 0
                }
            
            stats['operation_breakdown'][op_type_str]['total'] += count
            stats['total_bytes'] += total_size or 0
            
            if success:
                stats['successful_operations'] += count
                stats['successful_bytes'] += total_size or 0
                stats['operation_breakdown'][op_type_str]['successful'] += count
            else:
                stats['failed_operations'] += count
                stats['operation_breakdown'][op_type_str]['failed'] += count
            
            stats['operation_breakdown'][op_type_str]['total_bytes'] += total_size or 0
            stats['operation_breakdown'][op_type_str]['avg_size_bytes'] = avg_size or 0
        
        # Calculate success rate
        if stats['total_operations'] > 0:
            stats['success_rate_percent'] = round(
                (stats['successful_operations'] / stats['total_operations']) * 100, 2
            )
        
        return stats

    async def get_failed_operations(
        self, 
        execution_id: Optional[UUID] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[SyncOperation]:
        """
        Get failed operations.
        
        Args:
            execution_id: Optional execution ID to filter by
            hours: Hours to look back
            limit: Maximum number of operations to return
            
        Returns:
            List of failed SyncOperation objects
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(SyncOperation).filter(
            and_(
                SyncOperation.success == False,
                SyncOperation.created_at >= cutoff_time
            )
        )
        
        if execution_id:
            query = query.filter(SyncOperation.execution_id == execution_id)
        
        result = await query.order_by(desc(SyncOperation.created_at)).limit(limit).all()
        return result

    async def get_large_file_operations(
        self, 
        min_size_mb: int = 100,
        hours: int = 24,
        limit: int = 50
    ) -> List[SyncOperation]:
        """
        Get operations for large files.
        
        Args:
            min_size_mb: Minimum file size in MB
            hours: Hours to look back
            limit: Maximum number of operations to return
            
        Returns:
            List of SyncOperation objects for large files
        """
        min_size_bytes = min_size_mb * 1024 * 1024
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.db.query(SyncOperation).filter(
            and_(
                SyncOperation.file_size >= min_size_bytes,
                SyncOperation.created_at >= cutoff_time
            )
        ).order_by(desc(SyncOperation.file_size)).limit(limit).all()
        
        return result

    async def cleanup_old_operations(self, days: int = 30) -> int:
        """
        Clean up old operation records.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of deleted operations
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.query(SyncOperation).filter(
            SyncOperation.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        return result

    async def get_operation_performance_metrics(
        self, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get operation performance metrics.
        
        Args:
            hours: Hours to look back
            
        Returns:
            Dictionary with performance metrics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get throughput metrics
        throughput_query = await self.db.query(
            func.sum(SyncOperation.file_size).label('total_bytes'),
            func.count(SyncOperation.id).label('total_operations'),
            func.avg(SyncOperation.file_size).label('avg_file_size')
        ).filter(
            and_(
                SyncOperation.created_at >= cutoff_time,
                SyncOperation.success == True
            )
        ).first()
        
        # Get operation type distribution
        type_distribution = await self.db.query(
            SyncOperation.operation_type,
            func.count(SyncOperation.id).label('count')
        ).filter(
            SyncOperation.created_at >= cutoff_time
        ).group_by(SyncOperation.operation_type).all()
        
        metrics = {
            'time_period_hours': hours,
            'total_bytes_transferred': throughput_query.total_bytes or 0,
            'total_successful_operations': throughput_query.total_operations or 0,
            'average_file_size_bytes': throughput_query.avg_file_size or 0,
            'throughput_mb_per_hour': 0,
            'operation_type_distribution': {}
        }
        
        # Calculate throughput
        if metrics['total_bytes_transferred'] > 0 and hours > 0:
            metrics['throughput_mb_per_hour'] = round(
                (metrics['total_bytes_transferred'] / (1024 * 1024)) / hours, 2
            )
        
        # Format operation type distribution
        for op_type, count in type_distribution:
            metrics['operation_type_distribution'][op_type.value] = count
        
        return metrics

    async def get_operations_by_file_pattern(
        self, 
        pattern: str,
        execution_id: Optional[UUID] = None,
        limit: int = 100
    ) -> List[SyncOperation]:
        """
        Get operations matching file pattern.
        
        Args:
            pattern: File path pattern (SQL LIKE pattern)
            execution_id: Optional execution ID to filter by
            limit: Maximum number of operations to return
            
        Returns:
            List of matching SyncOperation objects
        """
        query = self.db.query(SyncOperation).filter(
            or_(
                SyncOperation.source_path.like(f'%{pattern}%'),
                SyncOperation.destination_path.like(f'%{pattern}%')
            )
        )
        
        if execution_id:
            query = query.filter(SyncOperation.execution_id == execution_id)
        
        result = await query.order_by(desc(SyncOperation.created_at)).limit(limit).all()
        return result
