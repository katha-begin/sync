"""
Integration tests for Browse API.
"""
import pytest
from uuid import uuid4
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.mark.integration
class TestBrowseAPI:
    """Integration tests for browse API."""

    @pytest.fixture
    def test_endpoint_id(self, test_client: TestClient, sample_endpoint_data):
        """Create a test endpoint and return its ID."""
        response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        return response.json()["id"]

    def test_browse_directory_success(self, test_client: TestClient, test_endpoint_id):
        """Test successful directory browsing."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            # Mock manager
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.return_value = [
                {
                    'name': 'file1.txt',
                    'path': '/test/path/file1.txt',
                    'size': 1024,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False,
                    'permissions': '644'
                },
                {
                    'name': 'subdir',
                    'path': '/test/path/subdir',
                    'size': 0,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': True,
                    'permissions': '755'
                }
            ]
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/browse",
                params={"path": "/test/path", "max_depth": 2}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["path"] == "/test/path"
            assert data["max_depth"] == 2
            assert len(data["items"]) == 2
            
            # Check file item
            file_item = next(item for item in data["items"] if item["name"] == "file1.txt")
            assert file_item["size"] == 1024
            assert file_item["is_directory"] is False
            
            # Check directory item
            dir_item = next(item for item in data["items"] if item["name"] == "subdir")
            assert dir_item["is_directory"] is True

    def test_browse_directory_endpoint_not_found(self, test_client: TestClient):
        """Test browsing with non-existent endpoint."""
        fake_id = str(uuid4())
        response = test_client.get(
            f"/api/v1/endpoints/{fake_id}/browse",
            params={"path": "/test/path"}
        )
        
        assert response.status_code == 404

    def test_browse_directory_connection_error(self, test_client: TestClient, test_endpoint_id):
        """Test browsing with connection error."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.side_effect = Exception("Connection failed")
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/browse",
                params={"path": "/test/path"}
            )
            
            assert response.status_code == 500

    def test_browse_directory_with_search(self, test_client: TestClient, test_endpoint_id):
        """Test directory browsing with search pattern."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.return_value = [
                {
                    'name': 'document.txt',
                    'path': '/test/path/document.txt',
                    'size': 1024,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False,
                    'permissions': '644'
                },
                {
                    'name': 'image.jpg',
                    'path': '/test/path/image.jpg',
                    'size': 2048,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False,
                    'permissions': '644'
                }
            ]
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/browse",
                params={
                    "path": "/test/path",
                    "search_pattern": "*.txt"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should only return .txt files
            assert len(data["items"]) == 1
            assert data["items"][0]["name"] == "document.txt"

    def test_get_file_metadata_success(self, test_client: TestClient, test_endpoint_id):
        """Test successful file metadata retrieval."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_file_info.return_value = {
                'name': 'test_file.txt',
                'path': '/test/path/test_file.txt',
                'size': 1024,
                'modified_time': '2024-01-01T12:00:00Z',
                'is_directory': False,
                'permissions': '644',
                'checksum': 'abc123def456'
            }
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/metadata",
                params={"file_path": "/test/path/test_file.txt"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test_file.txt"
            assert data["size"] == 1024
            assert data["checksum"] == "abc123def456"

    def test_get_file_metadata_not_found(self, test_client: TestClient, test_endpoint_id):
        """Test file metadata retrieval for non-existent file."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.get_file_info.return_value = None
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/metadata",
                params={"file_path": "/nonexistent/file.txt"}
            )
            
            assert response.status_code == 404

    def test_compare_files_metadata(self, test_client: TestClient, test_data_factory):
        """Test file metadata comparison between endpoints."""
        # Create two endpoints
        endpoint1_data = test_data_factory.create_endpoint_data("ftp", name="Source FTP")
        endpoint2_data = test_data_factory.create_endpoint_data("local", name="Dest Local")
        
        response1 = test_client.post("/api/v1/endpoints/", json=endpoint1_data)
        response2 = test_client.post("/api/v1/endpoints/", json=endpoint2_data)
        
        source_id = response1.json()["id"]
        dest_id = response2.json()["id"]
        
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            # Mock managers for both endpoints
            def mock_manager_factory(endpoint_config):
                mock_manager = AsyncMock()
                if endpoint_config.get('endpoint_type') == 'ftp':
                    # Source file is newer
                    mock_manager.get_file_info.return_value = {
                        'name': 'test.txt',
                        'path': '/source/test.txt',
                        'size': 1024,
                        'modified_time': '2024-01-01T13:00:00Z',
                        'is_directory': False
                    }
                else:
                    # Destination file is older
                    mock_manager.get_file_info.return_value = {
                        'name': 'test.txt',
                        'path': '/dest/test.txt',
                        'size': 1024,
                        'modified_time': '2024-01-01T12:00:00Z',
                        'is_directory': False
                    }
                return mock_manager
            
            mock_get_manager.side_effect = mock_manager_factory
            
            comparison_data = {
                "source_endpoint_id": source_id,
                "destination_endpoint_id": dest_id,
                "source_path": "/source/test.txt",
                "destination_path": "/dest/test.txt"
            }
            
            response = test_client.post("/api/v1/browse/compare-metadata", json=comparison_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["operation"] == "download"  # Source is newer
            assert data["reason"] == "Source file is newer"

    def test_search_files_by_pattern(self, test_client: TestClient, test_endpoint_id):
        """Test searching files by pattern."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.return_value = [
                {
                    'name': 'report_2024.pdf',
                    'path': '/docs/report_2024.pdf',
                    'size': 5120,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                },
                {
                    'name': 'backup_2024.zip',
                    'path': '/backups/backup_2024.zip',
                    'size': 10240,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                }
            ]
            mock_get_manager.return_value = mock_manager
            
            search_data = {
                "endpoint_id": test_endpoint_id,
                "base_path": "/",
                "pattern": "*2024*",
                "max_depth": 5
            }
            
            response = test_client.post("/api/v1/browse/search", json=search_data)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["results"]) == 2
            assert all("2024" in item["name"] for item in data["results"])

    def test_browse_directory_with_filters(self, test_client: TestClient, test_endpoint_id):
        """Test directory browsing with file filters."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.return_value = [
                {
                    'name': 'document.txt',
                    'path': '/test/document.txt',
                    'size': 1024,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                },
                {
                    'name': 'image.jpg',
                    'path': '/test/image.jpg',
                    'size': 2048,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                },
                {
                    'name': 'temp.tmp',
                    'path': '/test/temp.tmp',
                    'size': 512,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                }
            ]
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/browse",
                params={
                    "path": "/test",
                    "include_patterns": "*.txt,*.jpg",
                    "exclude_patterns": "*.tmp"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should exclude .tmp files
            file_names = [item["name"] for item in data["items"]]
            assert "document.txt" in file_names
            assert "image.jpg" in file_names
            assert "temp.tmp" not in file_names

    def test_browse_directory_pagination(self, test_client: TestClient, test_endpoint_id):
        """Test directory browsing with pagination."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            # Create many files for pagination test
            files = []
            for i in range(50):
                files.append({
                    'name': f'file_{i:03d}.txt',
                    'path': f'/test/file_{i:03d}.txt',
                    'size': 1024,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                })
            mock_manager.list_directory_recursive.return_value = files
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/browse",
                params={
                    "path": "/test",
                    "skip": 10,
                    "limit": 20
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 20
            assert data["pagination"]["skip"] == 10
            assert data["pagination"]["limit"] == 20
            assert data["pagination"]["total"] == 50

    def test_browse_directory_sorting(self, test_client: TestClient, test_endpoint_id):
        """Test directory browsing with sorting."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.return_value = [
                {
                    'name': 'zebra.txt',
                    'path': '/test/zebra.txt',
                    'size': 1024,
                    'modified_time': '2024-01-01T12:00:00Z',
                    'is_directory': False
                },
                {
                    'name': 'alpha.txt',
                    'path': '/test/alpha.txt',
                    'size': 2048,
                    'modified_time': '2024-01-01T11:00:00Z',
                    'is_directory': False
                }
            ]
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/browse",
                params={
                    "path": "/test",
                    "sort_by": "name",
                    "sort_order": "asc"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Should be sorted alphabetically
            names = [item["name"] for item in data["items"]]
            assert names == ["alpha.txt", "zebra.txt"]

    def test_get_directory_size(self, test_client: TestClient, test_endpoint_id):
        """Test getting directory size calculation."""
        with patch('app.api.v1.browse.get_endpoint_manager') as mock_get_manager:
            mock_manager = AsyncMock()
            mock_manager.list_directory_recursive.return_value = [
                {
                    'name': 'file1.txt',
                    'path': '/test/file1.txt',
                    'size': 1024,
                    'is_directory': False
                },
                {
                    'name': 'file2.txt',
                    'path': '/test/file2.txt',
                    'size': 2048,
                    'is_directory': False
                }
            ]
            mock_get_manager.return_value = mock_manager
            
            response = test_client.get(
                f"/api/v1/endpoints/{test_endpoint_id}/size",
                params={"path": "/test"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_size"] == 3072  # 1024 + 2048
            assert data["file_count"] == 2
            assert data["directory_count"] == 0
