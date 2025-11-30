"""
Integration tests for Endpoints API.
"""
import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from app.core.security import encrypt_password


@pytest.mark.integration
class TestEndpointsAPI:
    """Integration tests for endpoints API."""

    def test_create_endpoint_success(self, test_client: TestClient, sample_endpoint_data):
        """Test successful endpoint creation."""
        response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == sample_endpoint_data["name"]
        assert data["endpoint_type"] == sample_endpoint_data["endpoint_type"]
        assert data["host"] == sample_endpoint_data["host"]
        assert data["port"] == sample_endpoint_data["port"]
        assert data["is_active"] == sample_endpoint_data["is_active"]
        assert "id" in data
        assert "created_at" in data
        assert "password" not in data  # Password should not be returned

    def test_create_endpoint_invalid_data(self, test_client: TestClient):
        """Test endpoint creation with invalid data."""
        invalid_data = {
            "name": "",  # Empty name
            "endpoint_type": "invalid_type",
            "host": "",  # Empty host
            "port": -1,  # Invalid port
        }
        
        response = test_client.post("/api/v1/endpoints/", json=invalid_data)
        
        assert response.status_code == 422  # Validation error

    def test_get_endpoint_success(self, test_client: TestClient, sample_endpoint_data):
        """Test successful endpoint retrieval."""
        # First create an endpoint
        create_response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        assert create_response.status_code == 201
        endpoint_id = create_response.json()["id"]
        
        # Then retrieve it
        response = test_client.get(f"/api/v1/endpoints/{endpoint_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == endpoint_id
        assert data["name"] == sample_endpoint_data["name"]

    def test_get_endpoint_not_found(self, test_client: TestClient):
        """Test getting non-existent endpoint."""
        fake_id = str(uuid4())
        response = test_client.get(f"/api/v1/endpoints/{fake_id}")
        
        assert response.status_code == 404

    def test_list_endpoints(self, test_client: TestClient, sample_endpoint_data, test_data_factory):
        """Test listing endpoints."""
        # Create multiple endpoints
        endpoint1_data = test_data_factory.create_endpoint_data("ftp", name="FTP Server 1")
        endpoint2_data = test_data_factory.create_endpoint_data("sftp", name="SFTP Server 1")
        
        test_client.post("/api/v1/endpoints/", json=endpoint1_data)
        test_client.post("/api/v1/endpoints/", json=endpoint2_data)
        
        # List endpoints
        response = test_client.get("/api/v1/endpoints/")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        
        # Check that both endpoints are in the list
        names = [endpoint["name"] for endpoint in data]
        assert "FTP Server 1" in names
        assert "SFTP Server 1" in names

    def test_update_endpoint_success(self, test_client: TestClient, sample_endpoint_data):
        """Test successful endpoint update."""
        # Create endpoint
        create_response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        endpoint_id = create_response.json()["id"]
        
        # Update endpoint
        update_data = {
            "name": "Updated FTP Server",
            "is_active": False
        }
        response = test_client.put(f"/api/v1/endpoints/{endpoint_id}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated FTP Server"
        assert data["is_active"] is False

    def test_update_endpoint_not_found(self, test_client: TestClient):
        """Test updating non-existent endpoint."""
        fake_id = str(uuid4())
        update_data = {"name": "Updated Name"}
        
        response = test_client.put(f"/api/v1/endpoints/{fake_id}", json=update_data)
        
        assert response.status_code == 404

    def test_delete_endpoint_success(self, test_client: TestClient, sample_endpoint_data):
        """Test successful endpoint deletion."""
        # Create endpoint
        create_response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        endpoint_id = create_response.json()["id"]
        
        # Delete endpoint
        response = test_client.delete(f"/api/v1/endpoints/{endpoint_id}")
        
        assert response.status_code == 204
        
        # Verify it's deleted
        get_response = test_client.get(f"/api/v1/endpoints/{endpoint_id}")
        assert get_response.status_code == 404

    def test_delete_endpoint_not_found(self, test_client: TestClient):
        """Test deleting non-existent endpoint."""
        fake_id = str(uuid4())
        response = test_client.delete(f"/api/v1/endpoints/{fake_id}")
        
        assert response.status_code == 404

    def test_test_endpoint_connection_success(self, test_client: TestClient, sample_endpoint_data):
        """Test endpoint connection testing."""
        # Create endpoint
        create_response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        endpoint_id = create_response.json()["id"]
        
        # Mock successful connection test
        with pytest.mock.patch('app.api.v1.endpoints.test_endpoint_connection') as mock_test:
            mock_test.return_value = {"status": "success", "message": "Connection successful"}
            
            response = test_client.post(f"/api/v1/endpoints/{endpoint_id}/test")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"

    def test_test_endpoint_connection_failure(self, test_client: TestClient, sample_endpoint_data):
        """Test endpoint connection testing failure."""
        # Create endpoint
        create_response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        endpoint_id = create_response.json()["id"]
        
        # Mock failed connection test
        with pytest.mock.patch('app.api.v1.endpoints.test_endpoint_connection') as mock_test:
            mock_test.return_value = {"status": "error", "message": "Connection failed"}
            
            response = test_client.post(f"/api/v1/endpoints/{endpoint_id}/test")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"

    def test_get_endpoint_statistics(self, test_client: TestClient, sample_endpoint_data):
        """Test getting endpoint statistics."""
        # Create endpoint
        create_response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        endpoint_id = create_response.json()["id"]
        
        response = test_client.get(f"/api/v1/endpoints/{endpoint_id}/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_sessions" in data
        assert "total_executions" in data
        assert "last_used" in data

    def test_list_endpoints_with_filters(self, test_client: TestClient, test_data_factory):
        """Test listing endpoints with filters."""
        # Create endpoints of different types
        ftp_data = test_data_factory.create_endpoint_data("ftp", name="FTP Server")
        sftp_data = test_data_factory.create_endpoint_data("sftp", name="SFTP Server")
        
        test_client.post("/api/v1/endpoints/", json=ftp_data)
        test_client.post("/api/v1/endpoints/", json=sftp_data)
        
        # Filter by endpoint type
        response = test_client.get("/api/v1/endpoints/?endpoint_type=ftp")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(endpoint["endpoint_type"] == "ftp" for endpoint in data)

    def test_list_endpoints_with_pagination(self, test_client: TestClient, test_data_factory):
        """Test listing endpoints with pagination."""
        # Create multiple endpoints
        for i in range(5):
            endpoint_data = test_data_factory.create_endpoint_data("ftp", name=f"FTP Server {i}")
            test_client.post("/api/v1/endpoints/", json=endpoint_data)
        
        # Test pagination
        response = test_client.get("/api/v1/endpoints/?skip=0&limit=3")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 3

    def test_endpoint_password_encryption(self, test_client: TestClient, sample_endpoint_data):
        """Test that endpoint passwords are encrypted in database."""
        # Create endpoint
        response = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        endpoint_id = response.json()["id"]
        
        # Verify password is not returned in API response
        get_response = test_client.get(f"/api/v1/endpoints/{endpoint_id}")
        data = get_response.json()
        assert "password" not in data
        
        # The actual encryption test would require database access
        # This is more of a contract test

    def test_create_s3_endpoint(self, test_client: TestClient):
        """Test creating S3 endpoint with specific fields."""
        s3_data = {
            "name": "Test S3 Bucket",
            "endpoint_type": "s3",
            "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "bucket_name": "test-bucket",
            "region": "us-east-1",
            "is_active": True
        }
        
        response = test_client.post("/api/v1/endpoints/", json=s3_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["endpoint_type"] == "s3"
        assert data["bucket_name"] == "test-bucket"
        assert data["region"] == "us-east-1"
        assert "aws_secret_access_key" not in data  # Should not be returned

    def test_create_local_endpoint(self, test_client: TestClient):
        """Test creating local endpoint."""
        local_data = {
            "name": "Local Storage",
            "endpoint_type": "local",
            "base_path": "/local/storage/path",
            "is_active": True
        }
        
        response = test_client.post("/api/v1/endpoints/", json=local_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["endpoint_type"] == "local"
        assert data["base_path"] == "/local/storage/path"

    def test_endpoint_validation_rules(self, test_client: TestClient):
        """Test endpoint validation rules."""
        # Test FTP endpoint without required fields
        invalid_ftp = {
            "name": "Invalid FTP",
            "endpoint_type": "ftp",
            # Missing host, username, password
        }
        
        response = test_client.post("/api/v1/endpoints/", json=invalid_ftp)
        assert response.status_code == 422
        
        # Test S3 endpoint without required fields
        invalid_s3 = {
            "name": "Invalid S3",
            "endpoint_type": "s3",
            # Missing bucket_name, aws credentials
        }
        
        response = test_client.post("/api/v1/endpoints/", json=invalid_s3)
        assert response.status_code == 422

    def test_endpoint_name_uniqueness(self, test_client: TestClient, sample_endpoint_data):
        """Test that endpoint names must be unique."""
        # Create first endpoint
        response1 = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        assert response1.status_code == 201
        
        # Try to create another endpoint with same name
        response2 = test_client.post("/api/v1/endpoints/", json=sample_endpoint_data)
        assert response2.status_code == 400  # Should fail due to name conflict
