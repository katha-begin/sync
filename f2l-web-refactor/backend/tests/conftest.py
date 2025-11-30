"""
Pytest configuration and shared fixtures.
"""
import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config import settings
from app.database.models import Base
from app.database.session import get_async_session
from app.main import app


# Test database URL (use in-memory SQLite for tests)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True
    )
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Clean up
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture
def test_client(test_session):
    """Create test client with database session override."""
    def override_get_async_session():
        return test_session
    
    app.dependency_overrides[get_async_session] = override_get_async_session
    
    with TestClient(app) as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def temp_directory() -> Generator[Path, None, None]:
    """Create temporary directory for testing."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_ftp_connection():
    """Mock FTP connection for testing."""
    mock_ftp = MagicMock()
    mock_ftp.connect.return_value = None
    mock_ftp.login.return_value = None
    mock_ftp.quit.return_value = None
    mock_ftp.close.return_value = None
    mock_ftp.pwd.return_value = "/"
    mock_ftp.nlst.return_value = ["file1.txt", "file2.txt", "subdir"]
    mock_ftp.size.return_value = 1024
    mock_ftp.voidcmd.return_value = "213 20240101120000"
    mock_ftp.retrbinary.return_value = None
    mock_ftp.storbinary.return_value = None
    mock_ftp.delete.return_value = None
    
    return mock_ftp


@pytest.fixture
def mock_sftp_connection():
    """Mock SFTP connection for testing."""
    mock_sftp = MagicMock()
    mock_sftp.connect.return_value = None
    mock_sftp.close.return_value = None
    mock_sftp.listdir.return_value = ["file1.txt", "file2.txt", "subdir"]
    mock_sftp.listdir_attr.return_value = []
    mock_sftp.stat.return_value = MagicMock(st_size=1024, st_mtime=1704110400)
    mock_sftp.get.return_value = None
    mock_sftp.put.return_value = None
    mock_sftp.remove.return_value = None
    
    return mock_sftp


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        'Contents': [
            {
                'Key': 'file1.txt',
                'Size': 1024,
                'LastModified': '2024-01-01T12:00:00Z'
            },
            {
                'Key': 'file2.txt',
                'Size': 2048,
                'LastModified': '2024-01-01T12:30:00Z'
            }
        ]
    }
    mock_s3.head_object.return_value = {
        'ContentLength': 1024,
        'LastModified': '2024-01-01T12:00:00Z'
    }
    mock_s3.download_file.return_value = None
    mock_s3.upload_file.return_value = None
    mock_s3.delete_object.return_value = None
    
    return mock_s3


@pytest.fixture
def sample_endpoint_data():
    """Sample endpoint data for testing."""
    return {
        "name": "Test FTP Server",
        "endpoint_type": "ftp",
        "host": "ftp.example.com",
        "port": 21,
        "username": "testuser",
        "password": "testpass",
        "base_path": "/test/path",
        "is_active": True
    }


@pytest.fixture
def sample_session_data():
    """Sample session data for testing."""
    return {
        "name": "Test Sync Session",
        "source_endpoint_id": None,  # Will be set in tests
        "destination_endpoint_id": None,  # Will be set in tests
        "source_path": "/source/path",
        "destination_path": "/dest/path",
        "sync_direction": "source_to_destination",
        "is_active": True,
        "schedule_enabled": False
    }


@pytest.fixture
def sample_file_metadata():
    """Sample file metadata for testing."""
    return {
        "name": "test_file.txt",
        "path": "/test/path/test_file.txt",
        "size": 1024,
        "modified_time": "2024-01-01T12:00:00Z",
        "is_directory": False,
        "permissions": "644"
    }


@pytest.fixture
def mock_celery_task():
    """Mock Celery task for testing."""
    mock_task = AsyncMock()
    mock_task.delay.return_value = MagicMock(id="test-task-id")
    mock_task.apply_async.return_value = MagicMock(id="test-task-id")
    return mock_task


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    mock_redis = AsyncMock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = False
    return mock_redis


# Test data factories
class TestDataFactory:
    """Factory for creating test data."""
    
    @staticmethod
    def create_endpoint_data(endpoint_type: str = "ftp", **kwargs):
        """Create endpoint test data."""
        base_data = {
            "name": f"Test {endpoint_type.upper()} Server",
            "endpoint_type": endpoint_type,
            "host": f"{endpoint_type}.example.com",
            "port": 21 if endpoint_type == "ftp" else 22,
            "username": "testuser",
            "password": "testpass",
            "base_path": "/test/path",
            "is_active": True
        }
        base_data.update(kwargs)
        return base_data
    
    @staticmethod
    def create_session_data(source_id=None, dest_id=None, **kwargs):
        """Create session test data."""
        base_data = {
            "name": "Test Sync Session",
            "source_endpoint_id": source_id,
            "destination_endpoint_id": dest_id,
            "source_path": "/source/path",
            "destination_path": "/dest/path",
            "sync_direction": "source_to_destination",
            "is_active": True,
            "schedule_enabled": False
        }
        base_data.update(kwargs)
        return base_data
    
    @staticmethod
    def create_file_metadata(name: str = "test_file.txt", **kwargs):
        """Create file metadata test data."""
        base_data = {
            "name": name,
            "path": f"/test/path/{name}",
            "size": 1024,
            "modified_time": "2024-01-01T12:00:00Z",
            "is_directory": False,
            "permissions": "644"
        }
        base_data.update(kwargs)
        return base_data


@pytest.fixture
def test_data_factory():
    """Test data factory fixture."""
    return TestDataFactory


# Async test helpers
class AsyncTestHelpers:
    """Helper methods for async testing."""
    
    @staticmethod
    async def create_test_endpoint(session: AsyncSession, endpoint_data: dict):
        """Create test endpoint in database."""
        from app.repositories.endpoint_repository import EndpointRepository
        
        repo = EndpointRepository(session)
        return await repo.create(endpoint_data)
    
    @staticmethod
    async def create_test_session(session: AsyncSession, session_data: dict):
        """Create test session in database."""
        from app.repositories.session_repository import SessionRepository
        
        repo = SessionRepository(session)
        return await repo.create(session_data)


@pytest.fixture
def async_test_helpers():
    """Async test helpers fixture."""
    return AsyncTestHelpers


# Mock settings for testing
@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    test_settings = MagicMock()
    test_settings.DATABASE_URL = TEST_DATABASE_URL
    test_settings.REDIS_URL = "redis://localhost:6379/1"
    test_settings.TEMP_DIR = "/tmp/f2l_test"
    test_settings.LOG_LEVEL = "DEBUG"
    test_settings.DEBUG = True
    test_settings.is_production = False
    test_settings.is_development = True
    test_settings.FTP_TIMEOUT_SECONDS = 30
    test_settings.SFTP_TIMEOUT_SECONDS = 30
    test_settings.S3_TIMEOUT_SECONDS = 60
    test_settings.MAX_RETRY_ATTEMPTS = 3
    test_settings.RETRY_DELAY_SECONDS = 1
    test_settings.CHUNK_SIZE_BYTES = 8192
    test_settings.MAX_CONCURRENT_TRANSFERS = 5
    
    return test_settings


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    # Add custom markers
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "e2e: mark test as an end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Test collection configuration
def pytest_collection_modifyitems(config, items):
    """Modify test collection."""
    # Add markers based on test file location
    for item in items:
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
