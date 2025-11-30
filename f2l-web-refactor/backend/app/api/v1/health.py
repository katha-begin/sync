"""
Health Check API endpoints for monitoring and system status.
"""
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.core.monitoring import get_system_health, health_checker, metrics_collector
from app.core.config_manager import config_manager
from app.core.logging_config import get_logger


logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/", response_model=Dict[str, Any])
async def get_health_status():
    """
    Get comprehensive system health status.
    
    Returns:
        System health information including checks, metrics, and alerts
    """
    try:
        health_status = await get_system_health()
        
        # Set appropriate HTTP status code based on health
        status_code = 200
        if health_status['overall_status'] == 'warning':
            status_code = 200  # Still OK, but with warnings
        elif health_status['overall_status'] == 'unhealthy':
            status_code = 503  # Service Unavailable
        
        return JSONResponse(
            content=health_status,
            status_code=status_code
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            content={
                'overall_status': 'unhealthy',
                'error': str(e),
                'timestamp': '2024-01-01T00:00:00Z'
            },
            status_code=503
        )


@router.get("/live", response_model=Dict[str, str])
async def liveness_probe():
    """
    Kubernetes liveness probe endpoint.
    
    Returns:
        Simple alive status
    """
    return {"status": "alive", "service": "f2l-sync"}


@router.get("/ready", response_model=Dict[str, Any])
async def readiness_probe():
    """
    Kubernetes readiness probe endpoint.
    
    Returns:
        Readiness status with critical checks
    """
    try:
        # Run only critical checks for readiness
        critical_checks = ['database', 'redis']
        results = {}
        
        for check_name in critical_checks:
            result = await health_checker.run_check(check_name)
            results[check_name] = {
                'status': result.status,
                'message': result.message,
                'duration_ms': result.duration_ms
            }
        
        # Determine readiness
        ready = all(result['status'] == 'healthy' for result in results.values())
        
        response_data = {
            'ready': ready,
            'service': 'f2l-sync',
            'checks': results
        }
        
        status_code = 200 if ready else 503
        return JSONResponse(content=response_data, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            content={
                'ready': False,
                'service': 'f2l-sync',
                'error': str(e)
            },
            status_code=503
        )


@router.get("/checks", response_model=Dict[str, Any])
async def get_health_checks():
    """
    Get detailed health check results.
    
    Returns:
        Detailed health check information
    """
    try:
        results = await health_checker.run_all_checks()
        
        return {
            'timestamp': results[list(results.keys())[0]].timestamp.isoformat() if results else None,
            'checks': {
                name: {
                    'status': result.status,
                    'message': result.message,
                    'duration_ms': result.duration_ms,
                    'details': result.details
                }
                for name, result in results.items()
            }
        }
        
    except Exception as e:
        logger.error(f"Health checks failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checks/{check_name}", response_model=Dict[str, Any])
async def get_specific_health_check(check_name: str):
    """
    Get specific health check result.
    
    Args:
        check_name: Name of the health check to run
        
    Returns:
        Specific health check result
    """
    try:
        result = await health_checker.run_check(check_name)
        
        return {
            'name': result.name,
            'status': result.status,
            'message': result.message,
            'duration_ms': result.duration_ms,
            'timestamp': result.timestamp.isoformat(),
            'details': result.details
        }
        
    except Exception as e:
        logger.error(f"Health check {check_name} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics", response_model=Dict[str, Any])
async def get_system_metrics():
    """
    Get current system metrics.
    
    Returns:
        Current system metrics
    """
    try:
        current_metrics = metrics_collector.collect_system_metrics()
        
        return {
            'timestamp': current_metrics.timestamp.isoformat(),
            'cpu_percent': current_metrics.cpu_percent,
            'memory_percent': current_metrics.memory_percent,
            'memory_used_mb': current_metrics.memory_used_mb,
            'memory_available_mb': current_metrics.memory_available_mb,
            'disk_percent': current_metrics.disk_percent,
            'disk_used_gb': current_metrics.disk_used_gb,
            'disk_free_gb': current_metrics.disk_free_gb,
            'load_average': current_metrics.load_average,
            'process_count': current_metrics.process_count,
            'thread_count': current_metrics.thread_count
        }
        
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/summary", response_model=Dict[str, Any])
async def get_metrics_summary(hours: int = 1):
    """
    Get metrics summary for specified time period.
    
    Args:
        hours: Number of hours to look back (default: 1)
        
    Returns:
        Metrics summary
    """
    try:
        if hours < 1 or hours > 24:
            raise HTTPException(status_code=400, detail="Hours must be between 1 and 24")
        
        summary = metrics_collector.get_metrics_summary(hours)
        return summary
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Metrics summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config", response_model=Dict[str, Any])
async def get_configuration_status():
    """
    Get configuration validation status.
    
    Returns:
        Configuration status and validation results
    """
    try:
        # Get configuration summary
        config_summary = config_manager.get_configuration_summary()
        
        # Check environment health
        env_health = config_manager.check_environment_health()
        
        return {
            'configuration': config_summary,
            'environment_health': env_health,
            'timestamp': '2024-01-01T00:00:00Z'  # Will be set by response
        }
        
    except Exception as e:
        logger.error(f"Configuration status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/version", response_model=Dict[str, str])
async def get_version_info():
    """
    Get application version information.
    
    Returns:
        Version and build information
    """
    from app.config import settings
    
    return {
        'app_name': settings.APP_NAME,
        'version': settings.APP_VERSION,
        'environment': settings.APP_ENV,
        'python_version': '3.11+',
        'api_version': 'v1'
    }


@router.post("/checks/run", response_model=Dict[str, Any])
async def run_health_checks():
    """
    Manually trigger all health checks.
    
    Returns:
        Fresh health check results
    """
    try:
        results = await health_checker.run_all_checks()
        
        # Determine overall status
        overall_status = 'healthy'
        for result in results.values():
            if result.status == 'unhealthy':
                overall_status = 'unhealthy'
                break
            elif result.status == 'warning' and overall_status == 'healthy':
                overall_status = 'warning'
        
        return {
            'overall_status': overall_status,
            'timestamp': results[list(results.keys())[0]].timestamp.isoformat() if results else None,
            'checks_run': len(results),
            'results': {
                name: {
                    'status': result.status,
                    'message': result.message,
                    'duration_ms': result.duration_ms,
                    'details': result.details
                }
                for name, result in results.items()
            }
        }
        
    except Exception as e:
        logger.error(f"Manual health check run failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ping", response_model=Dict[str, str])
async def ping():
    """
    Simple ping endpoint for basic connectivity testing.
    
    Returns:
        Pong response
    """
    return {"message": "pong", "service": "f2l-sync"}


@router.get("/status", response_model=Dict[str, Any])
async def get_service_status():
    """
    Get high-level service status.
    
    Returns:
        Service status summary
    """
    try:
        from app.config import settings
        import time
        import psutil
        
        # Get basic system info
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        
        # Run critical checks only
        db_check = await health_checker.run_check('database')
        redis_check = await health_checker.run_check('redis')
        
        # Determine service status
        service_healthy = (
            db_check.status == 'healthy' and 
            redis_check.status == 'healthy'
        )
        
        return {
            'service': settings.APP_NAME,
            'version': settings.APP_VERSION,
            'environment': settings.APP_ENV,
            'status': 'healthy' if service_healthy else 'unhealthy',
            'uptime_seconds': round(uptime_seconds, 2),
            'timestamp': '2024-01-01T00:00:00Z',
            'critical_services': {
                'database': db_check.status,
                'redis': redis_check.status
            }
        }
        
    except Exception as e:
        logger.error(f"Service status check failed: {e}")
        return {
            'service': 'f2l-sync',
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': '2024-01-01T00:00:00Z'
        }
