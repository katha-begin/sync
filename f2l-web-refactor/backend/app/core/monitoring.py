"""
Monitoring System - Health checks, metrics collection, and system monitoring.
"""
import time
import psutil
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import settings
from app.core.logging_config import get_logger
from app.database.session import async_session_maker


logger = get_logger(__name__)


@dataclass
class HealthCheckResult:
    """Health check result data class."""
    name: str
    status: str  # 'healthy', 'warning', 'unhealthy'
    message: str
    duration_ms: float
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None


@dataclass
class SystemMetrics:
    """System metrics data class."""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_percent: float
    disk_used_gb: float
    disk_free_gb: float
    load_average: List[float]
    process_count: int
    thread_count: int


class HealthChecker:
    """System health checker."""

    def __init__(self):
        """Initialize health checker."""
        self.checks = {}
        self.register_default_checks()

    def register_default_checks(self):
        """Register default health checks."""
        self.register_check('database', self._check_database)
        self.register_check('redis', self._check_redis)
        self.register_check('disk_space', self._check_disk_space)
        self.register_check('memory', self._check_memory)
        self.register_check('temp_directory', self._check_temp_directory)

    def register_check(self, name: str, check_func):
        """
        Register a health check function.
        
        Args:
            name: Check name
            check_func: Async function that returns HealthCheckResult
        """
        self.checks[name] = check_func

    async def run_check(self, name: str) -> HealthCheckResult:
        """
        Run a specific health check.
        
        Args:
            name: Check name
            
        Returns:
            HealthCheckResult
        """
        if name not in self.checks:
            return HealthCheckResult(
                name=name,
                status='unhealthy',
                message=f'Unknown health check: {name}',
                duration_ms=0,
                timestamp=datetime.utcnow()
            )

        start_time = time.time()
        try:
            result = await self.checks[name]()
            result.duration_ms = (time.time() - start_time) * 1000
            result.timestamp = datetime.utcnow()
            return result
        except Exception as e:
            logger.error(f"Health check {name} failed: {e}")
            return HealthCheckResult(
                name=name,
                status='unhealthy',
                message=f'Health check failed: {str(e)}',
                duration_ms=(time.time() - start_time) * 1000,
                timestamp=datetime.utcnow()
            )

    async def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """
        Run all registered health checks.
        
        Returns:
            Dictionary of check results
        """
        results = {}
        
        # Run checks concurrently
        tasks = []
        for name in self.checks.keys():
            tasks.append(self.run_check(name))
        
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, name in enumerate(self.checks.keys()):
            result = check_results[i]
            if isinstance(result, Exception):
                results[name] = HealthCheckResult(
                    name=name,
                    status='unhealthy',
                    message=f'Check failed with exception: {str(result)}',
                    duration_ms=0,
                    timestamp=datetime.utcnow()
                )
            else:
                results[name] = result
        
        return results

    async def _check_database(self) -> HealthCheckResult:
        """Check database connectivity."""
        try:
            async with async_session_maker() as session:
                result = await session.execute(text("SELECT 1"))
                await result.fetchone()
                
                return HealthCheckResult(
                    name='database',
                    status='healthy',
                    message='Database connection successful',
                    duration_ms=0  # Will be set by run_check
                )
        except Exception as e:
            return HealthCheckResult(
                name='database',
                status='unhealthy',
                message=f'Database connection failed: {str(e)}',
                duration_ms=0
            )

    async def _check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity."""
        try:
            import redis.asyncio as redis
            
            redis_client = redis.from_url(settings.REDIS_URL)
            await redis_client.ping()
            await redis_client.close()
            
            return HealthCheckResult(
                name='redis',
                status='healthy',
                message='Redis connection successful',
                duration_ms=0
            )
        except Exception as e:
            return HealthCheckResult(
                name='redis',
                status='unhealthy',
                message=f'Redis connection failed: {str(e)}',
                duration_ms=0
            )

    async def _check_disk_space(self) -> HealthCheckResult:
        """Check disk space availability."""
        try:
            disk_usage = psutil.disk_usage('/')
            free_percent = (disk_usage.free / disk_usage.total) * 100
            
            if free_percent < 5:
                status = 'unhealthy'
                message = f'Critical: Only {free_percent:.1f}% disk space remaining'
            elif free_percent < 15:
                status = 'warning'
                message = f'Warning: Only {free_percent:.1f}% disk space remaining'
            else:
                status = 'healthy'
                message = f'Disk space OK: {free_percent:.1f}% free'
            
            return HealthCheckResult(
                name='disk_space',
                status=status,
                message=message,
                duration_ms=0,
                details={
                    'total_gb': round(disk_usage.total / (1024**3), 2),
                    'used_gb': round(disk_usage.used / (1024**3), 2),
                    'free_gb': round(disk_usage.free / (1024**3), 2),
                    'free_percent': round(free_percent, 2)
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name='disk_space',
                status='unhealthy',
                message=f'Disk space check failed: {str(e)}',
                duration_ms=0
            )

    async def _check_memory(self) -> HealthCheckResult:
        """Check memory usage."""
        try:
            memory = psutil.virtual_memory()
            
            if memory.percent > 90:
                status = 'unhealthy'
                message = f'Critical: {memory.percent:.1f}% memory usage'
            elif memory.percent > 80:
                status = 'warning'
                message = f'Warning: {memory.percent:.1f}% memory usage'
            else:
                status = 'healthy'
                message = f'Memory usage OK: {memory.percent:.1f}%'
            
            return HealthCheckResult(
                name='memory',
                status=status,
                message=message,
                duration_ms=0,
                details={
                    'total_mb': round(memory.total / (1024**2), 2),
                    'used_mb': round(memory.used / (1024**2), 2),
                    'available_mb': round(memory.available / (1024**2), 2),
                    'percent': round(memory.percent, 2)
                }
            )
        except Exception as e:
            return HealthCheckResult(
                name='memory',
                status='unhealthy',
                message=f'Memory check failed: {str(e)}',
                duration_ms=0
            )

    async def _check_temp_directory(self) -> HealthCheckResult:
        """Check temporary directory accessibility."""
        try:
            import tempfile
            import os
            from pathlib import Path
            
            temp_dir = Path(settings.TEMP_DIR)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            # Test write access
            with tempfile.NamedTemporaryFile(dir=temp_dir, delete=True) as f:
                f.write(b'health check test')
                f.flush()
            
            return HealthCheckResult(
                name='temp_directory',
                status='healthy',
                message=f'Temp directory accessible: {settings.TEMP_DIR}',
                duration_ms=0
            )
        except Exception as e:
            return HealthCheckResult(
                name='temp_directory',
                status='unhealthy',
                message=f'Temp directory check failed: {str(e)}',
                duration_ms=0
            )


class MetricsCollector:
    """System metrics collector."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics_history = []
        self.max_history_size = 1000

    def collect_system_metrics(self) -> SystemMetrics:
        """
        Collect current system metrics.
        
        Returns:
            SystemMetrics object
        """
        try:
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            
            # Load average (Unix-like systems)
            try:
                load_avg = list(psutil.getloadavg())
            except AttributeError:
                # Windows doesn't have load average
                load_avg = [0.0, 0.0, 0.0]
            
            # Process metrics
            process_count = len(psutil.pids())
            
            # Thread count for current process
            current_process = psutil.Process()
            thread_count = current_process.num_threads()
            
            metrics = SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_percent=round(cpu_percent, 2),
                memory_percent=round(memory.percent, 2),
                memory_used_mb=round(memory.used / (1024**2), 2),
                memory_available_mb=round(memory.available / (1024**2), 2),
                disk_percent=round((disk.used / disk.total) * 100, 2),
                disk_used_gb=round(disk.used / (1024**3), 2),
                disk_free_gb=round(disk.free / (1024**3), 2),
                load_average=[round(x, 2) for x in load_avg],
                process_count=process_count,
                thread_count=thread_count
            )
            
            # Store in history
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history.pop(0)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            raise

    def get_metrics_history(self, hours: int = 1) -> List[SystemMetrics]:
        """
        Get metrics history for specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            List of SystemMetrics
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]

    def get_metrics_summary(self, hours: int = 1) -> Dict[str, Any]:
        """
        Get summary of metrics for specified time period.
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with metrics summary
        """
        history = self.get_metrics_history(hours)
        
        if not history:
            return {'error': 'No metrics data available'}
        
        # Calculate averages and peaks
        cpu_values = [m.cpu_percent for m in history]
        memory_values = [m.memory_percent for m in history]
        disk_values = [m.disk_percent for m in history]
        
        return {
            'time_period_hours': hours,
            'data_points': len(history),
            'cpu': {
                'average_percent': round(sum(cpu_values) / len(cpu_values), 2),
                'peak_percent': max(cpu_values),
                'current_percent': cpu_values[-1] if cpu_values else 0
            },
            'memory': {
                'average_percent': round(sum(memory_values) / len(memory_values), 2),
                'peak_percent': max(memory_values),
                'current_percent': memory_values[-1] if memory_values else 0,
                'current_used_mb': history[-1].memory_used_mb if history else 0,
                'current_available_mb': history[-1].memory_available_mb if history else 0
            },
            'disk': {
                'average_percent': round(sum(disk_values) / len(disk_values), 2),
                'peak_percent': max(disk_values),
                'current_percent': disk_values[-1] if disk_values else 0,
                'current_used_gb': history[-1].disk_used_gb if history else 0,
                'current_free_gb': history[-1].disk_free_gb if history else 0
            },
            'process': {
                'current_count': history[-1].process_count if history else 0,
                'current_threads': history[-1].thread_count if history else 0
            },
            'load_average': history[-1].load_average if history else [0, 0, 0]
        }


class AlertManager:
    """Alert management for monitoring thresholds."""

    def __init__(self):
        """Initialize alert manager."""
        self.alert_thresholds = {
            'cpu_percent': {'warning': 80, 'critical': 95},
            'memory_percent': {'warning': 80, 'critical': 90},
            'disk_percent': {'warning': 85, 'critical': 95},
            'response_time_ms': {'warning': 1000, 'critical': 5000}
        }
        self.active_alerts = {}

    def check_thresholds(self, metrics: SystemMetrics) -> List[Dict[str, Any]]:
        """
        Check metrics against alert thresholds.
        
        Args:
            metrics: SystemMetrics to check
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        # Check CPU
        cpu_alert = self._check_threshold('cpu_percent', metrics.cpu_percent)
        if cpu_alert:
            alerts.append(cpu_alert)
        
        # Check Memory
        memory_alert = self._check_threshold('memory_percent', metrics.memory_percent)
        if memory_alert:
            alerts.append(memory_alert)
        
        # Check Disk
        disk_alert = self._check_threshold('disk_percent', metrics.disk_percent)
        if disk_alert:
            alerts.append(disk_alert)
        
        return alerts

    def _check_threshold(self, metric_name: str, value: float) -> Optional[Dict[str, Any]]:
        """Check individual metric threshold."""
        thresholds = self.alert_thresholds.get(metric_name)
        if not thresholds:
            return None
        
        alert_level = None
        if value >= thresholds['critical']:
            alert_level = 'critical'
        elif value >= thresholds['warning']:
            alert_level = 'warning'
        
        if alert_level:
            alert_key = f"{metric_name}_{alert_level}"
            
            # Check if this alert is already active
            if alert_key in self.active_alerts:
                return None  # Don't spam alerts
            
            # Mark alert as active
            self.active_alerts[alert_key] = datetime.utcnow()
            
            return {
                'metric': metric_name,
                'level': alert_level,
                'value': value,
                'threshold': thresholds[alert_level],
                'message': f"{metric_name} is {alert_level}: {value}% (threshold: {thresholds[alert_level]}%)",
                'timestamp': datetime.utcnow().isoformat()
            }
        else:
            # Clear any active alerts for this metric
            for level in ['warning', 'critical']:
                alert_key = f"{metric_name}_{level}"
                if alert_key in self.active_alerts:
                    del self.active_alerts[alert_key]
        
        return None


# Global instances
health_checker = HealthChecker()
metrics_collector = MetricsCollector()
alert_manager = AlertManager()


async def get_system_health() -> Dict[str, Any]:
    """
    Get comprehensive system health status.
    
    Returns:
        Dictionary with health status
    """
    # Run health checks
    health_results = await health_checker.run_all_checks()
    
    # Collect current metrics
    current_metrics = metrics_collector.collect_system_metrics()
    
    # Check for alerts
    alerts = alert_manager.check_thresholds(current_metrics)
    
    # Determine overall status
    overall_status = 'healthy'
    for result in health_results.values():
        if result.status == 'unhealthy':
            overall_status = 'unhealthy'
            break
        elif result.status == 'warning' and overall_status == 'healthy':
            overall_status = 'warning'
    
    return {
        'overall_status': overall_status,
        'timestamp': datetime.utcnow().isoformat(),
        'health_checks': {name: asdict(result) for name, result in health_results.items()},
        'system_metrics': asdict(current_metrics),
        'active_alerts': alerts,
        'uptime_seconds': time.time() - psutil.boot_time()
    }
