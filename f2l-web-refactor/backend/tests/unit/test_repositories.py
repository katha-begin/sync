"""
Unit tests for Repository classes.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from app.repositories.endpoint_repository import EndpointRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.execution_repository import ExecutionRepository


@pytest.mark.unit
class TestEndpointRepository:
    """Test cases for EndpointRepository."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def endpoint_repo(self, mock_session):
        """Create EndpointRepository instance."""
        return EndpointRepository(mock_session)

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
    async def test_create_endpoint(self, endpoint_repo, sample_endpoint_data, mock_session):
        """Test endpoint creation."""
        # Mock the database operations
        mock_endpoint = MagicMock()
        mock_endpoint.id = uuid4()
        mock_endpoint.name = sample_endpoint_data['name']
        
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        
        # Mock the constructor to return our mock endpoint
        with pytest.mock.patch('app.repositories.endpoint_repository.Endpoint', return_value=mock_endpoint):
            result = await endpoint_repo.create(sample_endpoint_data)
            
            assert result == mock_endpoint
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_endpoint_by_id(self, endpoint_repo, mock_session):
        """Test getting endpoint by ID."""
        endpoint_id = uuid4()
        mock_endpoint = MagicMock()
        mock_endpoint.id = endpoint_id
        
        mock_session.get.return_value = mock_endpoint
        
        result = await endpoint_repo.get_by_id(endpoint_id)
        
        assert result == mock_endpoint
        mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_endpoint_by_id_not_found(self, endpoint_repo, mock_session):
        """Test getting endpoint by ID when not found."""
        endpoint_id = uuid4()
        mock_session.get.return_value = None
        
        result = await endpoint_repo.get_by_id(endpoint_id)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_list_endpoints(self, endpoint_repo, mock_session):
        """Test listing endpoints."""
        mock_endpoints = [MagicMock(), MagicMock()]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_endpoints
        mock_session.execute.return_value = mock_result
        
        result = await endpoint_repo.list()
        
        assert result == mock_endpoints
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_endpoint(self, endpoint_repo, mock_session):
        """Test endpoint update."""
        endpoint_id = uuid4()
        update_data = {'name': 'Updated Name', 'is_active': False}
        
        mock_endpoint = MagicMock()
        mock_endpoint.id = endpoint_id
        mock_session.get.return_value = mock_endpoint
        
        result = await endpoint_repo.update(endpoint_id, update_data)
        
        assert result == mock_endpoint
        assert mock_endpoint.name == 'Updated Name'
        assert mock_endpoint.is_active is False
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_endpoint(self, endpoint_repo, mock_session):
        """Test endpoint deletion."""
        endpoint_id = uuid4()
        mock_endpoint = MagicMock()
        mock_session.get.return_value = mock_endpoint
        
        result = await endpoint_repo.delete(endpoint_id)
        
        assert result is True
        mock_session.delete.assert_called_once_with(mock_endpoint)
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_endpoint_not_found(self, endpoint_repo, mock_session):
        """Test deleting non-existent endpoint."""
        endpoint_id = uuid4()
        mock_session.get.return_value = None
        
        result = await endpoint_repo.delete(endpoint_id)
        
        assert result is False
        mock_session.delete.assert_not_called()


@pytest.mark.unit
class TestSessionRepository:
    """Test cases for SessionRepository."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def session_repo(self, mock_session):
        """Create SessionRepository instance."""
        return SessionRepository(mock_session)

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
    async def test_create_session(self, session_repo, sample_session_data, mock_session):
        """Test session creation."""
        mock_sync_session = MagicMock()
        mock_sync_session.id = uuid4()
        mock_sync_session.name = sample_session_data['name']
        
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        
        with pytest.mock.patch('app.repositories.session_repository.SyncSession', return_value=mock_sync_session):
            result = await session_repo.create(sample_session_data)
            
            assert result == mock_sync_session
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_active_sessions(self, session_repo, mock_session):
        """Test getting active sessions."""
        mock_sessions = [MagicMock(), MagicMock()]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_sessions
        mock_session.execute.return_value = mock_result
        
        result = await session_repo.get_active_sessions()
        
        assert result == mock_sessions
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_scheduled_sessions(self, session_repo, mock_session):
        """Test getting scheduled sessions."""
        mock_sessions = [MagicMock()]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_sessions
        mock_session.execute.return_value = mock_result
        
        result = await session_repo.get_scheduled_sessions()
        
        assert result == mock_sessions
        mock_session.execute.assert_called_once()


@pytest.mark.unit
class TestExecutionRepository:
    """Test cases for ExecutionRepository."""

    @pytest.fixture
    def mock_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def execution_repo(self, mock_session):
        """Create ExecutionRepository instance."""
        return ExecutionRepository(mock_session)

    @pytest.fixture
    def sample_execution_data(self):
        """Sample execution data."""
        return {
            'session_id': uuid4(),
            'status': 'running',
            'started_at': datetime.utcnow(),
            'dry_run': False
        }

    @pytest.mark.asyncio
    async def test_create_execution(self, execution_repo, sample_execution_data, mock_session):
        """Test execution creation."""
        mock_execution = MagicMock()
        mock_execution.id = uuid4()
        mock_execution.session_id = sample_execution_data['session_id']
        
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh.return_value = None
        
        with pytest.mock.patch('app.repositories.execution_repository.SyncExecution', return_value=mock_execution):
            result = await execution_repo.create(sample_execution_data)
            
            assert result == mock_execution
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_execution_status(self, execution_repo, mock_session):
        """Test execution status update."""
        execution_id = uuid4()
        new_status = 'completed'
        
        mock_execution = MagicMock()
        mock_execution.id = execution_id
        mock_session.get.return_value = mock_execution
        
        result = await execution_repo.update_status(execution_id, new_status)
        
        assert result == mock_execution
        assert mock_execution.status == new_status
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_execution_statistics(self, execution_repo, mock_session):
        """Test getting execution statistics."""
        execution_id = uuid4()
        
        # Mock query result
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (10, 8, 2, 1024000, 512000)  # total, success, failed, total_bytes, success_bytes
        mock_session.execute.return_value = mock_result
        
        result = await execution_repo.get_execution_statistics(execution_id)
        
        assert result['total_operations'] == 10
        assert result['successful_operations'] == 8
        assert result['failed_operations'] == 2
        assert result['total_bytes'] == 1024000
        assert result['successful_bytes'] == 512000
        assert result['success_rate_percent'] == 80.0

    @pytest.mark.asyncio
    async def test_get_recent_executions(self, execution_repo, mock_session):
        """Test getting recent executions."""
        mock_executions = [MagicMock(), MagicMock()]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        mock_session.execute.return_value = mock_result
        
        result = await execution_repo.get_recent_executions(hours=24)
        
        assert result == mock_executions
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_executions(self, execution_repo, mock_session):
        """Test cleanup of old executions."""
        days_to_keep = 30
        
        mock_result = MagicMock()
        mock_result.rowcount = 5  # 5 executions deleted
        mock_session.execute.return_value = mock_result
        
        result = await execution_repo.cleanup_old_executions(days_to_keep)
        
        assert result == 5
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_execution_by_session(self, execution_repo, mock_session):
        """Test getting executions by session."""
        session_id = uuid4()
        mock_executions = [MagicMock(), MagicMock()]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        mock_session.execute.return_value = mock_result
        
        result = await execution_repo.get_by_session(session_id)
        
        assert result == mock_executions
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_running_executions(self, execution_repo, mock_session):
        """Test getting running executions."""
        mock_executions = [MagicMock()]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        mock_session.execute.return_value = mock_result
        
        result = await execution_repo.get_running_executions()
        
        assert result == mock_executions
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_execution_progress(self, execution_repo, mock_session):
        """Test updating execution progress."""
        execution_id = uuid4()
        progress_data = {
            'files_scanned': 100,
            'files_transferred': 50,
            'bytes_transferred': 1024000,
            'current_file': '/path/to/current/file.txt'
        }
        
        mock_execution = MagicMock()
        mock_execution.id = execution_id
        mock_session.get.return_value = mock_execution
        
        result = await execution_repo.update_progress(execution_id, progress_data)
        
        assert result == mock_execution
        assert mock_execution.files_scanned == 100
        assert mock_execution.files_transferred == 50
        assert mock_execution.bytes_transferred == 1024000
        assert mock_execution.current_file == '/path/to/current/file.txt'
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_execution_duration_stats(self, execution_repo, mock_session):
        """Test getting execution duration statistics."""
        # Mock query result with duration stats
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (300.5, 150.0, 600.0, 10)  # avg, min, max, count
        mock_session.execute.return_value = mock_result
        
        result = await execution_repo.get_execution_duration_stats(hours=24)
        
        assert result['average_duration_seconds'] == 300.5
        assert result['min_duration_seconds'] == 150.0
        assert result['max_duration_seconds'] == 600.0
        assert result['total_executions'] == 10

    @pytest.mark.asyncio
    async def test_get_failed_executions(self, execution_repo, mock_session):
        """Test getting failed executions."""
        mock_executions = [MagicMock()]
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        mock_session.execute.return_value = mock_result
        
        result = await execution_repo.get_failed_executions(hours=24)
        
        assert result == mock_executions
        mock_session.execute.assert_called_once()
