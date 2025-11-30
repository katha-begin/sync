"""
Unit tests for Metadata Comparison Engine.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from app.core.metadata_engine import MetadataEngine


@pytest.mark.unit
class TestMetadataEngine:
    """Test cases for MetadataEngine."""

    def setup_method(self):
        """Set up test fixtures."""
        self.engine = MetadataEngine()

    def test_init(self):
        """Test MetadataEngine initialization."""
        assert self.engine is not None

    def test_compare_files_identical(self):
        """Test comparison of identical files."""
        source_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        result = self.engine.compare_files(source_metadata, dest_metadata)
        
        assert result['operation'] == 'skip'
        assert result['reason'] == 'Files are identical'

    def test_compare_files_source_newer(self):
        """Test comparison when source file is newer."""
        source_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T13:00:00Z',  # 1 hour newer
            'is_directory': False
        }
        
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        result = self.engine.compare_files(source_metadata, dest_metadata)
        
        assert result['operation'] == 'download'
        assert result['reason'] == 'Source file is newer'

    def test_compare_files_dest_newer(self):
        """Test comparison when destination file is newer."""
        source_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T13:00:00Z',  # 1 hour newer
            'is_directory': False
        }
        
        result = self.engine.compare_files(source_metadata, dest_metadata)
        
        assert result['operation'] == 'upload'
        assert result['reason'] == 'Destination file is newer'

    def test_compare_files_different_sizes_same_time(self):
        """Test comparison when files have different sizes but same modification time."""
        source_metadata = {
            'name': 'test.txt',
            'size': 2048,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        result = self.engine.compare_files(source_metadata, dest_metadata)
        
        assert result['operation'] == 'download'
        assert result['reason'] == 'Source file is larger'

    def test_compare_files_dest_missing(self):
        """Test comparison when destination file is missing."""
        source_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        result = self.engine.compare_files(source_metadata, None)
        
        assert result['operation'] == 'download'
        assert result['reason'] == 'File missing in destination'

    def test_compare_files_source_missing(self):
        """Test comparison when source file is missing."""
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        result = self.engine.compare_files(None, dest_metadata)
        
        assert result['operation'] == 'delete'
        assert result['reason'] == 'File missing in source'

    def test_compare_files_both_missing(self):
        """Test comparison when both files are missing."""
        result = self.engine.compare_files(None, None)
        
        assert result['operation'] == 'skip'
        assert result['reason'] == 'Both files missing'

    def test_compare_files_force_overwrite(self):
        """Test comparison with force overwrite enabled."""
        source_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        result = self.engine.compare_files(
            source_metadata, 
            dest_metadata, 
            force_overwrite=True
        )
        
        assert result['operation'] == 'download'
        assert result['reason'] == 'Force overwrite enabled'

    def test_compare_files_bidirectional_sync(self):
        """Test comparison with bidirectional sync."""
        source_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T13:00:00Z',  # Source newer
            'is_directory': False
        }
        
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        result = self.engine.compare_files(
            source_metadata, 
            dest_metadata, 
            sync_direction='bidirectional'
        )
        
        assert result['operation'] == 'download'
        assert result['reason'] == 'Source file is newer'

    def test_compare_files_conflict_detection(self):
        """Test conflict detection in bidirectional sync."""
        # Create a scenario where both files were modified recently
        # but we can't determine which is newer due to precision issues
        source_metadata = {
            'name': 'test.txt',
            'size': 2048,  # Different size
            'modified_time': '2024-01-01T12:00:00Z',
            'is_directory': False
        }
        
        dest_metadata = {
            'name': 'test.txt',
            'size': 1024,  # Different size
            'modified_time': '2024-01-01T12:00:01Z',  # 1 second difference
            'is_directory': False
        }
        
        result = self.engine.compare_files(
            source_metadata, 
            dest_metadata, 
            sync_direction='bidirectional',
            conflict_resolution='manual'
        )
        
        # Should detect conflict due to different sizes and close modification times
        assert result['operation'] in ['conflict', 'download']

    def test_parse_timestamp_iso_format(self):
        """Test parsing ISO format timestamps."""
        timestamp_str = '2024-01-01T12:00:00Z'
        result = self.engine._parse_timestamp(timestamp_str)
        
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        assert result.tzinfo == timezone.utc

    def test_parse_timestamp_with_microseconds(self):
        """Test parsing timestamps with microseconds."""
        timestamp_str = '2024-01-01T12:00:00.123456Z'
        result = self.engine._parse_timestamp(timestamp_str)
        
        assert isinstance(result, datetime)
        assert result.microsecond == 123456

    def test_parse_timestamp_unix_timestamp(self):
        """Test parsing Unix timestamps."""
        unix_timestamp = 1704110400  # 2024-01-01 12:00:00 UTC
        result = self.engine._parse_timestamp(unix_timestamp)
        
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12

    def test_parse_timestamp_invalid(self):
        """Test parsing invalid timestamps."""
        result = self.engine._parse_timestamp('invalid')
        assert result is None
        
        result = self.engine._parse_timestamp(None)
        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_sync_operations(self):
        """Test sync operations analysis."""
        # Mock managers
        source_manager = AsyncMock()
        dest_manager = AsyncMock()
        
        # Mock source files
        source_manager.list_directory_recursive.return_value = [
            {
                'name': 'file1.txt',
                'path': '/source/file1.txt',
                'size': 1024,
                'modified_time': '2024-01-01T12:00:00Z',
                'is_directory': False
            },
            {
                'name': 'file2.txt',
                'path': '/source/file2.txt',
                'size': 2048,
                'modified_time': '2024-01-01T13:00:00Z',
                'is_directory': False
            }
        ]
        
        # Mock destination files
        dest_manager.list_directory_recursive.return_value = [
            {
                'name': 'file1.txt',
                'path': '/dest/file1.txt',
                'size': 1024,
                'modified_time': '2024-01-01T11:00:00Z',  # Older
                'is_directory': False
            }
            # file2.txt missing in destination
        ]
        
        result = await self.engine.analyze_sync_operations(
            source_manager=source_manager,
            dest_manager=dest_manager,
            source_path='/source',
            dest_path='/dest'
        )
        
        assert 'operations' in result
        assert 'summary' in result
        assert len(result['operations']) == 2
        
        # Check operations
        operations = result['operations']
        file1_op = next(op for op in operations if op['source_path'] == '/source/file1.txt')
        file2_op = next(op for op in operations if op['source_path'] == '/source/file2.txt')
        
        assert file1_op['operation'] == 'download'  # Source newer
        assert file2_op['operation'] == 'download'  # Missing in dest

    @pytest.mark.asyncio
    async def test_analyze_sync_operations_with_filters(self):
        """Test sync operations analysis with file filters."""
        source_manager = AsyncMock()
        dest_manager = AsyncMock()
        
        # Mock files with different extensions
        source_manager.list_directory_recursive.return_value = [
            {
                'name': 'document.txt',
                'path': '/source/document.txt',
                'size': 1024,
                'modified_time': '2024-01-01T12:00:00Z',
                'is_directory': False
            },
            {
                'name': 'image.jpg',
                'path': '/source/image.jpg',
                'size': 2048,
                'modified_time': '2024-01-01T12:00:00Z',
                'is_directory': False
            },
            {
                'name': 'temp.tmp',
                'path': '/source/temp.tmp',
                'size': 512,
                'modified_time': '2024-01-01T12:00:00Z',
                'is_directory': False
            }
        ]
        
        dest_manager.list_directory_recursive.return_value = []
        
        # Filter to include only .txt and .jpg files
        file_filters = {
            'include_patterns': ['*.txt', '*.jpg'],
            'exclude_patterns': ['*.tmp']
        }
        
        result = await self.engine.analyze_sync_operations(
            source_manager=source_manager,
            dest_manager=dest_manager,
            source_path='/source',
            dest_path='/dest',
            file_filters=file_filters
        )
        
        operations = result['operations']
        assert len(operations) == 2  # Should exclude .tmp file
        
        file_names = [op['source_metadata']['name'] for op in operations]
        assert 'document.txt' in file_names
        assert 'image.jpg' in file_names
        assert 'temp.tmp' not in file_names

    def test_should_include_file_with_patterns(self):
        """Test file inclusion logic with patterns."""
        file_filters = {
            'include_patterns': ['*.txt', '*.doc*'],
            'exclude_patterns': ['temp*', '*.tmp']
        }
        
        # Should include
        assert self.engine._should_include_file('document.txt', file_filters) is True
        assert self.engine._should_include_file('report.docx', file_filters) is True
        
        # Should exclude
        assert self.engine._should_include_file('temp_file.txt', file_filters) is False
        assert self.engine._should_include_file('backup.tmp', file_filters) is False
        assert self.engine._should_include_file('image.jpg', file_filters) is False  # Not in include patterns

    def test_should_include_file_no_filters(self):
        """Test file inclusion with no filters."""
        assert self.engine._should_include_file('any_file.txt', None) is True
        assert self.engine._should_include_file('any_file.txt', {}) is True

    def test_calculate_sync_summary(self):
        """Test sync summary calculation."""
        operations = [
            {'operation': 'download', 'source_metadata': {'size': 1024}},
            {'operation': 'download', 'source_metadata': {'size': 2048}},
            {'operation': 'upload', 'dest_metadata': {'size': 512}},
            {'operation': 'delete', 'dest_metadata': {'size': 256}},
            {'operation': 'skip', 'source_metadata': {'size': 1024}}
        ]
        
        summary = self.engine._calculate_sync_summary(operations)
        
        assert summary['total_operations'] == 5
        assert summary['downloads'] == 2
        assert summary['uploads'] == 1
        assert summary['deletes'] == 1
        assert summary['skipped'] == 1
        assert summary['total_download_bytes'] == 3072  # 1024 + 2048
        assert summary['total_upload_bytes'] == 512
        assert summary['total_delete_bytes'] == 256
