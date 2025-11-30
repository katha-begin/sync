"""
Unit tests for FTP Manager.
"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime
import tempfile
import os

from app.core.ftp_manager import FTPManager


@pytest.mark.unit
class TestFTPManager:
    """Test cases for FTPManager."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = {
            'host': 'ftp.example.com',
            'port': 21,
            'username': 'testuser',
            'password': 'testpass',
            'timeout': 30
        }
        self.manager = FTPManager(self.config)

    def test_init(self):
        """Test FTPManager initialization."""
        assert self.manager.host == 'ftp.example.com'
        assert self.manager.port == 21
        assert self.manager.username == 'testuser'
        assert self.manager.password == 'testpass'
        assert self.manager.timeout == 30
        assert self.manager.ftp is None
        assert not self.manager.connected

    @patch('app.core.ftp_manager.FTP')
    def test_connect_success(self, mock_ftp_class):
        """Test successful FTP connection."""
        mock_ftp = MagicMock()
        mock_ftp_class.return_value = mock_ftp
        
        result = self.manager.connect()
        
        assert result is True
        assert self.manager.connected is True
        mock_ftp.connect.assert_called_once_with('ftp.example.com', 21, 30)
        mock_ftp.login.assert_called_once_with('testuser', 'testpass')

    @patch('app.core.ftp_manager.FTP')
    def test_connect_failure(self, mock_ftp_class):
        """Test FTP connection failure."""
        mock_ftp = MagicMock()
        mock_ftp.connect.side_effect = Exception("Connection failed")
        mock_ftp_class.return_value = mock_ftp
        
        result = self.manager.connect()
        
        assert result is False
        assert self.manager.connected is False

    @patch('app.core.ftp_manager.FTP')
    def test_disconnect(self, mock_ftp_class):
        """Test FTP disconnection."""
        mock_ftp = MagicMock()
        mock_ftp_class.return_value = mock_ftp
        
        # Connect first
        self.manager.connect()
        
        # Then disconnect
        self.manager.disconnect()
        
        assert self.manager.connected is False
        mock_ftp.quit.assert_called_once()
        mock_ftp.close.assert_called_once()

    @patch('app.core.ftp_manager.FTP')
    def test_list_directory_success(self, mock_ftp_class):
        """Test successful directory listing."""
        mock_ftp = MagicMock()
        mock_ftp.nlst.return_value = ['file1.txt', 'file2.txt', 'subdir']
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.list_directory('/test/path')
        
        assert result == ['file1.txt', 'file2.txt', 'subdir']
        mock_ftp.nlst.assert_called_once_with('/test/path')

    @patch('app.core.ftp_manager.FTP')
    def test_list_directory_failure(self, mock_ftp_class):
        """Test directory listing failure."""
        mock_ftp = MagicMock()
        mock_ftp.nlst.side_effect = Exception("Directory not found")
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.list_directory('/nonexistent')
        
        assert result == []

    @patch('app.core.ftp_manager.FTP')
    def test_get_file_info_success(self, mock_ftp_class):
        """Test successful file info retrieval."""
        mock_ftp = MagicMock()
        mock_ftp.size.return_value = 1024
        mock_ftp.voidcmd.return_value = "213 20240101120000"
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.get_file_info('/test/file.txt')
        
        assert result is not None
        assert result['size'] == 1024
        assert 'modified_time' in result
        assert result['name'] == 'file.txt'
        assert result['path'] == '/test/file.txt'

    @patch('app.core.ftp_manager.FTP')
    def test_get_file_info_failure(self, mock_ftp_class):
        """Test file info retrieval failure."""
        mock_ftp = MagicMock()
        mock_ftp.size.side_effect = Exception("File not found")
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.get_file_info('/nonexistent.txt')
        
        assert result is None

    @patch('app.core.ftp_manager.FTP')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_file_success(self, mock_file, mock_ftp_class):
        """Test successful file download."""
        mock_ftp = MagicMock()
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.download_file('/remote/file.txt', '/local/file.txt')
        
        assert result is True
        mock_file.assert_called_once_with('/local/file.txt', 'wb')
        mock_ftp.retrbinary.assert_called_once()

    @patch('app.core.ftp_manager.FTP')
    def test_download_file_failure(self, mock_ftp_class):
        """Test file download failure."""
        mock_ftp = MagicMock()
        mock_ftp.retrbinary.side_effect = Exception("Download failed")
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.download_file('/remote/file.txt', '/local/file.txt')
        
        assert result is False

    @patch('app.core.ftp_manager.FTP')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test content')
    def test_upload_file_success(self, mock_file, mock_ftp_class):
        """Test successful file upload."""
        mock_ftp = MagicMock()
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.upload_file('/local/file.txt', '/remote/file.txt')
        
        assert result is True
        mock_file.assert_called_once_with('/local/file.txt', 'rb')
        mock_ftp.storbinary.assert_called_once()

    @patch('app.core.ftp_manager.FTP')
    def test_upload_file_failure(self, mock_ftp_class):
        """Test file upload failure."""
        mock_ftp = MagicMock()
        mock_ftp.storbinary.side_effect = Exception("Upload failed")
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.upload_file('/local/file.txt', '/remote/file.txt')
        
        assert result is False

    @patch('app.core.ftp_manager.FTP')
    def test_delete_file_success(self, mock_ftp_class):
        """Test successful file deletion."""
        mock_ftp = MagicMock()
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.delete_file('/remote/file.txt')
        
        assert result is True
        mock_ftp.delete.assert_called_once_with('/remote/file.txt')

    @patch('app.core.ftp_manager.FTP')
    def test_delete_file_failure(self, mock_ftp_class):
        """Test file deletion failure."""
        mock_ftp = MagicMock()
        mock_ftp.delete.side_effect = Exception("Delete failed")
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.delete_file('/remote/file.txt')
        
        assert result is False

    @patch('app.core.ftp_manager.FTP')
    def test_health_check_connected(self, mock_ftp_class):
        """Test health check when connected."""
        mock_ftp = MagicMock()
        mock_ftp.pwd.return_value = '/'
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.health_check()
        
        assert result is True
        mock_ftp.pwd.assert_called_once()

    def test_health_check_not_connected(self):
        """Test health check when not connected."""
        result = self.manager.health_check()
        assert result is False

    @patch('app.core.ftp_manager.FTP')
    def test_health_check_failure(self, mock_ftp_class):
        """Test health check failure."""
        mock_ftp = MagicMock()
        mock_ftp.pwd.side_effect = Exception("Connection lost")
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.health_check()
        
        assert result is False

    def test_context_manager_success(self):
        """Test context manager usage."""
        with patch('app.core.ftp_manager.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp_class.return_value = mock_ftp
            
            with self.manager as manager:
                assert manager.connected is True
                mock_ftp.connect.assert_called_once()
                mock_ftp.login.assert_called_once()
            
            mock_ftp.quit.assert_called_once()
            mock_ftp.close.assert_called_once()

    def test_context_manager_failure(self):
        """Test context manager with connection failure."""
        with patch('app.core.ftp_manager.FTP') as mock_ftp_class:
            mock_ftp = MagicMock()
            mock_ftp.connect.side_effect = Exception("Connection failed")
            mock_ftp_class.return_value = mock_ftp
            
            with pytest.raises(Exception):
                with self.manager as manager:
                    pass

    @patch('app.core.ftp_manager.FTP')
    def test_list_directory_recursive(self, mock_ftp_class):
        """Test recursive directory listing."""
        mock_ftp = MagicMock()
        
        # Mock directory structure
        def mock_nlst(path):
            if path == '/test':
                return ['file1.txt', 'subdir']
            elif path == '/test/subdir':
                return ['file2.txt']
            else:
                return []
        
        def mock_cwd_and_pwd(path):
            return path
        
        mock_ftp.nlst.side_effect = mock_nlst
        mock_ftp.pwd.side_effect = mock_cwd_and_pwd
        mock_ftp_class.return_value = mock_ftp
        
        self.manager.connect()
        result = self.manager.list_directory_recursive('/test', max_depth=2)
        
        assert isinstance(result, list)
        # Should contain files from both levels
        file_paths = [item['path'] for item in result if not item.get('is_directory', False)]
        assert '/test/file1.txt' in file_paths

    @patch('app.core.ftp_manager.FTP')
    def test_parse_mdtm_response(self, mock_ftp_class):
        """Test MDTM response parsing."""
        mock_ftp = MagicMock()
        mock_ftp_class.return_value = mock_ftp
        
        # Test valid MDTM response
        result = self.manager._parse_mdtm_response("213 20240101120000")
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        
        # Test invalid MDTM response
        result = self.manager._parse_mdtm_response("550 File not found")
        assert result is None
        
        # Test malformed MDTM response
        result = self.manager._parse_mdtm_response("213 invalid")
        assert result is None

    def test_normalize_path(self):
        """Test path normalization."""
        assert self.manager._normalize_path('/test/path/') == '/test/path'
        assert self.manager._normalize_path('test/path') == '/test/path'
        assert self.manager._normalize_path('//test//path//') == '/test/path'
        assert self.manager._normalize_path('') == '/'
        assert self.manager._normalize_path('/') == '/'
