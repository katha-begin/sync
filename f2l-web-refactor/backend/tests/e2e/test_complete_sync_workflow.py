"""
End-to-end tests for complete sync workflows.
"""
import pytest
import tempfile
import os
import shutil
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient


@pytest.mark.e2e
class TestCompleteSyncWorkflow:
    """End-to-end tests for complete sync workflows."""

    @pytest.fixture
    def temp_directories(self):
        """Create temporary directories for testing."""
        source_dir = tempfile.mkdtemp(prefix="f2l_test_source_")
        dest_dir = tempfile.mkdtemp(prefix="f2l_test_dest_")
        
        # Create test files in source directory
        test_files = {
            'file1.txt': 'Content of file 1',
            'file2.txt': 'Content of file 2',
            'subdir/file3.txt': 'Content of file 3 in subdirectory'
        }
        
        for file_path, content in test_files.items():
            full_path = Path(source_dir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
        
        yield {
            'source': source_dir,
            'destination': dest_dir,
            'test_files': test_files
        }
        
        # Cleanup
        shutil.rmtree(source_dir, ignore_errors=True)
        shutil.rmtree(dest_dir, ignore_errors=True)

    @pytest.fixture
    def mock_ftp_server(self):
        """Mock FTP server for testing."""
        with patch('app.core.ftp_manager.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            
            # Mock FTP operations
            mock_ftp.connect.return_value = None
            mock_ftp.login.return_value = None
            mock_ftp.quit.return_value = None
            mock_ftp.close.return_value = None
            
            # Mock directory listing
            mock_ftp.nlst.return_value = ['file1.txt', 'file2.txt', 'subdir']
            mock_ftp.size.return_value = 1024
            mock_ftp.voidcmd.return_value = '213 20240101120000'  # MDTM response
            
            # Mock file operations
            mock_ftp.retrbinary.return_value = None
            mock_ftp.storbinary.return_value = None
            mock_ftp.delete.return_value = None
            
            yield mock_ftp

    def test_local_to_local_sync_workflow(self, test_client: TestClient, temp_directories):
        """Test complete local-to-local sync workflow."""
        source_dir = temp_directories['source']
        dest_dir = temp_directories['destination']
        
        # Step 1: Create source endpoint
        source_endpoint_data = {
            'name': 'Test Source Local',
            'endpoint_type': 'local',
            'base_path': source_dir,
            'is_active': True
        }
        
        response = test_client.post("/api/v1/endpoints/", json=source_endpoint_data)
        assert response.status_code == 201
        source_endpoint_id = response.json()['id']
        
        # Step 2: Create destination endpoint
        dest_endpoint_data = {
            'name': 'Test Dest Local',
            'endpoint_type': 'local',
            'base_path': dest_dir,
            'is_active': True
        }
        
        response = test_client.post("/api/v1/endpoints/", json=dest_endpoint_data)
        assert response.status_code == 201
        dest_endpoint_id = response.json()['id']
        
        # Step 3: Create sync session
        session_data = {
            'name': 'Local to Local Sync',
            'source_endpoint_id': source_endpoint_id,
            'destination_endpoint_id': dest_endpoint_id,
            'source_path': '/',
            'destination_path': '/',
            'sync_direction': 'source_to_destination',
            'is_active': True
        }
        
        response = test_client.post("/api/v1/sessions/", json=session_data)
        assert response.status_code == 201
        session_id = response.json()['id']
        
        # Step 4: Browse source directory
        response = test_client.get(
            f"/api/v1/endpoints/{source_endpoint_id}/browse",
            params={'path': '/', 'max_depth': 2}
        )
        assert response.status_code == 200
        browse_data = response.json()
        assert len(browse_data['items']) >= 3  # file1.txt, file2.txt, subdir
        
        # Step 5: Analyze sync operations (dry run)
        with patch('app.api.v1.sessions.SyncService') as mock_sync_service:
            mock_service = AsyncMock()
            mock_sync_service.return_value = mock_service
            
            mock_analysis = {
                'operations': [
                    {
                        'operation': 'download',
                        'source_path': '/file1.txt',
                        'dest_path': '/file1.txt',
                        'reason': 'File does not exist at destination'
                    },
                    {
                        'operation': 'download',
                        'source_path': '/file2.txt',
                        'dest_path': '/file2.txt',
                        'reason': 'File does not exist at destination'
                    }
                ],
                'summary': {
                    'total_operations': 2,
                    'downloads': 2,
                    'uploads': 0,
                    'deletes': 0,
                    'skipped': 0
                }
            }
            mock_service.analyze_sync_operations.return_value = mock_analysis
            
            response = test_client.post(f"/api/v1/sessions/{session_id}/analyze")
            assert response.status_code == 200
            analysis_data = response.json()
            assert analysis_data['summary']['total_operations'] >= 2
        
        # Step 6: Execute sync
        with patch('app.api.v1.sessions.SyncService') as mock_sync_service:
            mock_service = AsyncMock()
            mock_sync_service.return_value = mock_service
            
            mock_execution = MagicMock()
            mock_execution.id = str(uuid4())
            mock_execution.status = 'running'
            mock_service.start_sync_execution.return_value = mock_execution
            
            response = test_client.post(f"/api/v1/sessions/{session_id}/execute")
            assert response.status_code == 202
            execution_data = response.json()
            execution_id = execution_data['execution_id']
            
            # Step 7: Monitor execution progress
            mock_progress = {
                'status': 'completed',
                'files_scanned': 3,
                'files_transferred': 3,
                'bytes_transferred': 1024,
                'progress_percent': 100.0,
                'current_file': None
            }
            mock_service.get_execution_progress.return_value = mock_progress
            
            response = test_client.get(f"/api/v1/executions/{execution_id}/progress")
            assert response.status_code == 200
            progress_data = response.json()
            assert progress_data['status'] == 'completed'
            assert progress_data['progress_percent'] == 100.0

    def test_ftp_to_local_sync_workflow(self, test_client: TestClient, temp_directories, mock_ftp_server):
        """Test complete FTP-to-local sync workflow."""
        dest_dir = temp_directories['destination']
        
        # Step 1: Create FTP source endpoint
        source_endpoint_data = {
            'name': 'Test FTP Server',
            'endpoint_type': 'ftp',
            'host': 'ftp.example.com',
            'port': 21,
            'username': 'testuser',
            'password': 'testpass',
            'base_path': '/remote/path',
            'is_active': True
        }
        
        response = test_client.post("/api/v1/endpoints/", json=source_endpoint_data)
        assert response.status_code == 201
        source_endpoint_id = response.json()['id']
        
        # Step 2: Create local destination endpoint
        dest_endpoint_data = {
            'name': 'Test Local Dest',
            'endpoint_type': 'local',
            'base_path': dest_dir,
            'is_active': True
        }
        
        response = test_client.post("/api/v1/endpoints/", json=dest_endpoint_data)
        assert response.status_code == 201
        dest_endpoint_id = response.json()['id']
        
        # Step 3: Test FTP connection
        with patch('app.api.v1.endpoints.test_endpoint_connection') as mock_test:
            mock_test.return_value = {'status': 'success', 'message': 'Connection successful'}
            
            response = test_client.post(f"/api/v1/endpoints/{source_endpoint_id}/test")
            assert response.status_code == 200
            test_data = response.json()
            assert test_data['status'] == 'success'
        
        # Step 4: Browse FTP directory
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.return_value = [
                {
                    'name': 'remote_file1.txt',
                    'path': '/remote/path/remote_file1.txt',
                    'size': 1024,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                },
                {
                    'name': 'remote_file2.txt',
                    'path': '/remote/path/remote_file2.txt',
                    'size': 2048,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                }
            ]
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{source_endpoint_id}/browse",
                params={'path': '/remote/path', 'max_depth': 1}
            )
            assert response.status_code == 200
            browse_data = response.json()
            assert len(browse_data['items']) == 2
        
        # Step 5: Create and execute sync session
        session_data = {
            'name': 'FTP to Local Sync',
            'source_endpoint_id': source_endpoint_id,
            'destination_endpoint_id': dest_endpoint_id,
            'source_path': '/remote/path',
            'destination_path': '/',
            'sync_direction': 'source_to_destination',
            'is_active': True
        }
        
        response = test_client.post("/api/v1/sessions/", json=session_data)
        assert response.status_code == 201
        session_id = response.json()['id']
        
        # Execute sync with mocked service
        with patch('app.api.v1.sessions.SyncService') as mock_sync_service:
            mock_service = AsyncMock()
            mock_sync_service.return_value = mock_service
            
            mock_execution = MagicMock()
            mock_execution.id = str(uuid4())
            mock_execution.status = 'completed'
            mock_service.start_sync_execution.return_value = mock_execution
            
            response = test_client.post(f"/api/v1/sessions/{session_id}/execute")
            assert response.status_code == 202

    def test_bidirectional_sync_workflow(self, test_client: TestClient, temp_directories):
        """Test bidirectional sync workflow."""
        source_dir = temp_directories['source']
        dest_dir = temp_directories['destination']
        
        # Create additional file in destination
        dest_only_file = Path(dest_dir) / 'dest_only.txt'
        dest_only_file.write_text('This file exists only in destination')
        
        # Step 1: Create endpoints
        source_endpoint_data = {
            'name': 'Bidirectional Source',
            'endpoint_type': 'local',
            'base_path': source_dir,
            'is_active': True
        }
        
        dest_endpoint_data = {
            'name': 'Bidirectional Dest',
            'endpoint_type': 'local',
            'base_path': dest_dir,
            'is_active': True
        }
        
        source_response = test_client.post("/api/v1/endpoints/", json=source_endpoint_data)
        dest_response = test_client.post("/api/v1/endpoints/", json=dest_endpoint_data)
        
        source_endpoint_id = source_response.json()['id']
        dest_endpoint_id = dest_response.json()['id']
        
        # Step 2: Create bidirectional sync session
        session_data = {
            'name': 'Bidirectional Sync',
            'source_endpoint_id': source_endpoint_id,
            'destination_endpoint_id': dest_endpoint_id,
            'source_path': '/',
            'destination_path': '/',
            'sync_direction': 'bidirectional',
            'is_active': True
        }
        
        response = test_client.post("/api/v1/sessions/", json=session_data)
        assert response.status_code == 201
        session_id = response.json()['id']
        
        # Step 3: Analyze bidirectional operations
        with patch('app.api.v1.sessions.SyncService') as mock_sync_service:
            mock_service = AsyncMock()
            mock_sync_service.return_value = mock_service
            
            mock_analysis = {
                'operations': [
                    {
                        'operation': 'download',
                        'source_path': '/file1.txt',
                        'dest_path': '/file1.txt',
                        'reason': 'File does not exist at destination'
                    },
                    {
                        'operation': 'upload',
                        'source_path': '/dest_only.txt',
                        'dest_path': '/dest_only.txt',
                        'reason': 'File does not exist at source'
                    }
                ],
                'summary': {
                    'total_operations': 2,
                    'downloads': 1,
                    'uploads': 1,
                    'deletes': 0,
                    'skipped': 0
                }
            }
            mock_service.analyze_sync_operations.return_value = mock_analysis
            
            response = test_client.post(f"/api/v1/sessions/{session_id}/analyze")
            assert response.status_code == 200
            analysis_data = response.json()
            
            # Should have both download and upload operations
            assert analysis_data['summary']['downloads'] >= 1
            assert analysis_data['summary']['uploads'] >= 1

    def test_scheduled_sync_workflow(self, test_client: TestClient, temp_directories):
        """Test scheduled sync workflow."""
        source_dir = temp_directories['source']
        dest_dir = temp_directories['destination']
        
        # Step 1: Create endpoints and session
        source_endpoint_data = {
            'name': 'Scheduled Source',
            'endpoint_type': 'local',
            'base_path': source_dir,
            'is_active': True
        }
        
        dest_endpoint_data = {
            'name': 'Scheduled Dest',
            'endpoint_type': 'local',
            'base_path': dest_dir,
            'is_active': True
        }
        
        source_response = test_client.post("/api/v1/endpoints/", json=source_endpoint_data)
        dest_response = test_client.post("/api/v1/endpoints/", json=dest_endpoint_data)
        
        source_endpoint_id = source_response.json()['id']
        dest_endpoint_id = dest_response.json()['id']
        
        # Step 2: Create session with schedule
        session_data = {
            'name': 'Scheduled Sync Session',
            'source_endpoint_id': source_endpoint_id,
            'destination_endpoint_id': dest_endpoint_id,
            'source_path': '/',
            'destination_path': '/',
            'sync_direction': 'source_to_destination',
            'is_active': True,
            'schedule_enabled': True,
            'schedule_cron': '0 2 * * *',  # Daily at 2 AM
            'schedule_timezone': 'UTC'
        }
        
        response = test_client.post("/api/v1/sessions/", json=session_data)
        assert response.status_code == 201
        session_id = response.json()['id']
        session_data_response = response.json()
        
        assert session_data_response['schedule_enabled'] is True
        assert session_data_response['schedule_cron'] == '0 2 * * *'
        
        # Step 3: Get scheduled sessions
        response = test_client.get("/api/v1/sessions/scheduled")
        assert response.status_code == 200
        scheduled_sessions = response.json()
        
        # Should include our scheduled session
        session_ids = [session['id'] for session in scheduled_sessions]
        assert session_id in session_ids
        
        # Step 4: Update schedule
        schedule_update = {
            'schedule_cron': '0 6 * * *',  # Change to 6 AM
            'schedule_timezone': 'America/New_York'
        }
        
        response = test_client.put(f"/api/v1/sessions/{session_id}/schedule", json=schedule_update)
        assert response.status_code == 200
        updated_session = response.json()
        assert updated_session['schedule_cron'] == '0 6 * * *'

    def test_error_handling_workflow(self, test_client: TestClient):
        """Test error handling in sync workflow."""
        # Step 1: Try to create session with non-existent endpoints
        invalid_session_data = {
            'name': 'Invalid Session',
            'source_endpoint_id': str(uuid4()),  # Non-existent
            'destination_endpoint_id': str(uuid4()),  # Non-existent
            'source_path': '/',
            'destination_path': '/',
            'sync_direction': 'source_to_destination'
        }
        
        response = test_client.post("/api/v1/sessions/", json=invalid_session_data)
        assert response.status_code == 400  # Should fail validation
        
        # Step 2: Try to execute non-existent session
        fake_session_id = str(uuid4())
        response = test_client.post(f"/api/v1/sessions/{fake_session_id}/execute")
        assert response.status_code == 404
        
        # Step 3: Try to get progress of non-existent execution
        fake_execution_id = str(uuid4())
        response = test_client.get(f"/api/v1/executions/{fake_execution_id}/progress")
        assert response.status_code == 404

    def test_health_monitoring_during_sync(self, test_client: TestClient):
        """Test health monitoring during sync operations."""
        # Step 1: Check overall system health
        with patch('app.api.v1.health.get_system_health') as mock_health:
            mock_health.return_value = {
                'overall_status': 'healthy',
                'timestamp': '2024-01-01T12:00:00Z',
                'health_checks': {
                    'database': {'status': 'healthy', 'duration_ms': 15.5},
                    'redis': {'status': 'healthy', 'duration_ms': 8.2}
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
            health_data = response.json()
            assert health_data['overall_status'] == 'healthy'
        
        # Step 2: Check readiness for sync operations
        response = test_client.get("/api/v1/health/ready")
        assert response.status_code == 200
        
        # Step 3: Get system metrics
        with patch('app.api.v1.health.metrics_collector') as mock_collector:
            mock_metrics = AsyncMock()
            mock_metrics.cpu_percent = 30.0
            mock_metrics.memory_percent = 50.0
            mock_metrics.disk_percent = 65.0
            mock_collector.collect_system_metrics.return_value = mock_metrics
            
            response = test_client.get("/api/v1/health/metrics")
            assert response.status_code == 200
            metrics_data = response.json()
            assert metrics_data['cpu_percent'] == 30.0
