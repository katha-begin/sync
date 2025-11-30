"""
Unit tests for Service Layer.
"""
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.endpoint_service import EndpointService
from app.services.session_service import SessionService
from app.services.sync_service import SyncService


@pytest.mark.unit
class TestEndpointService:
    """Test cases for EndpointService."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_endpoint_repo(self):
        """Mock endpoint repository."""
        return AsyncMock()

    @pytest.fixture
    def endpoint_service(self, mock_session, mock_endpoint_repo):
        """Create EndpointService instance."""
        service = EndpointService(mock_session)
        service.endpoint_repo = mock_endpoint_repo
        return service

    @pytest.fixture
    def sample_endpoint_data(self):
        """Sample endpoint data."""
        return {
            'name': 'Test FTP Server',
            'endpoint_type': 'ftp',
            'host': 'ftp.example.com',
            'port': 21,
            'username': 'testuser',
            'password': 'testpass',
            'base_path': '/test/path',
            'is_active': True
        }

    @pytest.mark.asyncio
    async def test_create_endpoint_success(self, endpoint_service, mock_endpoint_repo, sample_endpoint_data):
        """Test successful endpoint creation."""
        mock_endpoint = MagicMock()
        mock_endpoint.id = uuid4()
        mock_endpoint.name = sample_endpoint_data['name']
        mock_endpoint_repo.create.return_value = mock_endpoint
        
        result = await endpoint_service.create_endpoint(sample_endpoint_data)
        
        assert result == mock_endpoint
        mock_endpoint_repo.create.assert_called_once()
        
        # Check that password was encrypted
        create_call_args = mock_endpoint_repo.create.call_args[0][0]
        assert create_call_args['password'] != sample_endpoint_data['password']

    @pytest.mark.asyncio
    async def test_create_endpoint_duplicate_name(self, endpoint_service, mock_endpoint_repo, sample_endpoint_data):
        """Test endpoint creation with duplicate name."""
        mock_endpoint_repo.get_by_name.return_value = MagicMock()  # Existing endpoint
        
        with pytest.raises(ValueError, match="Endpoint with name .* already exists"):
            await endpoint_service.create_endpoint(sample_endpoint_data)

    @pytest.mark.asyncio
    async def test_get_endpoint_by_id(self, endpoint_service, mock_endpoint_repo):
        """Test getting endpoint by ID."""
        endpoint_id = uuid4()
        mock_endpoint = MagicMock()
        mock_endpoint_repo.get_by_id.return_value = mock_endpoint
        
        result = await endpoint_service.get_endpoint(endpoint_id)
        
        assert result == mock_endpoint
        mock_endpoint_repo.get_by_id.assert_called_once_with(endpoint_id)

    @pytest.mark.asyncio
    async def test_test_endpoint_connection_success(self, endpoint_service):
        """Test successful endpoint connection test."""
        endpoint_config = {
            'endpoint_type': 'ftp',
            'host': 'ftp.example.com',
            'port': 21,
            'username': 'testuser',
            'password': 'testpass'
        }
        
        with patch('app.services.endpoint_service.FTPManager') as mock_ftp:
            mock_manager = MagicMock()
            mock_manager.health_check.return_value = True
            mock_ftp.return_value = mock_manager
            
            result = await endpoint_service.test_connection(endpoint_config)
            
            assert result['status'] == 'success'
            assert 'Connection successful' in result['message']

    @pytest.mark.asyncio
    async def test_test_endpoint_connection_failure(self, endpoint_service):
        """Test endpoint connection test failure."""
        endpoint_config = {
            'endpoint_type': 'ftp',
            'host': 'ftp.example.com',
            'port': 21,
            'username': 'testuser',
            'password': 'testpass'
        }
        
        with patch('app.services.endpoint_service.FTPManager') as mock_ftp:
            mock_manager = MagicMock()
            mock_manager.health_check.side_effect = Exception("Connection failed")
            mock_ftp.return_value = mock_manager
            
            result = await endpoint_service.test_connection(endpoint_config)
            
            assert result['status'] == 'error'
            assert 'Connection failed' in result['message']

    @pytest.mark.asyncio
    async def test_get_endpoint_statistics(self, endpoint_service, mock_endpoint_repo):
        """Test getting endpoint statistics."""
        endpoint_id = uuid4()
        
        mock_endpoint_repo.get_endpoint_statistics.return_value = {
            'total_sessions': 5,
            'total_executions': 15,
            'successful_executions': 12,
            'failed_executions': 3,
            'last_used': datetime.utcnow()
        }
        
        result = await endpoint_service.get_endpoint_statistics(endpoint_id)
        
        assert result['total_sessions'] == 5
        assert result['total_executions'] == 15
        assert result['success_rate'] == 80.0  # 12/15 * 100


@pytest.mark.unit
class TestSessionService:
    """Test cases for SessionService."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_session_repo(self):
        """Mock session repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_endpoint_repo(self):
        """Mock endpoint repository."""
        return AsyncMock()

    @pytest.fixture
    def session_service(self, mock_session, mock_session_repo, mock_endpoint_repo):
        """Create SessionService instance."""
        service = SessionService(mock_session)
        service.session_repo = mock_session_repo
        service.endpoint_repo = mock_endpoint_repo
        return service

    @pytest.fixture
    def sample_session_data(self):
        """Sample session data."""
        return {
            'name': 'Test Sync Session',
            'source_endpoint_id': uuid4(),
            'destination_endpoint_id': uuid4(),
            'source_path': '/source/path',
            'destination_path': '/dest/path',
            'sync_direction': 'source_to_destination',
            'is_active': True,
            'schedule_enabled': False
        }

    @pytest.mark.asyncio
    async def test_create_session_success(self, session_service, mock_session_repo, mock_endpoint_repo, sample_session_data):
        """Test successful session creation."""
        # Mock endpoints exist
        mock_endpoint_repo.get_by_id.return_value = MagicMock()
        
        mock_sync_session = MagicMock()
        mock_sync_session.id = uuid4()
        mock_session_repo.create.return_value = mock_sync_session
        
        result = await session_service.create_session(sample_session_data)
        
        assert result == mock_sync_session
        mock_session_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_invalid_endpoints(self, session_service, mock_endpoint_repo, sample_session_data):
        """Test session creation with invalid endpoints."""
        # Mock source endpoint doesn't exist
        mock_endpoint_repo.get_by_id.return_value = None
        
        with pytest.raises(ValueError, match="Source endpoint not found"):
            await session_service.create_session(sample_session_data)

    @pytest.mark.asyncio
    async def test_validate_session_paths(self, session_service):
        """Test session path validation."""
        session_data = {
            'source_path': '/valid/path',
            'destination_path': '/valid/dest',
            'sync_direction': 'source_to_destination'
        }
        
        # Should not raise exception
        session_service._validate_session_paths(session_data)
        
        # Test invalid paths
        invalid_session = {
            'source_path': '',  # Empty path
            'destination_path': '/valid/dest',
            'sync_direction': 'source_to_destination'
        }
        
        with pytest.raises(ValueError, match="Source path cannot be empty"):
            session_service._validate_session_paths(invalid_session)

    @pytest.mark.asyncio
    async def test_get_scheduled_sessions(self, session_service, mock_session_repo):
        """Test getting scheduled sessions."""
        mock_sessions = [MagicMock(), MagicMock()]
        mock_session_repo.get_scheduled_sessions.return_value = mock_sessions
        
        result = await session_service.get_scheduled_sessions()
        
        assert result == mock_sessions
        mock_session_repo.get_scheduled_sessions.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_session_schedule(self, session_service, mock_session_repo):
        """Test updating session schedule."""
        session_id = uuid4()
        schedule_data = {
            'schedule_enabled': True,
            'schedule_cron': '0 2 * * *',  # Daily at 2 AM
            'schedule_timezone': 'UTC'
        }
        
        mock_session = MagicMock()
        mock_session_repo.update.return_value = mock_session
        
        result = await session_service.update_session_schedule(session_id, schedule_data)
        
        assert result == mock_session
        mock_session_repo.update.assert_called_once_with(session_id, schedule_data)


@pytest.mark.unit
class TestSyncService:
    """Test cases for SyncService."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_execution_repo(self):
        """Mock execution repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_session_repo(self):
        """Mock session repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_endpoint_repo(self):
        """Mock endpoint repository."""
        return AsyncMock()

    @pytest.fixture
    def sync_service(self, mock_session, mock_execution_repo, mock_session_repo, mock_endpoint_repo):
        """Create SyncService instance."""
        service = SyncService(mock_session)
        service.execution_repo = mock_execution_repo
        service.session_repo = mock_session_repo
        service.endpoint_repo = mock_endpoint_repo
        return service

    @pytest.fixture
    def sample_session(self):
        """Sample session object."""
        session = MagicMock()
        session.id = uuid4()
        session.name = 'Test Session'
        session.source_endpoint_id = uuid4()
        session.destination_endpoint_id = uuid4()
        session.source_path = '/source'
        session.destination_path = '/dest'
        session.sync_direction = 'source_to_destination'
        return session

    @pytest.mark.asyncio
    async def test_start_sync_execution_success(self, sync_service, mock_execution_repo, mock_session_repo, mock_endpoint_repo, sample_session):
        """Test successful sync execution start."""
        session_id = sample_session.id
        
        # Mock repositories
        mock_session_repo.get_by_id.return_value = sample_session
        mock_endpoint_repo.get_by_id.return_value = MagicMock()  # Mock endpoints
        
        mock_execution = MagicMock()
        mock_execution.id = uuid4()
        mock_execution_repo.create.return_value = mock_execution
        
        with patch('app.services.sync_service.execute_sync_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='task-123')
            
            result = await sync_service.start_sync_execution(session_id)
            
            assert result == mock_execution
            mock_execution_repo.create.assert_called_once()
            mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_sync_execution_session_not_found(self, sync_service, mock_session_repo):
        """Test sync execution start with non-existent session."""
        session_id = uuid4()
        mock_session_repo.get_by_id.return_value = None
        
        with pytest.raises(ValueError, match="Session not found"):
            await sync_service.start_sync_execution(session_id)

    @pytest.mark.asyncio
    async def test_start_sync_execution_dry_run(self, sync_service, mock_execution_repo, mock_session_repo, mock_endpoint_repo, sample_session):
        """Test sync execution start in dry run mode."""
        session_id = sample_session.id
        
        mock_session_repo.get_by_id.return_value = sample_session
        mock_endpoint_repo.get_by_id.return_value = MagicMock()
        
        mock_execution = MagicMock()
        mock_execution_repo.create.return_value = mock_execution
        
        with patch('app.services.sync_service.execute_sync_task') as mock_task:
            mock_task.delay.return_value = MagicMock(id='task-123')
            
            result = await sync_service.start_sync_execution(session_id, dry_run=True)
            
            assert result == mock_execution
            # Check that dry_run was passed to task
            call_args = mock_task.delay.call_args[1]
            assert call_args['dry_run'] is True

    @pytest.mark.asyncio
    async def test_cancel_sync_execution(self, sync_service, mock_execution_repo):
        """Test sync execution cancellation."""
        execution_id = uuid4()
        
        mock_execution = MagicMock()
        mock_execution.status = 'running'
        mock_execution.celery_task_id = 'task-123'
        mock_execution_repo.get_by_id.return_value = mock_execution
        
        with patch('app.services.sync_service.celery_app') as mock_celery:
            mock_celery.control.revoke.return_value = None
            
            result = await sync_service.cancel_sync_execution(execution_id)
            
            assert result is True
            mock_execution_repo.update_status.assert_called_once_with(execution_id, 'cancelled')
            mock_celery.control.revoke.assert_called_once_with('task-123', terminate=True)

    @pytest.mark.asyncio
    async def test_cancel_sync_execution_not_running(self, sync_service, mock_execution_repo):
        """Test cancelling non-running execution."""
        execution_id = uuid4()
        
        mock_execution = MagicMock()
        mock_execution.status = 'completed'
        mock_execution_repo.get_by_id.return_value = mock_execution
        
        result = await sync_service.cancel_sync_execution(execution_id)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_get_execution_progress(self, sync_service, mock_execution_repo):
        """Test getting execution progress."""
        execution_id = uuid4()
        
        mock_execution = MagicMock()
        mock_execution.status = 'running'
        mock_execution.files_scanned = 100
        mock_execution.files_transferred = 50
        mock_execution.bytes_transferred = 1024000
        mock_execution.current_file = '/current/file.txt'
        mock_execution_repo.get_by_id.return_value = mock_execution
        
        result = await sync_service.get_execution_progress(execution_id)
        
        assert result['status'] == 'running'
        assert result['files_scanned'] == 100
        assert result['files_transferred'] == 50
        assert result['progress_percent'] == 50.0  # 50/100 * 100

    @pytest.mark.asyncio
    async def test_analyze_sync_operations(self, sync_service, mock_session_repo, mock_endpoint_repo, sample_session):
        """Test sync operations analysis."""
        session_id = sample_session.id
        
        mock_session_repo.get_by_id.return_value = sample_session
        mock_endpoint_repo.get_by_id.return_value = MagicMock()
        
        with patch('app.services.sync_service.MetadataEngine') as mock_metadata_engine:
            mock_engine = AsyncMock()
            mock_metadata_engine.return_value = mock_engine
            
            mock_analysis = {
                'operations': [
                    {
                        'operation': 'download',
                        'source_path': '/source/file1.txt',
                        'dest_path': '/dest/file1.txt'
                    }
                ],
                'summary': {
                    'total_operations': 1,
                    'downloads': 1,
                    'uploads': 0,
                    'deletes': 0,
                    'skipped': 0
                }
            }
            mock_engine.analyze_sync_operations.return_value = mock_analysis
            
            with patch('app.services.sync_service.get_endpoint_manager') as mock_get_manager:
                mock_get_manager.return_value = AsyncMock()
                
                result = await sync_service.analyze_sync_operations(session_id)
                
                assert result == mock_analysis
                mock_engine.analyze_sync_operations.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_execution_statistics(self, sync_service, mock_execution_repo):
        """Test getting execution statistics."""
        execution_id = uuid4()
        
        mock_stats = {
            'total_operations': 100,
            'successful_operations': 95,
            'failed_operations': 5,
            'total_bytes': 1024000,
            'successful_bytes': 972800,
            'success_rate_percent': 95.0
        }
        mock_execution_repo.get_execution_statistics.return_value = mock_stats
        
        result = await sync_service.get_execution_statistics(execution_id)
        
        assert result == mock_stats
        mock_execution_repo.get_execution_statistics.assert_called_once_with(execution_id)

    @pytest.mark.asyncio
    async def test_get_recent_executions(self, sync_service, mock_execution_repo):
        """Test getting recent executions."""
        mock_executions = [MagicMock(), MagicMock()]
        mock_execution_repo.get_recent_executions.return_value = mock_executions
        
        result = await sync_service.get_recent_executions(hours=24)
        
        assert result == mock_executions
        mock_execution_repo.get_recent_executions.assert_called_once_with(hours=24)

    @pytest.mark.asyncio
    async def test_cleanup_old_executions(self, sync_service, mock_execution_repo):
        """Test cleanup of old executions."""
        mock_execution_repo.cleanup_old_executions.return_value = 10  # 10 executions cleaned
        
        result = await sync_service.cleanup_old_executions(days=30)
        
        assert result == 10
        mock_execution_repo.cleanup_old_executions.assert_called_once_with(days=30)
