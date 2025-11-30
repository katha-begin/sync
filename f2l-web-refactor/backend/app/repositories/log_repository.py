"""
Log Repository - Database operations for application logging.
"""
from typing import List, Optional, Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, desc, func
from datetime import datetime, timedelta

from app.database.models import Log


class LogRepository:
    """Repository for application log database operations."""

    def __init__(self, db: AsyncSession):
        """Initialize repository with database session."""
        self.db = db

    async def get_all(
        self, 
        level: Optional[str] = None,
        component: Optional[str] = None,
        execution_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        hours: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Log]:
        """
        Get all logs with optional filtering.
        
        Args:
            level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            component: Filter by component name
            execution_id: Filter by execution ID
            session_id: Filter by session ID
            hours: Filter by hours back from now
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of Log objects
        """
        query = self.db.query(Log)
        
        if level:
            query = query.filter(Log.level == level.upper())
        
        if component:
            query = query.filter(Log.component.like(f'%{component}%'))
        
        if execution_id:
            query = query.filter(Log.execution_id == execution_id)
        
        if session_id:
            query = query.filter(Log.session_id == session_id)
        
        if hours:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(Log.created_at >= cutoff_time)
        
        query = query.order_by(desc(Log.created_at))
        result = await query.offset(skip).limit(limit).all()
        return result

    async def get_by_id(self, log_id: UUID) -> Optional[Log]:
        """
        Get log entry by ID.
        
        Args:
            log_id: Log UUID
            
        Returns:
            Log object or None if not found
        """
        result = await self.db.query(Log).filter(Log.id == log_id).first()
        return result

    async def create(self, log_data: dict) -> Log:
        """
        Create new log entry.
        
        Args:
            log_data: Dictionary with log data
            
        Returns:
            Created Log object
        """
        log_entry = Log(**log_data)
        self.db.add(log_entry)
        await self.db.flush()  # Get ID without committing
        await self.db.refresh(log_entry)
        return log_entry

    async def create_batch(self, logs_data: List[dict]) -> List[Log]:
        """
        Create multiple log entries in batch.
        
        Args:
            logs_data: List of log data dictionaries
            
        Returns:
            List of created Log objects
        """
        logs = []
        for data in logs_data:
            log_entry = Log(**data)
            logs.append(log_entry)
            self.db.add(log_entry)
        
        await self.db.flush()
        
        for log_entry in logs:
            await self.db.refresh(log_entry)
        
        return logs

    async def delete(self, log_id: UUID) -> bool:
        """
        Delete log entry.
        
        Args:
            log_id: Log UUID
            
        Returns:
            True if deleted, False if not found
        """
        log_entry = await self.get_by_id(log_id)
        if not log_entry:
            return False
        
        await self.db.delete(log_entry)
        return True

    async def get_logs_by_execution(
        self, 
        execution_id: UUID,
        level: Optional[str] = None,
        limit: int = 1000
    ) -> List[Log]:
        """
        Get logs for a specific execution.
        
        Args:
            execution_id: Execution UUID
            level: Optional log level filter
            limit: Maximum number of logs to return
            
        Returns:
            List of Log objects
        """
        return await self.get_all(
            execution_id=execution_id,
            level=level,
            limit=limit
        )

    async def get_logs_by_session(
        self, 
        session_id: UUID,
        level: Optional[str] = None,
        hours: int = 24,
        limit: int = 1000
    ) -> List[Log]:
        """
        Get logs for a specific session.
        
        Args:
            session_id: Session UUID
            level: Optional log level filter
            hours: Hours to look back
            limit: Maximum number of logs to return
            
        Returns:
            List of Log objects
        """
        return await self.get_all(
            session_id=session_id,
            level=level,
            hours=hours,
            limit=limit
        )

    async def get_error_logs(
        self, 
        hours: int = 24,
        component: Optional[str] = None,
        limit: int = 100
    ) -> List[Log]:
        """
        Get error and critical logs.
        
        Args:
            hours: Hours to look back
            component: Optional component filter
            limit: Maximum number of logs to return
            
        Returns:
            List of error Log objects
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(Log).filter(
            and_(
                Log.level.in_(['ERROR', 'CRITICAL']),
                Log.created_at >= cutoff_time
            )
        )
        
        if component:
            query = query.filter(Log.component.like(f'%{component}%'))
        
        result = await query.order_by(desc(Log.created_at)).limit(limit).all()
        return result

    async def get_log_statistics(
        self, 
        hours: int = 24,
        component: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get log statistics.
        
        Args:
            hours: Hours to look back
            component: Optional component filter
            
        Returns:
            Dictionary with log statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(
            Log.level,
            func.count(Log.id).label('count')
        ).filter(Log.created_at >= cutoff_time)
        
        if component:
            query = query.filter(Log.component.like(f'%{component}%'))
        
        result = await query.group_by(Log.level).all()
        
        stats = {
            'time_period_hours': hours,
            'total_logs': 0,
            'level_breakdown': {
                'DEBUG': 0,
                'INFO': 0,
                'WARNING': 0,
                'ERROR': 0,
                'CRITICAL': 0
            },
            'error_rate_percent': 0,
            'component_filter': component
        }
        
        for level, count in result:
            stats['total_logs'] += count
            stats['level_breakdown'][level] = count
        
        # Calculate error rate
        error_count = stats['level_breakdown']['ERROR'] + stats['level_breakdown']['CRITICAL']
        if stats['total_logs'] > 0:
            stats['error_rate_percent'] = round((error_count / stats['total_logs']) * 100, 2)
        
        return stats

    async def get_component_statistics(
        self, 
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get statistics by component.
        
        Args:
            hours: Hours to look back
            
        Returns:
            Dictionary with component statistics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        result = await self.db.query(
            Log.component,
            Log.level,
            func.count(Log.id).label('count')
        ).filter(
            Log.created_at >= cutoff_time
        ).group_by(Log.component, Log.level).all()
        
        stats = {
            'time_period_hours': hours,
            'components': {}
        }
        
        for component, level, count in result:
            if component not in stats['components']:
                stats['components'][component] = {
                    'total_logs': 0,
                    'level_breakdown': {
                        'DEBUG': 0,
                        'INFO': 0,
                        'WARNING': 0,
                        'ERROR': 0,
                        'CRITICAL': 0
                    }
                }
            
            stats['components'][component]['total_logs'] += count
            stats['components'][component]['level_breakdown'][level] = count
        
        return stats

    async def search_logs(
        self, 
        search_term: str,
        level: Optional[str] = None,
        component: Optional[str] = None,
        hours: int = 24,
        limit: int = 100
    ) -> List[Log]:
        """
        Search logs by message content.
        
        Args:
            search_term: Term to search for in log messages
            level: Optional log level filter
            component: Optional component filter
            hours: Hours to look back
            limit: Maximum number of logs to return
            
        Returns:
            List of matching Log objects
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.db.query(Log).filter(
            and_(
                Log.message.like(f'%{search_term}%'),
                Log.created_at >= cutoff_time
            )
        )
        
        if level:
            query = query.filter(Log.level == level.upper())
        
        if component:
            query = query.filter(Log.component.like(f'%{component}%'))
        
        result = await query.order_by(desc(Log.created_at)).limit(limit).all()
        return result

    async def cleanup_old_logs(self, days: int = 7) -> int:
        """
        Clean up old log entries.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of deleted log entries
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.db.query(Log).filter(
            Log.created_at < cutoff_date
        ).delete(synchronize_session=False)
        
        return result

    async def get_recent_errors_summary(
        self, 
        hours: int = 1
    ) -> Dict[str, Any]:
        """
        Get summary of recent errors for alerting.
        
        Args:
            hours: Hours to look back
            
        Returns:
            Dictionary with error summary
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # Get error counts by component
        error_counts = await self.db.query(
            Log.component,
            func.count(Log.id).label('count')
        ).filter(
            and_(
                Log.level.in_(['ERROR', 'CRITICAL']),
                Log.created_at >= cutoff_time
            )
        ).group_by(Log.component).all()
        
        # Get most recent errors
        recent_errors = await self.db.query(Log).filter(
            and_(
                Log.level.in_(['ERROR', 'CRITICAL']),
                Log.created_at >= cutoff_time
            )
        ).order_by(desc(Log.created_at)).limit(10).all()
        
        summary = {
            'time_period_hours': hours,
            'total_errors': sum(count for _, count in error_counts),
            'errors_by_component': {component: count for component, count in error_counts},
            'recent_errors': [
                {
                    'id': str(log.id),
                    'level': log.level,
                    'component': log.component,
                    'message': log.message[:200] + '...' if len(log.message) > 200 else log.message,
                    'created_at': log.created_at.isoformat(),
                    'execution_id': str(log.execution_id) if log.execution_id else None,
                    'session_id': str(log.session_id) if log.session_id else None
                }
                for log in recent_errors
            ]
        }
        
        return summary

    async def get_log_trends(
        self, 
        hours: int = 24,
        interval_hours: int = 1
    ) -> Dict[str, Any]:
        """
        Get log trends over time.
        
        Args:
            hours: Total hours to analyze
            interval_hours: Interval for grouping
            
        Returns:
            Dictionary with trend data
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        # This would require more complex SQL for time-based grouping
        # For now, return basic trend information
        
        # Get hourly error counts
        hourly_errors = []
        for i in range(hours):
            hour_start = datetime.utcnow() - timedelta(hours=i+1)
            hour_end = datetime.utcnow() - timedelta(hours=i)
            
            error_count = await self.db.query(func.count(Log.id)).filter(
                and_(
                    Log.level.in_(['ERROR', 'CRITICAL']),
                    Log.created_at >= hour_start,
                    Log.created_at < hour_end
                )
            ).scalar()
            
            hourly_errors.append({
                'hour': hour_start.strftime('%Y-%m-%d %H:00'),
                'error_count': error_count or 0
            })
        
        # Reverse to get chronological order
        hourly_errors.reverse()
        
        return {
            'time_period_hours': hours,
            'interval_hours': interval_hours,
            'hourly_error_trends': hourly_errors
        }
