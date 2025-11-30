"""
Unit tests for Celery Tasks.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.tasks.sync_tasks import execute_sync_task, scheduled_sync_task
from app.tasks.health_tasks import health_check_task, endpoint_health_check_task
from app.tasks.maintenance_tasks import cleanup_old_executions_task, cache_cleanup_task


@pytest.mark.unit
class TestSyncTasks:
    """Test cases for sync tasks."""

    @pytest.fixture
    def sample_session_config(self):
        """Sample session configuration."""
        return {
            'id': str(uuid4()),
            'name': 'Test Session',
            'source_endpoint_id': str(uuid4()),
            'destination_endpoint_id': str(uuid4()),
            'source_path': '/source/path',
            'destination_path': '/dest/path',
            'sync_direction': 'source_to_destination'
        }

    @pytest.fixture
    def sample_endpoint_configs(self):
        """Sample endpoint configurations."""
        return {
            'source': {
                'id': str(uuid4()),
                'endpoint_type': 'ftp',
                'host': 'ftp.example.com',
                'port': 21,
                'username': 'testuser',
                'password': 'testpass'
            },
            'destination': {
                'id': str(uuid4()),
                'endpoint_type': 'local',
                'base_path': '/local/path'
            }
        }

    def test_execute_sync_task_success(self, sample_session_config, sample_endpoint_configs):
        """Test successful sync task execution."""
        execution_id = str(uuid4())
        
        with patch('app.tasks.sync_tasks.SyncEngine') as mock_sync_engine:
            mock_engine = AsyncMock()
            mock_sync_engine.return_value = mock_engine
            
            # Mock successful execution
            mock_result = {
                'status': 'completed',
                'files_transferred': 10,
                'bytes_transferred': 1024000,
                'operations': []
            }
            mock_engine.execute_session.return_value = mock_result
            
            with patch('app.tasks.sync_tasks.get_database_session') as mock_get_session:
                mock_session = AsyncMock()
                mock_get_session.return_value.__aenter__.return_value = mock_session
                
                with patch('app.tasks.sync_tasks.ExecutionRepository') as mock_repo:
                    mock_execution_repo = AsyncMock()
                    mock_repo.return_value = mock_execution_repo
                    
                    result = execute_sync_task(
                        execution_id=execution_id,
                        session_config=sample_session_config,
                        source_endpoint_config=sample_endpoint_configs['source'],
                        destination_endpoint_config=sample_endpoint_configs['destination']
                    )
                    
                    assert result['status'] == 'completed'
                    mock_engine.execute_session.assert_called_once()
                    mock_execution_repo.update_status.assert_called()

    def test_execute_sync_task_failure(self, sample_session_config, sample_endpoint_configs):
        """Test sync task execution failure."""
        execution_id = str(uuid4())
        
        with patch('app.tasks.sync_tasks.SyncEngine') as mock_sync_engine:
            mock_engine = AsyncMock()
            mock_sync_engine.return_value = mock_engine
            
            # Mock execution failure
            mock_engine.execute_session.side_effect = Exception("Sync failed")
            
            with patch('app.tasks.sync_tasks.get_database_session') as mock_get_session:
                mock_session = AsyncMock()
                mock_get_session.return_value.__aenter__.return_value = mock_session
                
                with patch('app.tasks.sync_tasks.ExecutionRepository') as mock_repo:
                    mock_execution_repo = AsyncMock()
                    mock_repo.return_value = mock_execution_repo
                    
                    result = execute_sync_task(
                        execution_id=execution_id,
                        session_config=sample_session_config,
                        source_endpoint_config=sample_endpoint_configs['source'],
                        destination_endpoint_config=sample_endpoint_configs['destination']
                    )
                    
                    assert result['status'] == 'failed'
                    assert 'Sync failed' in result['error_message']
                    mock_execution_repo.update_status.assert_called_with(
                        execution_id, 'failed', error_message='Sync failed'
                    )

    def test_execute_sync_task_dry_run(self, sample_session_config, sample_endpoint_configs):
        """Test sync task execution in dry run mode."""
        execution_id = str(uuid4())
        
        with patch('app.tasks.sync_tasks.SyncEngine') as mock_sync_engine:
            mock_engine = AsyncMock()
            mock_sync_engine.return_value = mock_engine
            
            mock_result = {
                'status': 'completed',
                'dry_run': True,
                'operations_planned': 5,
                'operations': []
            }
            mock_engine.execute_session.return_value = mock_result
            
            with patch('app.tasks.sync_tasks.get_database_session') as mock_get_session:
                mock_session = AsyncMock()
                mock_get_session.return_value.__aenter__.return_value = mock_session
                
                with patch('app.tasks.sync_tasks.ExecutionRepository') as mock_repo:
                    mock_execution_repo = AsyncMock()
                    mock_repo.return_value = mock_execution_repo
                    
                    result = execute_sync_task(
                        execution_id=execution_id,
                        session_config=sample_session_config,
                        source_endpoint_config=sample_endpoint_configs['source'],
                        destination_endpoint_config=sample_endpoint_configs['destination'],
                        dry_run=True
                    )
                    
                    assert result['dry_run'] is True
                    assert result['operations_planned'] == 5

    def test_scheduled_sync_task(self):
        """Test scheduled sync task execution."""
        session_id = str(uuid4())
        
        with patch('app.tasks.sync_tasks.get_database_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            with patch('app.tasks.sync_tasks.SessionRepository') as mock_session_repo:
                mock_repo = AsyncMock()
                mock_session_repo.return_value = mock_repo
                
                # Mock session data
                mock_sync_session = MagicMock()
                mock_sync_session.id = session_id
                mock_sync_session.name = 'Scheduled Session'
                mock_repo.get_by_id.return_value = mock_sync_session
                
                with patch('app.tasks.sync_tasks.SyncService') as mock_sync_service:
                    mock_service = AsyncMock()
                    mock_sync_service.return_value = mock_service
                    
                    mock_execution = MagicMock()
                    mock_execution.id = str(uuid4())
                    mock_service.start_sync_execution.return_value = mock_execution
                    
                    result = scheduled_sync_task(session_id)
                    
                    assert result['status'] == 'started'
                    assert result['execution_id'] == str(mock_execution.id)
                    mock_service.start_sync_execution.assert_called_once_with(session_id)


@pytest.mark.unit
class TestHealthTasks:
    """Test cases for health tasks."""

    def test_health_check_task_success(self):
        """Test successful health check task."""
        with patch('app.tasks.health_tasks.HealthChecker') as mock_health_checker:
            mock_checker = AsyncMock()
            mock_health_checker.return_value = mock_checker
            
            mock_results = {
                'database': MagicMock(status='healthy', message='OK'),
                'redis': MagicMock(status='healthy', message='OK')
            }
            mock_checker.run_all_checks.return_value = mock_results
            
            result = health_check_task()
            
            assert result['overall_status'] == 'healthy'
            assert len(result['checks']) == 2
            mock_checker.run_all_checks.assert_called_once()

    def test_health_check_task_failure(self):
        """Test health check task with failures."""
        with patch('app.tasks.health_tasks.HealthChecker') as mock_health_checker:
            mock_checker = AsyncMock()
            mock_health_checker.return_value = mock_checker
            
            mock_results = {
                'database': MagicMock(status='unhealthy', message='Connection failed'),
                'redis': MagicMock(status='healthy', message='OK')
            }
            mock_checker.run_all_checks.return_value = mock_results
            
            result = health_check_task()
            
            assert result['overall_status'] == 'unhealthy'
            assert result['failed_checks'] == 1

    def test_endpoint_health_check_task(self):
        """Test endpoint health check task."""
        endpoint_id = str(uuid4())
        
        with patch('app.tasks.health_tasks.get_database_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            with patch('app.tasks.health_tasks.EndpointRepository') as mock_repo:
                mock_endpoint_repo = AsyncMock()
                mock_repo.return_value = mock_endpoint_repo
                
                # Mock endpoint
                mock_endpoint = MagicMock()
                mock_endpoint.id = endpoint_id
                mock_endpoint.endpoint_type = 'ftp'
                mock_endpoint_repo.get_by_id.return_value = mock_endpoint
                
                with patch('app.tasks.health_tasks.get_endpoint_manager') as mock_get_manager:
                    mock_manager = AsyncMock()
                    mock_manager.health_check.return_value = True
                    mock_get_manager.return_value = mock_manager
                    
                    result = endpoint_health_check_task(endpoint_id)
                    
                    assert result['endpoint_id'] == endpoint_id
                    assert result['status'] == 'healthy'
                    mock_manager.health_check.assert_called_once()

    def test_endpoint_health_check_task_failure(self):
        """Test endpoint health check task failure."""
        endpoint_id = str(uuid4())
        
        with patch('app.tasks.health_tasks.get_database_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            with patch('app.tasks.health_tasks.EndpointRepository') as mock_repo:
                mock_endpoint_repo = AsyncMock()
                mock_repo.return_value = mock_endpoint_repo
                
                mock_endpoint = MagicMock()
                mock_endpoint.id = endpoint_id
                mock_endpoint_repo.get_by_id.return_value = mock_endpoint
                
                with patch('app.tasks.health_tasks.get_endpoint_manager') as mock_get_manager:
                    mock_manager = AsyncMock()
                    mock_manager.health_check.side_effect = Exception("Connection failed")
                    mock_get_manager.return_value = mock_manager
                    
                    result = endpoint_health_check_task(endpoint_id)
                    
                    assert result['status'] == 'unhealthy'
                    assert 'Connection failed' in result['error']


@pytest.mark.unit
class TestMaintenanceTasks:
    """Test cases for maintenance tasks."""

    def test_cleanup_old_executions_task(self):
        """Test cleanup old executions task."""
        with patch('app.tasks.maintenance_tasks.get_database_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            with patch('app.tasks.maintenance_tasks.ExecutionRepository') as mock_repo:
                mock_execution_repo = AsyncMock()
                mock_repo.return_value = mock_execution_repo
                
                mock_execution_repo.cleanup_old_executions.return_value = 15  # 15 cleaned
                
                result = cleanup_old_executions_task(days=30)
                
                assert result['cleaned_count'] == 15
                assert result['days'] == 30
                mock_execution_repo.cleanup_old_executions.assert_called_once_with(days=30)

    def test_cache_cleanup_task(self):
        """Test cache cleanup task."""
        with patch('app.tasks.maintenance_tasks.get_database_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            with patch('app.tasks.maintenance_tasks.CacheRepository') as mock_repo:
                mock_cache_repo = AsyncMock()
                mock_repo.return_value = mock_cache_repo
                
                mock_cache_repo.cleanup_expired_cache.return_value = 25  # 25 cleaned
                
                result = cache_cleanup_task(hours=24)
                
                assert result['cleaned_count'] == 25
                assert result['hours'] == 24
                mock_cache_repo.cleanup_expired_cache.assert_called_once_with(hours=24)

    def test_system_maintenance_task(self):
        """Test system maintenance task."""
        with patch('app.tasks.maintenance_tasks.cleanup_old_executions_task') as mock_cleanup_exec:
            with patch('app.tasks.maintenance_tasks.cache_cleanup_task') as mock_cleanup_cache:
                mock_cleanup_exec.return_value = {'cleaned_count': 10}
                mock_cleanup_cache.return_value = {'cleaned_count': 20}
                
                with patch('app.tasks.maintenance_tasks.system_maintenance_task') as mock_maintenance:
                    mock_maintenance.return_value = {
                        'executions_cleaned': 10,
                        'cache_entries_cleaned': 20,
                        'maintenance_completed': True
                    }
                    
                    result = mock_maintenance()
                    
                    assert result['maintenance_completed'] is True
                    assert result['executions_cleaned'] == 10
                    assert result['cache_entries_cleaned'] == 20

    def test_database_optimization_task(self):
        """Test database optimization task."""
        with patch('app.tasks.maintenance_tasks.get_database_session') as mock_get_session:
            mock_session = AsyncMock()
            mock_get_session.return_value.__aenter__.return_value = mock_session
            
            with patch('app.tasks.maintenance_tasks.database_optimization_task') as mock_optimize:
                mock_optimize.return_value = {
                    'tables_analyzed': 5,
                    'indexes_rebuilt': 3,
                    'optimization_completed': True
                }
                
                result = mock_optimize()
                
                assert result['optimization_completed'] is True
                assert result['tables_analyzed'] == 5
                assert result['indexes_rebuilt'] == 3

    def test_log_rotation_task(self):
        """Test log rotation task."""
        with patch('app.tasks.maintenance_tasks.LogRepository') as mock_repo:
            mock_log_repo = AsyncMock()
            mock_repo.return_value = mock_log_repo
            
            mock_log_repo.rotate_logs.return_value = {
                'archived_logs': 100,
                'deleted_logs': 50
            }
            
            with patch('app.tasks.maintenance_tasks.log_rotation_task') as mock_rotate:
                mock_rotate.return_value = {
                    'archived_logs': 100,
                    'deleted_logs': 50,
                    'rotation_completed': True
                }
                
                result = mock_rotate(days=90)
                
                assert result['rotation_completed'] is True
                assert result['archived_logs'] == 100
                assert result['deleted_logs'] == 50

    def test_disk_space_monitoring_task(self):
        """Test disk space monitoring task."""
        with patch('app.tasks.maintenance_tasks.MetricsCollector') as mock_collector:
            mock_metrics = AsyncMock()
            mock_collector.return_value = mock_metrics
            
            mock_metrics.collect_system_metrics.return_value = MagicMock(
                disk_percent=85.5,
                disk_used_gb=170.5,
                disk_free_gb=29.5
            )
            
            with patch('app.tasks.maintenance_tasks.disk_space_monitoring_task') as mock_monitor:
                mock_monitor.return_value = {
                    'disk_usage_percent': 85.5,
                    'disk_free_gb': 29.5,
                    'alert_triggered': True,
                    'alert_level': 'warning'
                }
                
                result = mock_monitor(threshold_percent=80)
                
                assert result['alert_triggered'] is True
                assert result['alert_level'] == 'warning'
                assert result['disk_usage_percent'] == 85.5
