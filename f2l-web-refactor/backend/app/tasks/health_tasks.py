"""
Health check tasks for monitoring endpoint connectivity and system health.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List
from uuid import UUID

from app.tasks.celery_app import celery_app
from app.repositories.endpoint_repository import EndpointRepository
from app.core.ftp_manager import FTPManager, FTPConfig
from app.core.sftp_manager import SFTPManager, SFTPConfig
from app.core.s3_manager import S3Manager, S3Config
from app.database.models import EndpointType
from app.database.session import async_session_maker

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.health_tasks.check_all_endpoints_health")
def check_all_endpoints_health() -> Dict[str, Any]:
    """
    Check health of all active endpoints.
    
    Returns:
        Dictionary with health check results
    """
    logger.info("Starting health check for all endpoints")
    
    try:
        result = asyncio.run(_check_all_endpoints_health_async())
        return result
        
    except Exception as e:
        logger.error(f"Failed to check endpoints health: {e}")
        return {
            'success': False,
            'message': str(e),
            'endpoints_checked': 0,
            'endpoints_healthy': 0,
            'endpoints_unhealthy': 0
        }


async def _check_all_endpoints_health_async() -> Dict[str, Any]:
    """Async implementation of endpoint health checking."""
    async with async_session_maker() as db:
        try:
            endpoint_repo = EndpointRepository(db)
            
            # Get all active endpoints
            endpoints = await endpoint_repo.get_all(active_only=True, limit=1000)
            
            healthy_count = 0
            unhealthy_count = 0
            health_results = []
            
            # Check each endpoint
            for endpoint in endpoints:
                try:
                    logger.info(f"Checking health of endpoint {endpoint.id} ({endpoint.name})")
                    
                    # Get endpoint with decrypted credentials
                    endpoint_data = await endpoint_repo.get_with_decrypted_password(endpoint.id)
                    
                    if not endpoint_data:
                        logger.warning(f"Could not get credentials for endpoint {endpoint.id}")
                        continue
                    
                    # Perform health check based on endpoint type
                    health_result = await _check_endpoint_health(endpoint_data)
                    
                    # Update endpoint status in database
                    status = "connected" if health_result['success'] else "error"
                    await endpoint_repo.update_connection_status(
                        endpoint.id,
                        status,
                        health_result['message']
                    )
                    
                    if health_result['success']:
                        healthy_count += 1
                    else:
                        unhealthy_count += 1
                    
                    health_results.append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_name': endpoint.name,
                        'endpoint_type': endpoint.endpoint_type.value,
                        'success': health_result['success'],
                        'message': health_result['message'],
                        'response_time_ms': health_result.get('response_time_ms', 0)
                    })
                    
                except Exception as e:
                    logger.error(f"Health check failed for endpoint {endpoint.id}: {e}")
                    unhealthy_count += 1
                    
                    # Update endpoint status to error
                    await endpoint_repo.update_connection_status(
                        endpoint.id,
                        "error",
                        f"Health check failed: {str(e)}"
                    )
                    
                    health_results.append({
                        'endpoint_id': str(endpoint.id),
                        'endpoint_name': endpoint.name,
                        'endpoint_type': endpoint.endpoint_type.value,
                        'success': False,
                        'message': f"Health check failed: {str(e)}",
                        'response_time_ms': 0
                    })
            
            await db.commit()
            
            logger.info(f"Health check completed: {healthy_count} healthy, {unhealthy_count} unhealthy")
            
            return {
                'success': True,
                'endpoints_checked': len(endpoints),
                'endpoints_healthy': healthy_count,
                'endpoints_unhealthy': unhealthy_count,
                'health_results': health_results,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            raise


async def _check_endpoint_health(endpoint_data: dict) -> Dict[str, Any]:
    """Check health of a specific endpoint."""
    start_time = datetime.now()
    
    try:
        endpoint_type = endpoint_data['endpoint_type']
        
        if endpoint_type == EndpointType.FTP:
            result = await _check_ftp_health(endpoint_data)
        elif endpoint_type == EndpointType.SFTP:
            result = await _check_sftp_health(endpoint_data)
        elif endpoint_type == EndpointType.S3:
            result = await _check_s3_health(endpoint_data)
        elif endpoint_type == EndpointType.LOCAL:
            result = await _check_local_health(endpoint_data)
        else:
            result = {
                'success': False,
                'message': f"Unsupported endpoint type: {endpoint_type}"
            }
        
        # Calculate response time
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        result['response_time_ms'] = int(response_time)
        
        return result
        
    except Exception as e:
        response_time = (datetime.now() - start_time).total_seconds() * 1000
        return {
            'success': False,
            'message': f"Health check error: {str(e)}",
            'response_time_ms': int(response_time)
        }


async def _check_ftp_health(endpoint_data: dict) -> Dict[str, Any]:
    """Check FTP endpoint health."""
    try:
        config = FTPConfig(
            host=endpoint_data['host'],
            username=endpoint_data['username'],
            password=endpoint_data.get('password', ''),
            port=endpoint_data.get('port', 21)
        )
        
        manager = FTPManager(config)
        
        # Test connection
        if manager.connect():
            # Test basic operations
            health_result = manager.health_check()
            manager.close()
            return health_result
        else:
            return {
                'success': False,
                'message': 'Failed to establish FTP connection'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'FTP health check failed: {str(e)}'
        }


async def _check_sftp_health(endpoint_data: dict) -> Dict[str, Any]:
    """Check SFTP endpoint health."""
    try:
        config = SFTPConfig(
            host=endpoint_data['host'],
            username=endpoint_data['username'],
            password=endpoint_data.get('password', ''),
            port=endpoint_data.get('port', 22)
        )
        
        manager = SFTPManager(config)
        
        # Test connection
        if manager.connect():
            # Test basic operations
            health_result = manager.health_check()
            manager.close()
            return health_result
        else:
            return {
                'success': False,
                'message': 'Failed to establish SFTP connection'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'SFTP health check failed: {str(e)}'
        }


async def _check_s3_health(endpoint_data: dict) -> Dict[str, Any]:
    """Check S3 endpoint health."""
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
            'success': result['success'],
            'message': result['message']
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f'S3 health check failed: {str(e)}'
        }


async def _check_local_health(endpoint_data: dict) -> Dict[str, Any]:
    """Check local endpoint health."""
    import os
    
    try:
        local_path = endpoint_data.get('local_path')
        if not local_path:
            return {
                'success': False,
                'message': 'Local path not specified'
            }
        
        if os.path.exists(local_path) and os.path.isdir(local_path):
            # Test read/write permissions
            test_file = os.path.join(local_path, '.f2l_health_check')
            try:
                with open(test_file, 'w') as f:
                    f.write('health_check')
                os.remove(test_file)
                
                return {
                    'success': True,
                    'message': 'Local path accessible with read/write permissions'
                }
            except:
                return {
                    'success': False,
                    'message': 'Local path exists but no write permissions'
                }
        else:
            return {
                'success': False,
                'message': 'Local path does not exist or is not a directory'
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'Local health check failed: {str(e)}'
        }


@celery_app.task(name="app.tasks.health_tasks.check_endpoint_health")
def check_endpoint_health(endpoint_id: str) -> Dict[str, Any]:
    """
    Check health of a specific endpoint.
    
    Args:
        endpoint_id: UUID of the endpoint to check
        
    Returns:
        Dictionary with health check result
    """
    logger.info(f"Checking health of endpoint {endpoint_id}")
    
    try:
        result = asyncio.run(_check_single_endpoint_health_async(UUID(endpoint_id)))
        return result
        
    except Exception as e:
        logger.error(f"Failed to check endpoint {endpoint_id} health: {e}")
        return {
            'success': False,
            'message': str(e),
            'endpoint_id': endpoint_id
        }


async def _check_single_endpoint_health_async(endpoint_id: UUID) -> Dict[str, Any]:
    """Async implementation of single endpoint health check."""
    async with async_session_maker() as db:
        try:
            endpoint_repo = EndpointRepository(db)
            
            # Get endpoint with decrypted credentials
            endpoint_data = await endpoint_repo.get_with_decrypted_password(endpoint_id)
            
            if not endpoint_data:
                return {
                    'success': False,
                    'message': 'Endpoint not found',
                    'endpoint_id': str(endpoint_id)
                }
            
            # Perform health check
            health_result = await _check_endpoint_health(endpoint_data)
            
            # Update endpoint status in database
            status = "connected" if health_result['success'] else "error"
            await endpoint_repo.update_connection_status(
                endpoint_id,
                status,
                health_result['message']
            )
            
            await db.commit()
            
            return {
                'success': health_result['success'],
                'message': health_result['message'],
                'endpoint_id': str(endpoint_id),
                'endpoint_name': endpoint_data['name'],
                'endpoint_type': endpoint_data['endpoint_type'].value,
                'response_time_ms': health_result.get('response_time_ms', 0),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error checking endpoint {endpoint_id} health: {e}")
            raise


@celery_app.task(name="app.tasks.health_tasks.get_system_health")
def get_system_health() -> Dict[str, Any]:
    """
    Get overall system health status.
    
    Returns:
        Dictionary with system health information
    """
    try:
        result = asyncio.run(_get_system_health_async())
        return result
        
    except Exception as e:
        logger.error(f"Failed to get system health: {e}")
        return {
            'success': False,
            'message': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


async def _get_system_health_async() -> Dict[str, Any]:
    """Async implementation of system health check."""
    async with async_session_maker() as db:
        try:
            endpoint_repo = EndpointRepository(db)
            
            # Get endpoint health summary
            health_summary = await endpoint_repo.get_health_status_summary()
            
            # Get endpoint counts by type
            type_counts = await endpoint_repo.count_by_type()
            
            # Calculate health percentage
            total_endpoints = sum(health_summary.values())
            healthy_endpoints = health_summary.get('connected', 0)
            health_percentage = (healthy_endpoints / total_endpoints * 100) if total_endpoints > 0 else 100
            
            # Determine overall system status
            if health_percentage >= 90:
                system_status = 'healthy'
            elif health_percentage >= 70:
                system_status = 'degraded'
            else:
                system_status = 'unhealthy'
            
            return {
                'success': True,
                'system_status': system_status,
                'health_percentage': round(health_percentage, 2),
                'endpoint_summary': {
                    'total_endpoints': total_endpoints,
                    'healthy_endpoints': healthy_endpoints,
                    'unhealthy_endpoints': total_endpoints - healthy_endpoints,
                    'health_status_breakdown': health_summary,
                    'endpoint_type_breakdown': type_counts
                },
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            raise
