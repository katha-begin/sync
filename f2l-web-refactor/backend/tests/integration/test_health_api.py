"""
Integration tests for Health API.
"""
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestHealthAPI:
    """Integration tests for health API."""

    def test_health_status_healthy(self, test_client: TestClient):
        """Test health status when system is healthy."""
        with patch('app.api.v1.health.get_system_health') as mock_health:
            mock_health.return_value = {
                'overall_status': 'healthy',
                'timestamp': '2024-01-01T12:00:00Z',
                'health_checks': {
                    'database': {
                        'status': 'healthy',
                        'message': 'Database connection successful',
                        'duration_ms': 15.5
                    },
                    'redis': {
                        'status': 'healthy',
                        'message': 'Redis connection successful',
                        'duration_ms': 8.2
                    }
                },
                'system_metrics': {
                    'cpu_percent': 25.5,
                    'memory_percent': 45.2,
                    'disk_percent': 60.1
                },
                'active_alerts': [],
                'uptime_seconds': 86400
            }
            
            response = test_client.get("/api/v1/health/")
            
            assert response.status_code == 200
            data = response.json()
            assert data['overall_status'] == 'healthy'
            assert 'health_checks' in data
            assert 'system_metrics' in data

    def test_health_status_unhealthy(self, test_client: TestClient):
        """Test health status when system is unhealthy."""
        with patch('app.api.v1.health.get_system_health') as mock_health:
            mock_health.return_value = {
                'overall_status': 'unhealthy',
                'timestamp': '2024-01-01T12:00:00Z',
                'health_checks': {
                    'database': {
                        'status': 'unhealthy',
                        'message': 'Database connection failed',
                        'duration_ms': 5000.0
                    }
                },
                'system_metrics': {},
                'active_alerts': [
                    {
                        'metric': 'database',
                        'level': 'critical',
                        'message': 'Database connection failed'
                    }
                ],
                'uptime_seconds': 86400
            }
            
            response = test_client.get("/api/v1/health/")
            
            assert response.status_code == 503  # Service Unavailable
            data = response.json()
            assert data['overall_status'] == 'unhealthy'

    def test_liveness_probe(self, test_client: TestClient):
        """Test Kubernetes liveness probe."""
        response = test_client.get("/api/v1/health/live")
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'alive'
        assert data['service'] == 'f2l-sync'

    def test_readiness_probe_ready(self, test_client: TestClient):
        """Test Kubernetes readiness probe when ready."""
        with patch('app.api.v1.health.health_checker') as mock_checker:
            # Mock successful critical checks
            async def mock_run_check(check_name):
                mock_result = AsyncMock()
                mock_result.status = 'healthy'
                mock_result.message = f'{check_name} is healthy'
                mock_result.duration_ms = 10.0
                return mock_result
            
            mock_checker.run_check.side_effect = mock_run_check
            
            response = test_client.get("/api/v1/health/ready")
            
            assert response.status_code == 200
            data = response.json()
            assert data['ready'] is True
            assert data['service'] == 'f2l-sync'

    def test_readiness_probe_not_ready(self, test_client: TestClient):
        """Test Kubernetes readiness probe when not ready."""
        with patch('app.api.v1.health.health_checker') as mock_checker:
            # Mock failed database check
            async def mock_run_check(check_name):
                mock_result = AsyncMock()
                if check_name == 'database':
                    mock_result.status = 'unhealthy'
                    mock_result.message = 'Database connection failed'
                else:
                    mock_result.status = 'healthy'
                    mock_result.message = f'{check_name} is healthy'
                mock_result.duration_ms = 10.0
                return mock_result
            
            mock_checker.run_check.side_effect = mock_run_check
            
            response = test_client.get("/api/v1/health/ready")
            
            assert response.status_code == 503
            data = response.json()
            assert data['ready'] is False

    def test_health_checks_detailed(self, test_client: TestClient):
        """Test detailed health checks endpoint."""
        with patch('app.api.v1.health.health_checker') as mock_checker:
            mock_results = {
                'database': AsyncMock(
                    status='healthy',
                    message='Database connection successful',
                    duration_ms=15.5,
                    details={'connection_pool': 'active'},
                    timestamp='2024-01-01T12:00:00Z'
                ),
                'redis': AsyncMock(
                    status='healthy',
                    message='Redis connection successful',
                    duration_ms=8.2,
                    details=None,
                    timestamp='2024-01-01T12:00:00Z'
                )
            }
            
            mock_checker.run_all_checks.return_value = mock_results
            
            response = test_client.get("/api/v1/health/checks")
            
            assert response.status_code == 200
            data = response.json()
            assert 'checks' in data
            assert 'database' in data['checks']
            assert 'redis' in data['checks']
            assert data['checks']['database']['status'] == 'healthy'

    def test_specific_health_check(self, test_client: TestClient):
        """Test specific health check endpoint."""
        with patch('app.api.v1.health.health_checker') as mock_checker:
            mock_result = AsyncMock()
            mock_result.name = 'database'
            mock_result.status = 'healthy'
            mock_result.message = 'Database connection successful'
            mock_result.duration_ms = 15.5
            mock_result.details = {'connection_pool': 'active'}
            mock_result.timestamp = '2024-01-01T12:00:00Z'
            
            mock_checker.run_check.return_value = mock_result
            
            response = test_client.get("/api/v1/health/checks/database")
            
            assert response.status_code == 200
            data = response.json()
            assert data['name'] == 'database'
            assert data['status'] == 'healthy'
            assert data['details'] == {'connection_pool': 'active'}

    def test_system_metrics(self, test_client: TestClient):
        """Test system metrics endpoint."""
        with patch('app.api.v1.health.metrics_collector') as mock_collector:
            mock_metrics = AsyncMock()
            mock_metrics.timestamp = '2024-01-01T12:00:00Z'
            mock_metrics.cpu_percent = 25.5
            mock_metrics.memory_percent = 45.2
            mock_metrics.memory_used_mb = 2048.0
            mock_metrics.memory_available_mb = 2560.0
            mock_metrics.disk_percent = 60.1
            mock_metrics.disk_used_gb = 120.5
            mock_metrics.disk_free_gb = 79.5
            mock_metrics.load_average = [1.2, 1.1, 1.0]
            mock_metrics.process_count = 150
            mock_metrics.thread_count = 8
            
            mock_collector.collect_system_metrics.return_value = mock_metrics
            
            response = test_client.get("/api/v1/health/metrics")
            
            assert response.status_code == 200
            data = response.json()
            assert data['cpu_percent'] == 25.5
            assert data['memory_percent'] == 45.2
            assert data['disk_percent'] == 60.1
            assert data['load_average'] == [1.2, 1.1, 1.0]

    def test_metrics_summary(self, test_client: TestClient):
        """Test metrics summary endpoint."""
        with patch('app.api.v1.health.metrics_collector') as mock_collector:
            mock_summary = {
                'time_period_hours': 1,
                'data_points': 60,
                'cpu': {
                    'average_percent': 30.5,
                    'peak_percent': 45.2,
                    'current_percent': 25.5
                },
                'memory': {
                    'average_percent': 50.1,
                    'peak_percent': 65.8,
                    'current_percent': 45.2,
                    'current_used_mb': 2048.0,
                    'current_available_mb': 2560.0
                },
                'disk': {
                    'average_percent': 58.5,
                    'peak_percent': 62.1,
                    'current_percent': 60.1,
                    'current_used_gb': 120.5,
                    'current_free_gb': 79.5
                }
            }
            
            mock_collector.get_metrics_summary.return_value = mock_summary
            
            response = test_client.get("/api/v1/health/metrics/summary?hours=1")
            
            assert response.status_code == 200
            data = response.json()
            assert data['time_period_hours'] == 1
            assert data['cpu']['average_percent'] == 30.5
            assert data['memory']['peak_percent'] == 65.8

    def test_metrics_summary_invalid_hours(self, test_client: TestClient):
        """Test metrics summary with invalid hours parameter."""
        response = test_client.get("/api/v1/health/metrics/summary?hours=25")
        
        assert response.status_code == 400

    def test_configuration_status(self, test_client: TestClient):
        """Test configuration status endpoint."""
        with patch('app.api.v1.health.config_manager') as mock_config:
            mock_config.get_configuration_summary.return_value = {
                'application': {
                    'name': 'F2L Sync',
                    'version': '2.0.0',
                    'environment': 'development'
                },
                'database': {
                    'url_masked': 'postgresql://user:***@localhost:5432/f2l_sync'
                }
            }
            
            mock_config.check_environment_health.return_value = {
                'overall_status': 'healthy',
                'checks': {'temp_directory': 'accessible'},
                'warnings': [],
                'errors': []
            }
            
            response = test_client.get("/api/v1/health/config")
            
            assert response.status_code == 200
            data = response.json()
            assert 'configuration' in data
            assert 'environment_health' in data
            assert data['configuration']['application']['name'] == 'F2L Sync'

    def test_version_info(self, test_client: TestClient):
        """Test version information endpoint."""
        response = test_client.get("/api/v1/health/version")
        
        assert response.status_code == 200
        data = response.json()
        assert 'app_name' in data
        assert 'version' in data
        assert 'environment' in data
        assert 'python_version' in data
        assert 'api_version' in data

    def test_manual_health_check_run(self, test_client: TestClient):
        """Test manual health check trigger."""
        with patch('app.api.v1.health.health_checker') as mock_checker:
            mock_results = {
                'database': AsyncMock(
                    status='healthy',
                    message='Database connection successful',
                    duration_ms=15.5,
                    details=None,
                    timestamp='2024-01-01T12:00:00Z'
                )
            }
            
            mock_checker.run_all_checks.return_value = mock_results
            
            response = test_client.post("/api/v1/health/checks/run")
            
            assert response.status_code == 200
            data = response.json()
            assert data['overall_status'] == 'healthy'
            assert data['checks_run'] == 1
            assert 'results' in data

    def test_ping_endpoint(self, test_client: TestClient):
        """Test simple ping endpoint."""
        response = test_client.get("/api/v1/health/ping")
        
        assert response.status_code == 200
        data = response.json()
        assert data['message'] == 'pong'
        assert data['service'] == 'f2l-sync'

    def test_service_status(self, test_client: TestClient):
        """Test service status endpoint."""
        with patch('app.api.v1.health.health_checker') as mock_checker:
            # Mock critical service checks
            async def mock_run_check(check_name):
                mock_result = AsyncMock()
                mock_result.status = 'healthy'
                return mock_result
            
            mock_checker.run_check.side_effect = mock_run_check
            
            response = test_client.get("/api/v1/health/status")
            
            assert response.status_code == 200
            data = response.json()
            assert 'service' in data
            assert 'version' in data
            assert 'status' in data
            assert 'uptime_seconds' in data
            assert 'critical_services' in data

    def test_health_check_error_handling(self, test_client: TestClient):
        """Test health check error handling."""
        with patch('app.api.v1.health.get_system_health') as mock_health:
            mock_health.side_effect = Exception("Health check system failure")
            
            response = test_client.get("/api/v1/health/")
            
            assert response.status_code == 503
            data = response.json()
            assert data['overall_status'] == 'unhealthy'
            assert 'error' in data
