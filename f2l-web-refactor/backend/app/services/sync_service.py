"""
Sync Service - Business logic for file synchronization operations.
"""
import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timezone

from app.repositories.endpoint_repository import EndpointRepository
from app.core.metadata_engine import MetadataEngine, SyncDirection, FileMetadata, ComparisonResult
from app.services.endpoint_service import EndpointService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SyncService:
    """Service for sync operation business logic."""

    def __init__(self, db: AsyncSession):
        """Initialize service with database session."""
        self.db = db
        self.endpoint_repo = EndpointRepository(db)
        self.endpoint_service = EndpointService(db)
        self.metadata_engine = MetadataEngine()

    async def compare_files_metadata(
        self,
        source_endpoint_id: UUID,
        destination_endpoint_id: UUID,
        source_path: str,
        destination_path: str,
        sync_direction: SyncDirection,
        force_overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Compare file metadata between two endpoints.
        
        Args:
            source_endpoint_id: Source endpoint UUID
            destination_endpoint_id: Destination endpoint UUID
            source_path: Path to source file
            destination_path: Path to destination file
            sync_direction: Direction of sync
            force_overwrite: Whether to force overwrite
            
        Returns:
            Dictionary with comparison results
        """
        try:
            logger.info(f"Comparing metadata: {source_path} -> {destination_path}")
            
            # Get metadata from both endpoints
            source_metadata_result = await self.endpoint_service.get_file_metadata(
                source_endpoint_id, source_path
            )
            
            dest_metadata_result = await self.endpoint_service.get_file_metadata(
                destination_endpoint_id, destination_path
            )
            
            # Convert to FileMetadata objects
            source_metadata = None
            if source_metadata_result['success']:
                metadata = source_metadata_result['metadata']
                source_metadata = FileMetadata(
                    path=source_path,
                    size=metadata.get('size', 0),
                    modified=metadata.get('modified'),
                    exists=metadata.get('exists', True)
                )
            
            dest_metadata = None
            if dest_metadata_result['success']:
                metadata = dest_metadata_result['metadata']
                dest_metadata = FileMetadata(
                    path=destination_path,
                    size=metadata.get('size', 0),
                    modified=metadata.get('modified'),
                    exists=metadata.get('exists', True)
                )
            
            # Compare using metadata engine
            comparison = self.metadata_engine.compare_files(
                source_metadata=source_metadata,
                destination_metadata=dest_metadata,
                sync_direction=sync_direction,
                source_is_main=True,
                force_overwrite=force_overwrite
            )
            
            result = {
                'success': True,
                'source_path': source_path,
                'destination_path': destination_path,
                'source_metadata': {
                    'exists': source_metadata.exists if source_metadata else False,
                    'size': source_metadata.size if source_metadata else 0,
                    'modified': source_metadata.modified.isoformat() if source_metadata and source_metadata.modified else None
                },
                'destination_metadata': {
                    'exists': dest_metadata.exists if dest_metadata else False,
                    'size': dest_metadata.size if dest_metadata else 0,
                    'modified': dest_metadata.modified.isoformat() if dest_metadata and dest_metadata.modified else None
                },
                'comparison_result': {
                    'operation': comparison.operation.value,
                    'reason': comparison.reason,
                    'needs_sync': comparison.operation.value != 'skip'
                },
                'sync_direction': sync_direction.value,
                'force_overwrite': force_overwrite
            }
            
            logger.info(f"Metadata comparison result: {comparison.operation.value} - {comparison.reason}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to compare file metadata: {e}")
            return {
                'success': False,
                'message': str(e),
                'source_path': source_path,
                'destination_path': destination_path
            }

    async def analyze_directory_sync(
        self,
        source_endpoint_id: UUID,
        destination_endpoint_id: UUID,
        source_path: str,
        destination_path: str,
        sync_direction: SyncDirection,
        folder_filter: Optional[str] = None,
        file_filter: Optional[str] = None,
        exclude_patterns: Optional[str] = None,
        max_depth: int = 5,
        force_overwrite: bool = False,
        delete_extra_files: bool = False
    ) -> Dict[str, Any]:
        """
        Analyze what sync operations would be needed for a directory.
        
        Args:
            source_endpoint_id: Source endpoint UUID
            destination_endpoint_id: Destination endpoint UUID
            source_path: Source directory path
            destination_path: Destination directory path
            sync_direction: Direction of sync
            folder_filter: Folder filter pattern
            file_filter: File filter pattern
            exclude_patterns: Exclude patterns
            max_depth: Maximum directory depth
            force_overwrite: Whether to force overwrite
            delete_extra_files: Whether to delete extra files
            
        Returns:
            Dictionary with sync analysis results
        """
        try:
            logger.info(f"Analyzing directory sync: {source_path} -> {destination_path}")
            
            # Browse source directory
            source_browse_result = await self.endpoint_service.browse_endpoint_directory(
                source_endpoint_id, source_path, max_depth
            )
            
            if not source_browse_result['success']:
                raise ValueError(f"Failed to browse source directory: {source_browse_result['message']}")
            
            # Browse destination directory
            dest_browse_result = await self.endpoint_service.browse_endpoint_directory(
                destination_endpoint_id, destination_path, max_depth
            )
            
            if not dest_browse_result['success']:
                logger.warning(f"Failed to browse destination directory: {dest_browse_result['message']}")
                dest_files = []
            else:
                dest_files = dest_browse_result['files']
            
            source_files = source_browse_result['files']
            
            # Apply filters
            filtered_source_files = self._apply_filters(
                source_files, folder_filter, file_filter, exclude_patterns
            )
            
            filtered_dest_files = self._apply_filters(
                dest_files, folder_filter, file_filter, exclude_patterns
            )
            
            # Analyze sync operations
            sync_operations = await self._analyze_sync_operations(
                source_files=filtered_source_files,
                dest_files=filtered_dest_files,
                sync_direction=sync_direction,
                force_overwrite=force_overwrite,
                delete_extra_files=delete_extra_files
            )
            
            # Calculate statistics
            stats = self._calculate_sync_statistics(sync_operations)
            
            result = {
                'success': True,
                'source_path': source_path,
                'destination_path': destination_path,
                'source_files_found': len(source_files),
                'destination_files_found': len(dest_files),
                'source_files_filtered': len(filtered_source_files),
                'destination_files_filtered': len(filtered_dest_files),
                'sync_operations': sync_operations,
                'statistics': stats,
                'sync_direction': sync_direction.value,
                'force_overwrite': force_overwrite,
                'delete_extra_files': delete_extra_files,
                'filters': {
                    'folder_filter': folder_filter,
                    'file_filter': file_filter,
                    'exclude_patterns': exclude_patterns
                }
            }
            
            logger.info(f"Directory sync analysis completed: {stats['total_operations']} operations planned")
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze directory sync: {e}")
            return {
                'success': False,
                'message': str(e),
                'source_path': source_path,
                'destination_path': destination_path
            }

    async def preview_sync_operations(
        self,
        source_endpoint_id: UUID,
        destination_endpoint_id: UUID,
        file_paths: List[Tuple[str, str]],  # List of (source_path, dest_path) tuples
        sync_direction: SyncDirection,
        force_overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Preview sync operations for specific files.
        
        Args:
            source_endpoint_id: Source endpoint UUID
            destination_endpoint_id: Destination endpoint UUID
            file_paths: List of (source_path, dest_path) tuples
            sync_direction: Direction of sync
            force_overwrite: Whether to force overwrite
            
        Returns:
            Dictionary with preview results
        """
        try:
            logger.info(f"Previewing sync operations for {len(file_paths)} files")
            
            preview_results = []
            
            for source_path, dest_path in file_paths:
                try:
                    comparison_result = await self.compare_files_metadata(
                        source_endpoint_id=source_endpoint_id,
                        destination_endpoint_id=destination_endpoint_id,
                        source_path=source_path,
                        destination_path=dest_path,
                        sync_direction=sync_direction,
                        force_overwrite=force_overwrite
                    )
                    
                    preview_results.append(comparison_result)
                    
                except Exception as e:
                    logger.error(f"Failed to preview {source_path} -> {dest_path}: {e}")
                    preview_results.append({
                        'success': False,
                        'message': str(e),
                        'source_path': source_path,
                        'destination_path': dest_path
                    })
            
            # Calculate summary statistics
            successful_previews = [r for r in preview_results if r['success']]
            operations_needed = [r for r in successful_previews if r.get('comparison_result', {}).get('needs_sync', False)]
            
            operation_counts = {}
            for result in operations_needed:
                op_type = result.get('comparison_result', {}).get('operation', 'unknown')
                operation_counts[op_type] = operation_counts.get(op_type, 0) + 1
            
            summary = {
                'total_files': len(file_paths),
                'successful_previews': len(successful_previews),
                'failed_previews': len(file_paths) - len(successful_previews),
                'operations_needed': len(operations_needed),
                'no_sync_needed': len(successful_previews) - len(operations_needed),
                'operation_breakdown': operation_counts
            }
            
            result = {
                'success': True,
                'preview_results': preview_results,
                'summary': summary,
                'sync_direction': sync_direction.value,
                'force_overwrite': force_overwrite
            }
            
            logger.info(f"Sync preview completed: {summary['operations_needed']} operations needed")
            return result
            
        except Exception as e:
            logger.error(f"Failed to preview sync operations: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def _apply_filters(
        self,
        files: List[Dict[str, Any]],
        folder_filter: Optional[str],
        file_filter: Optional[str],
        exclude_patterns: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Apply filters to file list."""
        # TODO: Implement proper pattern matching
        # For now, return all files
        return files

    async def _analyze_sync_operations(
        self,
        source_files: List[Dict[str, Any]],
        dest_files: List[Dict[str, Any]],
        sync_direction: SyncDirection,
        force_overwrite: bool,
        delete_extra_files: bool
    ) -> List[Dict[str, Any]]:
        """Analyze what sync operations are needed."""
        operations = []
        
        # Create lookup for destination files
        dest_file_map = {f['path']: f for f in dest_files}
        
        # Analyze source files
        for source_file in source_files:
            if not source_file.get('is_file', True):
                continue  # Skip directories
            
            source_path = source_file['path']
            dest_file = dest_file_map.get(source_path)
            
            # Convert to FileMetadata objects
            source_metadata = FileMetadata(
                path=source_path,
                size=source_file.get('size', 0),
                modified=source_file.get('modified'),
                exists=True
            )
            
            dest_metadata = None
            if dest_file:
                dest_metadata = FileMetadata(
                    path=source_path,
                    size=dest_file.get('size', 0),
                    modified=dest_file.get('modified'),
                    exists=True
                )
            
            # Use metadata engine to determine operation
            comparison = self.metadata_engine.compare_files(
                source_metadata=source_metadata,
                destination_metadata=dest_metadata,
                sync_direction=sync_direction,
                source_is_main=True,
                force_overwrite=force_overwrite
            )
            
            if comparison.operation.value != 'skip':
                operations.append({
                    'operation': comparison.operation.value,
                    'source_path': source_path,
                    'dest_path': source_path,
                    'source_size': source_metadata.size,
                    'dest_size': dest_metadata.size if dest_metadata else 0,
                    'source_modified': source_metadata.modified.isoformat() if source_metadata.modified else None,
                    'dest_modified': dest_metadata.modified.isoformat() if dest_metadata and dest_metadata.modified else None,
                    'reason': comparison.reason
                })
        
        # Handle extra files in destination (for deletion)
        if delete_extra_files:
            source_file_paths = {f['path'] for f in source_files}
            
            for dest_file in dest_files:
                if not dest_file.get('is_file', True):
                    continue
                
                dest_path = dest_file['path']
                if dest_path not in source_file_paths:
                    operations.append({
                        'operation': 'delete',
                        'source_path': None,
                        'dest_path': dest_path,
                        'source_size': 0,
                        'dest_size': dest_file.get('size', 0),
                        'source_modified': None,
                        'dest_modified': dest_file.get('modified').isoformat() if dest_file.get('modified') else None,
                        'reason': 'File exists in destination but not in source'
                    })
        
        return operations

    def _calculate_sync_statistics(self, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics for sync operations."""
        stats = {
            'total_operations': len(operations),
            'downloads': 0,
            'uploads': 0,
            'deletes': 0,
            'total_bytes_to_transfer': 0,
            'operation_breakdown': {}
        }
        
        for operation in operations:
            op_type = operation['operation']
            stats['operation_breakdown'][op_type] = stats['operation_breakdown'].get(op_type, 0) + 1
            
            if op_type == 'download':
                stats['downloads'] += 1
                stats['total_bytes_to_transfer'] += operation.get('source_size', 0)
            elif op_type == 'upload':
                stats['uploads'] += 1
                stats['total_bytes_to_transfer'] += operation.get('source_size', 0)
            elif op_type == 'delete':
                stats['deletes'] += 1
        
        return stats

    async def get_sync_recommendations(
        self,
        source_endpoint_id: UUID,
        destination_endpoint_id: UUID,
        source_path: str,
        destination_path: str
    ) -> Dict[str, Any]:
        """
        Get sync recommendations based on endpoint types and file analysis.
        
        Args:
            source_endpoint_id: Source endpoint UUID
            destination_endpoint_id: Destination endpoint UUID
            source_path: Source path
            destination_path: Destination path
            
        Returns:
            Dictionary with sync recommendations
        """
        try:
            # Get endpoint information
            source_endpoint = await self.endpoint_repo.get_by_id(source_endpoint_id)
            dest_endpoint = await self.endpoint_repo.get_by_id(destination_endpoint_id)
            
            if not source_endpoint or not dest_endpoint:
                raise ValueError("One or both endpoints not found")
            
            recommendations = {
                'sync_direction': self._recommend_sync_direction(source_endpoint, dest_endpoint),
                'suggested_filters': self._suggest_filters(source_path),
                'performance_tips': self._get_performance_tips(source_endpoint, dest_endpoint),
                'security_considerations': self._get_security_considerations(source_endpoint, dest_endpoint),
                'estimated_complexity': self._estimate_complexity(source_endpoint, dest_endpoint)
            }
            
            return {
                'success': True,
                'recommendations': recommendations,
                'source_endpoint_type': source_endpoint.endpoint_type.value,
                'destination_endpoint_type': dest_endpoint.endpoint_type.value
            }
            
        except Exception as e:
            logger.error(f"Failed to get sync recommendations: {e}")
            return {
                'success': False,
                'message': str(e)
            }

    def _recommend_sync_direction(self, source_endpoint, dest_endpoint) -> str:
        """Recommend sync direction based on endpoint types."""
        # Simple logic - can be enhanced
        if source_endpoint.endpoint_type.value == 'local':
            return 'local_to_remote'
        elif dest_endpoint.endpoint_type.value == 'local':
            return 'remote_to_local'
        else:
            return 'bidirectional'

    def _suggest_filters(self, path: str) -> Dict[str, str]:
        """Suggest filters based on path patterns."""
        suggestions = {}
        
        # Common exclusion patterns
        suggestions['exclude_patterns'] = '*.tmp,*.log,*.cache,__pycache__,node_modules,.git'
        
        # File type suggestions based on path
        if 'video' in path.lower() or 'media' in path.lower():
            suggestions['file_filter'] = '*.mp4,*.mov,*.avi,*.mkv'
        elif 'image' in path.lower() or 'photo' in path.lower():
            suggestions['file_filter'] = '*.jpg,*.jpeg,*.png,*.tiff,*.raw'
        elif 'document' in path.lower():
            suggestions['file_filter'] = '*.pdf,*.doc,*.docx,*.txt'
        
        return suggestions

    def _get_performance_tips(self, source_endpoint, dest_endpoint) -> List[str]:
        """Get performance tips based on endpoint types."""
        tips = []
        
        if source_endpoint.endpoint_type.value in ['ftp', 'sftp']:
            tips.append("Consider using parallel connections for better throughput")
            tips.append("Large files may benefit from resume capability")
        
        if dest_endpoint.endpoint_type.value == 's3':
            tips.append("Use multipart upload for files larger than 100MB")
            tips.append("Consider S3 Transfer Acceleration for cross-region transfers")
        
        if source_endpoint.endpoint_type.value == 'local' and dest_endpoint.endpoint_type.value == 'local':
            tips.append("Local to local transfers are fastest but consider network storage latency")
        
        return tips

    def _get_security_considerations(self, source_endpoint, dest_endpoint) -> List[str]:
        """Get security considerations based on endpoint types."""
        considerations = []
        
        if source_endpoint.endpoint_type.value == 'ftp':
            considerations.append("FTP transfers are unencrypted - consider SFTP for sensitive data")
        
        if dest_endpoint.endpoint_type.value == 's3':
            considerations.append("Ensure S3 bucket has appropriate access policies")
            considerations.append("Consider enabling S3 encryption at rest")
        
        considerations.append("Verify endpoint credentials are properly secured")
        considerations.append("Monitor sync logs for any unauthorized access attempts")
        
        return considerations

    def _estimate_complexity(self, source_endpoint, dest_endpoint) -> str:
        """Estimate sync complexity based on endpoint types."""
        complexity_score = 0
        
        # Add complexity based on endpoint types
        if source_endpoint.endpoint_type.value in ['ftp', 'sftp']:
            complexity_score += 2
        elif source_endpoint.endpoint_type.value == 's3':
            complexity_score += 3
        else:  # local
            complexity_score += 1
        
        if dest_endpoint.endpoint_type.value in ['ftp', 'sftp']:
            complexity_score += 2
        elif dest_endpoint.endpoint_type.value == 's3':
            complexity_score += 3
        else:  # local
            complexity_score += 1
        
        if complexity_score <= 2:
            return 'low'
        elif complexity_score <= 4:
            return 'medium'
        else:
            return 'high'
