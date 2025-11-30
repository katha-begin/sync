"""
Unit tests for Sync Engine.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import tempfile
import os

from app.core.sync_engine import SyncEngine


@pytest.mark.unit
class TestSyncEngine:
    """Test cases for SyncEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = SyncEngine()

    def test_init(self):
        """Test SyncEngine initialization."""
        assert self.engine is not None

    @pytest.mark.asyncio
    async def test_execute_session_success(self):
        """Test successful session execution."""
        # Mock session data
        session_data = {
            'id': str(uuid4()),
            'name': 'Test Session',
            'source_endpoint_id': str(uuid4()),
            'destination_endpoint_id': str(uuid4()),
            'source_path': '/source',
            'destination_path': '/dest',
            'sync_direction': 'source_to_destination'
        }
        
        # Mock execution data
        execution_data = {
            'id': str(uuid4()),
            'session_id': session_data['id'],
            'status': 'running'
        }
        
        # Mock managers
        source_manager = AsyncMock()
        dest_manager = AsyncMock()
        
        # Mock metadata engine
        with patch('app.core.sync_engine.MetadataEngine') as mock_metadata_engine:
            mock_engine = AsyncMock()
            mock_metadata_engine.return_value = mock_engine
            
            # Mock analysis result
            mock_engine.analyze_sync_operations.return_value = {
                'operations': [
                    {
                        'operation': 'download',
                        'source_path': '/source/file1.txt',
                        'dest_path': '/dest/file1.txt',
                        'source_metadata': {'size': 1024}
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
            
            # Mock successful file transfer
            with patch.object(self.engine, '_execute_download', return_value=True):
                result = await self.engine.execute_session(
                    session_data=session_data,
                    execution_data=execution_data,
                    source_manager=source_manager,
                    dest_manager=dest_manager
                )
            
            assert result['status'] == 'completed'
            assert result['files_transferred'] == 1
            assert result['downloads'] == 1

    @pytest.mark.asyncio
    async def test_execute_session_dry_run(self):
        """Test session execution in dry run mode."""
        session_data = {
            'id': str(uuid4()),
            'name': 'Test Session',
            'source_endpoint_id': str(uuid4()),
            'destination_endpoint_id': str(uuid4()),
            'source_path': '/source',
            'destination_path': '/dest',
            'sync_direction': 'source_to_destination'
        }
        
        execution_data = {
            'id': str(uuid4()),
            'session_id': session_data['id'],
            'status': 'running'
        }
        
        source_manager = AsyncMock()
        dest_manager = AsyncMock()
        
        with patch('app.core.sync_engine.MetadataEngine') as mock_metadata_engine:
            mock_engine = AsyncMock()
            mock_metadata_engine.return_value = mock_engine
            
            mock_engine.analyze_sync_operations.return_value = {
                'operations': [
                    {
                        'operation': 'download',
                        'source_path': '/source/file1.txt',
                        'dest_path': '/dest/file1.txt',
                        'source_metadata': {'size': 1024}
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
            
            result = await self.engine.execute_session(
                session_data=session_data,
                execution_data=execution_data,
                source_manager=source_manager,
                dest_manager=dest_manager,
                dry_run=True
            )
            
            assert result['status'] == 'completed'
            assert result['files_transferred'] == 0  # No actual transfers in dry run
            assert result['downloads'] == 1  # But operations are counted

    @pytest.mark.asyncio
    async def test_execute_download_success(self):
        """Test successful file download."""
        source_manager = MagicMock()
        dest_manager = MagicMock()
        
        source_manager.download_file.return_value = True
        dest_manager.upload_file.return_value = True
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = '/tmp/test_file'
            
            with patch('os.path.exists', return_value=True):
                with patch('os.unlink') as mock_unlink:
                    result = await self.engine._execute_download(
                        source_manager=source_manager,
                        dest_manager=dest_manager,
                        source_path='/source/file.txt',
                        dest_path='/dest/file.txt'
                    )
                    
                    assert result is True
                    source_manager.download_file.assert_called_once()
                    dest_manager.upload_file.assert_called_once()
                    mock_unlink.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_download_source_failure(self):
        """Test download failure at source."""
        source_manager = MagicMock()
        dest_manager = MagicMock()
        
        source_manager.download_file.return_value = False
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = '/tmp/test_file'
            
            with patch('os.path.exists', return_value=True):
                with patch('os.unlink'):
                    result = await self.engine._execute_download(
                        source_manager=source_manager,
                        dest_manager=dest_manager,
                        source_path='/source/file.txt',
                        dest_path='/dest/file.txt'
                    )
                    
                    assert result is False
                    source_manager.download_file.assert_called_once()
                    dest_manager.upload_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_download_dest_failure(self):
        """Test download failure at destination."""
        source_manager = MagicMock()
        dest_manager = MagicMock()
        
        source_manager.download_file.return_value = True
        dest_manager.upload_file.return_value = False
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = '/tmp/test_file'
            
            with patch('os.path.exists', return_value=True):
                with patch('os.unlink'):
                    result = await self.engine._execute_download(
                        source_manager=source_manager,
                        dest_manager=dest_manager,
                        source_path='/source/file.txt',
                        dest_path='/dest/file.txt'
                    )
                    
                    assert result is False
                    source_manager.download_file.assert_called_once()
                    dest_manager.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_upload_success(self):
        """Test successful file upload."""
        source_manager = MagicMock()
        dest_manager = MagicMock()
        
        dest_manager.download_file.return_value = True
        source_manager.upload_file.return_value = True
        
        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            mock_temp.return_value.__enter__.return_value.name = '/tmp/test_file'
            
            with patch('os.path.exists', return_value=True):
                with patch('os.unlink'):
                    result = await self.engine._execute_upload(
                        source_manager=source_manager,
                        dest_manager=dest_manager,
                        source_path='/source/file.txt',
                        dest_path='/dest/file.txt'
                    )
                    
                    assert result is True
                    dest_manager.download_file.assert_called_once()
                    source_manager.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_delete_success(self):
        """Test successful file deletion."""
        dest_manager = MagicMock()
        dest_manager.delete_file.return_value = True
        
        result = await self.engine._execute_delete(
            dest_manager=dest_manager,
            file_path='/dest/file.txt'
        )
        
        assert result is True
        dest_manager.delete_file.assert_called_once_with('/dest/file.txt')

    @pytest.mark.asyncio
    async def test_execute_delete_failure(self):
        """Test file deletion failure."""
        dest_manager = MagicMock()
        dest_manager.delete_file.return_value = False
        
        result = await self.engine._execute_delete(
            dest_manager=dest_manager,
            file_path='/dest/file.txt'
        )
        
        assert result is False
        dest_manager.delete_file.assert_called_once_with('/dest/file.txt')

    @pytest.mark.asyncio
    async def test_get_endpoint_manager_ftp(self):
        """Test getting FTP endpoint manager."""
        endpoint_config = {
            'endpoint_type': 'ftp',
            'host': 'ftp.example.com',
            'port': 21,
            'username': 'user',
            'password': 'pass'
        }
        
        with patch('app.core.sync_engine.FTPManager') as mock_ftp:
            manager = await self.engine._get_endpoint_manager(endpoint_config)
            mock_ftp.assert_called_once_with(endpoint_config)

    @pytest.mark.asyncio
    async def test_get_endpoint_manager_sftp(self):
        """Test getting SFTP endpoint manager."""
        endpoint_config = {
            'endpoint_type': 'sftp',
            'host': 'sftp.example.com',
            'port': 22,
            'username': 'user',
            'password': 'pass'
        }
        
        with patch('app.core.sync_engine.SFTPManager') as mock_sftp:
            manager = await self.engine._get_endpoint_manager(endpoint_config)
            mock_sftp.assert_called_once_with(endpoint_config)

    @pytest.mark.asyncio
    async def test_get_endpoint_manager_s3(self):
        """Test getting S3 endpoint manager."""
        endpoint_config = {
            'endpoint_type': 's3',
            'aws_access_key_id': 'access_key',
            'aws_secret_access_key': 'secret_key',
            'bucket_name': 'test-bucket',
            'region': 'us-east-1'
        }
        
        with patch('app.core.sync_engine.S3Manager') as mock_s3:
            manager = await self.engine._get_endpoint_manager(endpoint_config)
            mock_s3.assert_called_once_with(endpoint_config)

    @pytest.mark.asyncio
    async def test_get_endpoint_manager_local(self):
        """Test getting Local endpoint manager."""
        endpoint_config = {
            'endpoint_type': 'local',
            'base_path': '/local/path'
        }
        
        with patch('app.core.sync_engine.LocalManager') as mock_local:
            manager = await self.engine._get_endpoint_manager(endpoint_config)
            mock_local.assert_called_once_with(endpoint_config)

    @pytest.mark.asyncio
    async def test_get_endpoint_manager_invalid_type(self):
        """Test getting manager for invalid endpoint type."""
        endpoint_config = {
            'endpoint_type': 'invalid',
            'host': 'example.com'
        }
        
        with pytest.raises(ValueError, match="Unsupported endpoint type"):
            await self.engine._get_endpoint_manager(endpoint_config)

    def test_calculate_progress(self):
        """Test progress calculation."""
        progress = self.engine._calculate_progress(
            completed_operations=25,
            total_operations=100,
            bytes_transferred=1024 * 1024,  # 1 MB
            total_bytes=4 * 1024 * 1024     # 4 MB
        )
        
        assert progress['operations_percent'] == 25.0
        assert progress['bytes_percent'] == 25.0
        assert progress['completed_operations'] == 25
        assert progress['total_operations'] == 100
        assert progress['bytes_transferred'] == 1024 * 1024
        assert progress['total_bytes'] == 4 * 1024 * 1024

    def test_calculate_progress_zero_total(self):
        """Test progress calculation with zero totals."""
        progress = self.engine._calculate_progress(
            completed_operations=0,
            total_operations=0,
            bytes_transferred=0,
            total_bytes=0
        )
        
        assert progress['operations_percent'] == 0.0
        assert progress['bytes_percent'] == 0.0

    def test_format_bytes(self):
        """Test byte formatting."""
        assert self.engine._format_bytes(1024) == "1.0 KB"
        assert self.engine._format_bytes(1024 * 1024) == "1.0 MB"
        assert self.engine._format_bytes(1024 * 1024 * 1024) == "1.0 GB"
        assert self.engine._format_bytes(512) == "512 B"
        assert self.engine._format_bytes(0) == "0 B"

    def test_format_duration(self):
        """Test duration formatting."""
        assert self.engine._format_duration(30) == "30s"
        assert self.engine._format_duration(90) == "1m 30s"
        assert self.engine._format_duration(3661) == "1h 1m 1s"
        assert self.engine._format_duration(0) == "0s"

    @pytest.mark.asyncio
    async def test_session_execution_with_progress_callback(self):
        """Test session execution with progress callback."""
        progress_updates = []
        
        def progress_callback(progress):
            progress_updates.append(progress)
        
        session_data = {
            'id': str(uuid4()),
            'name': 'Test Session',
            'source_endpoint_id': str(uuid4()),
            'destination_endpoint_id': str(uuid4()),
            'source_path': '/source',
            'destination_path': '/dest',
            'sync_direction': 'source_to_destination'
        }
        
        execution_data = {
            'id': str(uuid4()),
            'session_id': session_data['id'],
            'status': 'running'
        }
        
        source_manager = AsyncMock()
        dest_manager = AsyncMock()
        
        with patch('app.core.sync_engine.MetadataEngine') as mock_metadata_engine:
            mock_engine = AsyncMock()
            mock_metadata_engine.return_value = mock_engine
            
            mock_engine.analyze_sync_operations.return_value = {
                'operations': [
                    {
                        'operation': 'download',
                        'source_path': '/source/file1.txt',
                        'dest_path': '/dest/file1.txt',
                        'source_metadata': {'size': 1024}
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
            
            with patch.object(self.engine, '_execute_download', return_value=True):
                await self.engine.execute_session(
                    session_data=session_data,
                    execution_data=execution_data,
                    source_manager=source_manager,
                    dest_manager=dest_manager,
                    progress_callback=progress_callback
                )
            
            # Should have received progress updates
            assert len(progress_updates) > 0
            
            # Check final progress
            final_progress = progress_updates[-1]
            assert final_progress['operations_percent'] == 100.0
