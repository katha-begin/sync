"""
Maintenance tasks for system cleanup and optimization.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List
import os
import shutil

from app.tasks.celery_app import celery_app
from app.repositories.execution_repository import ExecutionRepository
from app.repositories.endpoint_repository import EndpointRepository
from app.database.models import ScanCache, Log
from app.database.session import async_session_maker
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_old_executions")
def cleanup_old_executions(days: int = 30) -> Dict[str, Any]:
    """
    Clean up old execution records and associated data.
    
    Args:
        days: Number of days to keep (default: 30)
        
    Returns:
        Dictionary with cleanup results
    """
    logger.info(f"Starting cleanup of executions older than {days} days")
    
    try:
        result = asyncio.run(_cleanup_old_executions_async(days))
        return result
        
    except Exception as e:
        logger.error(f"Failed to cleanup old executions: {e}")
        return {
            'success': False,
            'message': str(e),
            'executions_deleted': 0,
            'operations_deleted': 0
        }


async def _cleanup_old_executions_async(days: int) -> Dict[str, Any]:
    """Async implementation of execution cleanup."""
    async with async_session_maker() as db:
        try:
            execution_repo = ExecutionRepository(db)
            
            # Clean up old executions (this will cascade delete operations)
            deleted_count = await execution_repo.cleanup_old_executions(days)
            
            await db.commit()
            
            logger.info(f"Cleaned up {deleted_count} old executions")
            
            return {
                'success': True,
                'executions_deleted': deleted_count,
                'cutoff_date': (datetime.utcnow() - timedelta(days=days)).isoformat(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in execution cleanup: {e}")
            await db.rollback()
            raise


@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_old_logs")
def cleanup_old_logs(days: int = 7) -> Dict[str, Any]:
    """
    Clean up old log entries.
    
    Args:
        days: Number of days to keep (default: 7)
        
    Returns:
        Dictionary with cleanup results
    """
    logger.info(f"Starting cleanup of logs older than {days} days")
    
    try:
        result = asyncio.run(_cleanup_old_logs_async(days))
        return result
        
    except Exception as e:
        logger.error(f"Failed to cleanup old logs: {e}")
        return {
            'success': False,
            'message': str(e),
            'logs_deleted': 0
        }


async def _cleanup_old_logs_async(days: int) -> Dict[str, Any]:
    """Async implementation of log cleanup."""
    async with async_session_maker() as db:
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old log entries
            result = await db.query(Log).filter(
                Log.created_at < cutoff_date
            ).delete(synchronize_session=False)
            
            await db.commit()
            
            logger.info(f"Cleaned up {result} old log entries")
            
            return {
                'success': True,
                'logs_deleted': result,
                'cutoff_date': cutoff_date.isoformat(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in log cleanup: {e}")
            await db.rollback()
            raise


@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_scan_cache")
def cleanup_scan_cache(hours: int = 24) -> Dict[str, Any]:
    """
    Clean up expired scan cache entries.
    
    Args:
        hours: Cache expiry time in hours (default: 24)
        
    Returns:
        Dictionary with cleanup results
    """
    logger.info(f"Starting cleanup of scan cache older than {hours} hours")
    
    try:
        result = asyncio.run(_cleanup_scan_cache_async(hours))
        return result
        
    except Exception as e:
        logger.error(f"Failed to cleanup scan cache: {e}")
        return {
            'success': False,
            'message': str(e),
            'cache_entries_deleted': 0
        }


async def _cleanup_scan_cache_async(hours: int) -> Dict[str, Any]:
    """Async implementation of scan cache cleanup."""
    async with async_session_maker() as db:
        try:
            cutoff_date = datetime.utcnow() - timedelta(hours=hours)
            
            # Delete expired cache entries
            result = await db.query(ScanCache).filter(
                ScanCache.created_at < cutoff_date
            ).delete(synchronize_session=False)
            
            await db.commit()
            
            logger.info(f"Cleaned up {result} expired scan cache entries")
            
            return {
                'success': True,
                'cache_entries_deleted': result,
                'cutoff_date': cutoff_date.isoformat(),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in scan cache cleanup: {e}")
            await db.rollback()
            raise


@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_temp_files")
def cleanup_temp_files() -> Dict[str, Any]:
    """
    Clean up temporary files created during sync operations.
    
    Returns:
        Dictionary with cleanup results
    """
    logger.info("Starting cleanup of temporary files")
    
    try:
        temp_dir = getattr(settings, 'TEMP_DIR', '/tmp/f2l_sync')
        
        if not os.path.exists(temp_dir):
            return {
                'success': True,
                'message': 'Temp directory does not exist',
                'files_deleted': 0,
                'bytes_freed': 0
            }
        
        files_deleted = 0
        bytes_freed = 0
        
        # Clean up files older than 1 hour
        cutoff_time = datetime.now().timestamp() - 3600
        
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if os.path.getmtime(file_path) < cutoff_time:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        files_deleted += 1
                        bytes_freed += file_size
                        logger.debug(f"Deleted temp file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {file_path}: {e}")
        
        # Clean up empty directories
        for root, dirs, files in os.walk(temp_dir, topdown=False):
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    if not os.listdir(dir_path):  # Directory is empty
                        os.rmdir(dir_path)
                        logger.debug(f"Deleted empty temp directory: {dir_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete temp directory {dir_path}: {e}")
        
        logger.info(f"Cleaned up {files_deleted} temp files, freed {bytes_freed} bytes")
        
        return {
            'success': True,
            'files_deleted': files_deleted,
            'bytes_freed': bytes_freed,
            'temp_directory': temp_dir,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup temp files: {e}")
        return {
            'success': False,
            'message': str(e),
            'files_deleted': 0,
            'bytes_freed': 0
        }


@celery_app.task(name="app.tasks.maintenance_tasks.optimize_database")
def optimize_database() -> Dict[str, Any]:
    """
    Optimize database performance by running maintenance queries.
    
    Returns:
        Dictionary with optimization results
    """
    logger.info("Starting database optimization")
    
    try:
        result = asyncio.run(_optimize_database_async())
        return result
        
    except Exception as e:
        logger.error(f"Failed to optimize database: {e}")
        return {
            'success': False,
            'message': str(e)
        }


async def _optimize_database_async() -> Dict[str, Any]:
    """Async implementation of database optimization."""
    async with async_session_maker() as db:
        try:
            # PostgreSQL-specific optimization queries
            optimization_queries = [
                "VACUUM ANALYZE sync_executions;",
                "VACUUM ANALYZE sync_operations;",
                "VACUUM ANALYZE scan_cache;",
                "VACUUM ANALYZE logs;",
                "REINDEX INDEX CONCURRENTLY idx_sync_executions_session_id;",
                "REINDEX INDEX CONCURRENTLY idx_sync_operations_execution_id;",
            ]
            
            executed_queries = []
            
            for query in optimization_queries:
                try:
                    await db.execute(query)
                    executed_queries.append(query)
                    logger.debug(f"Executed optimization query: {query}")
                except Exception as e:
                    logger.warning(f"Failed to execute optimization query '{query}': {e}")
            
            await db.commit()
            
            logger.info(f"Database optimization completed, executed {len(executed_queries)} queries")
            
            return {
                'success': True,
                'queries_executed': len(executed_queries),
                'executed_queries': executed_queries,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in database optimization: {e}")
            await db.rollback()
            raise


@celery_app.task(name="app.tasks.maintenance_tasks.generate_system_report")
def generate_system_report() -> Dict[str, Any]:
    """
    Generate comprehensive system health and usage report.
    
    Returns:
        Dictionary with system report
    """
    logger.info("Generating system report")
    
    try:
        result = asyncio.run(_generate_system_report_async())
        return result
        
    except Exception as e:
        logger.error(f"Failed to generate system report: {e}")
        return {
            'success': False,
            'message': str(e)
        }


async def _generate_system_report_async() -> Dict[str, Any]:
    """Async implementation of system report generation."""
    async with async_session_maker() as db:
        try:
            endpoint_repo = EndpointRepository(db)
            execution_repo = ExecutionRepository(db)
            
            # Get endpoint statistics
            endpoint_counts = await endpoint_repo.count_by_type()
            health_summary = await endpoint_repo.get_health_status_summary()
            
            # Get execution statistics
            recent_executions = await execution_repo.get_recent_executions(hours=24, limit=100)
            active_executions = await execution_repo.get_active_executions_count()
            
            # Calculate success rate for recent executions
            successful_executions = sum(1 for exec in recent_executions if exec.status.value == 'completed')
            success_rate = (successful_executions / len(recent_executions) * 100) if recent_executions else 100
            
            # Get duration statistics
            duration_stats = await execution_repo.get_execution_duration_stats()
            
            # System resource usage (basic)
            import psutil
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            report = {
                'success': True,
                'report_timestamp': datetime.now(timezone.utc).isoformat(),
                'system_overview': {
                    'total_endpoints': sum(endpoint_counts.values()),
                    'endpoint_types': endpoint_counts,
                    'endpoint_health': health_summary,
                    'active_executions': active_executions
                },
                'execution_statistics': {
                    'recent_executions_24h': len(recent_executions),
                    'success_rate_percent': round(success_rate, 2),
                    'average_duration_seconds': duration_stats['average_duration_seconds'],
                    'min_duration_seconds': duration_stats['minimum_duration_seconds'],
                    'max_duration_seconds': duration_stats['maximum_duration_seconds']
                },
                'system_resources': {
                    'cpu_usage_percent': cpu_percent,
                    'memory_usage_percent': memory.percent,
                    'memory_available_gb': round(memory.available / (1024**3), 2),
                    'disk_usage_percent': round(disk.used / disk.total * 100, 2),
                    'disk_free_gb': round(disk.free / (1024**3), 2)
                }
            }
            
            logger.info("System report generated successfully")
            return report
            
        except Exception as e:
            logger.error(f"Error generating system report: {e}")
            raise


@celery_app.task(name="app.tasks.maintenance_tasks.backup_configuration")
def backup_configuration() -> Dict[str, Any]:
    """
    Backup system configuration and critical data.
    
    Returns:
        Dictionary with backup results
    """
    logger.info("Starting configuration backup")
    
    try:
        result = asyncio.run(_backup_configuration_async())
        return result
        
    except Exception as e:
        logger.error(f"Failed to backup configuration: {e}")
        return {
            'success': False,
            'message': str(e)
        }


async def _backup_configuration_async() -> Dict[str, Any]:
    """Async implementation of configuration backup."""
    async with async_session_maker() as db:
        try:
            # Create backup directory
            backup_dir = f"/tmp/f2l_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.makedirs(backup_dir, exist_ok=True)
            
            # Export endpoints (without passwords)
            endpoint_repo = EndpointRepository(db)
            endpoints = await endpoint_repo.get_all(active_only=False, limit=1000)
            
            endpoint_backup = []
            for endpoint in endpoints:
                endpoint_data = {
                    'name': endpoint.name,
                    'endpoint_type': endpoint.endpoint_type.value,
                    'host': endpoint.host,
                    'port': endpoint.port,
                    'username': endpoint.username,
                    'remote_path': endpoint.remote_path,
                    'local_path': endpoint.local_path,
                    's3_bucket': endpoint.s3_bucket,
                    's3_region': endpoint.s3_region,
                    's3_access_key': endpoint.s3_access_key,
                    'notes': endpoint.notes,
                    'is_active': endpoint.is_active
                }
                endpoint_backup.append(endpoint_data)
            
            # Save backup files
            import json
            
            with open(os.path.join(backup_dir, 'endpoints.json'), 'w') as f:
                json.dump(endpoint_backup, f, indent=2, default=str)
            
            # Create archive
            archive_path = f"{backup_dir}.tar.gz"
            shutil.make_archive(backup_dir, 'gztar', backup_dir)
            
            # Clean up temp directory
            shutil.rmtree(backup_dir)
            
            backup_size = os.path.getsize(archive_path)
            
            logger.info(f"Configuration backup created: {archive_path} ({backup_size} bytes)")
            
            return {
                'success': True,
                'backup_path': archive_path,
                'backup_size_bytes': backup_size,
                'endpoints_backed_up': len(endpoint_backup),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in configuration backup: {e}")
            raise
