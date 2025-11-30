"""
MetadataEngine - File metadata comparison engine for F2L Web Refactor.
Ported from original f2l_complete.py with enhanced comparison logic.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import os
import logging

logger = logging.getLogger(__name__)


class SyncOperation(Enum):
    """Sync operation types."""
    DOWNLOAD = "download"
    UPLOAD = "upload"
    SKIP = "skip"
    CONFLICT = "conflict"


class SyncDirection(Enum):
    """Sync direction types."""
    FTP_TO_LOCAL = "ftp_to_local"
    LOCAL_TO_FTP = "local_to_ftp"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class FileMetadata:
    """File metadata container."""
    path: str
    size: int
    modified: Optional[datetime]
    exists: bool = True


@dataclass
class ComparisonResult:
    """File comparison result."""
    operation: SyncOperation
    reason: str
    source_metadata: Optional[FileMetadata] = None
    destination_metadata: Optional[FileMetadata] = None


class MetadataEngine:
    """
    File metadata comparison engine.
    
    Features:
    - Size and modification time comparison
    - Conflict detection and resolution
    - Support for force overwrite mode
    - Bidirectional sync logic
    - Main source priority handling
    """

    def __init__(self):
        """Initialize MetadataEngine."""
        logger.info("MetadataEngine initialized")

    def compare_files(
        self,
        source_metadata: Optional[FileMetadata],
        destination_metadata: Optional[FileMetadata],
        sync_direction: SyncDirection,
        source_is_main: bool = True,
        force_overwrite: bool = False
    ) -> ComparisonResult:
        """
        Compare two files and determine sync operation.
        
        Args:
            source_metadata: Source file metadata (None if doesn't exist)
            destination_metadata: Destination file metadata (None if doesn't exist)
            sync_direction: Direction of sync operation
            source_is_main: Whether source is the main/authoritative source
            force_overwrite: If True, always sync regardless of metadata
            
        Returns:
            ComparisonResult with operation and reason
        """
        # Handle force overwrite mode
        if force_overwrite:
            if sync_direction == SyncDirection.FTP_TO_LOCAL:
                return ComparisonResult(
                    operation=SyncOperation.DOWNLOAD,
                    reason="Force overwrite enabled",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            elif sync_direction == SyncDirection.LOCAL_TO_FTP:
                return ComparisonResult(
                    operation=SyncOperation.UPLOAD,
                    reason="Force overwrite enabled",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            elif sync_direction == SyncDirection.BIDIRECTIONAL:
                # In bidirectional mode with force, prefer main source
                operation = SyncOperation.DOWNLOAD if source_is_main else SyncOperation.UPLOAD
                return ComparisonResult(
                    operation=operation,
                    reason="Force overwrite enabled (main source priority)",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )

        # Handle missing files
        if not source_metadata or not source_metadata.exists:
            if sync_direction == SyncDirection.LOCAL_TO_FTP:
                return ComparisonResult(
                    operation=SyncOperation.SKIP,
                    reason="Source file does not exist",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            else:
                return ComparisonResult(
                    operation=SyncOperation.SKIP,
                    reason="Source file does not exist",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )

        if not destination_metadata or not destination_metadata.exists:
            if sync_direction == SyncDirection.FTP_TO_LOCAL:
                return ComparisonResult(
                    operation=SyncOperation.DOWNLOAD,
                    reason="Destination file does not exist",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            elif sync_direction == SyncDirection.LOCAL_TO_FTP:
                return ComparisonResult(
                    operation=SyncOperation.UPLOAD,
                    reason="Destination file does not exist",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            else:  # BIDIRECTIONAL
                operation = SyncOperation.DOWNLOAD if source_is_main else SyncOperation.UPLOAD
                return ComparisonResult(
                    operation=operation,
                    reason="Destination file does not exist",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )

        # Both files exist - compare metadata
        return self._compare_existing_files(
            source_metadata, destination_metadata, sync_direction, source_is_main
        )

    def _compare_existing_files(
        self,
        source_metadata: FileMetadata,
        destination_metadata: FileMetadata,
        sync_direction: SyncDirection,
        source_is_main: bool
    ) -> ComparisonResult:
        """
        Compare two existing files based on metadata.
        
        Args:
            source_metadata: Source file metadata
            destination_metadata: Destination file metadata
            sync_direction: Direction of sync operation
            source_is_main: Whether source is the main/authoritative source
            
        Returns:
            ComparisonResult with operation and reason
        """
        # Compare modification times
        if source_metadata.modified and destination_metadata.modified:
            source_time = source_metadata.modified
            dest_time = destination_metadata.modified
            
            # Handle timezone-naive datetimes by assuming UTC
            if source_time.tzinfo is None:
                source_time = source_time.replace(tzinfo=timezone.utc)
            if dest_time.tzinfo is None:
                dest_time = dest_time.replace(tzinfo=timezone.utc)
            
            time_diff = abs((source_time - dest_time).total_seconds())
            
            # Consider files with same modification time if within 1 second
            if time_diff <= 1:
                # Same modification time, check size
                return self._compare_file_sizes(
                    source_metadata, destination_metadata, sync_direction, source_is_main
                )
            elif source_time > dest_time:
                # Source is newer
                return self._handle_newer_source(
                    source_metadata, destination_metadata, sync_direction, source_is_main
                )
            else:
                # Destination is newer
                return self._handle_newer_destination(
                    source_metadata, destination_metadata, sync_direction, source_is_main
                )
        else:
            # Cannot compare modification times, compare sizes
            return self._compare_file_sizes(
                source_metadata, destination_metadata, sync_direction, source_is_main
            )

    def _compare_file_sizes(
        self,
        source_metadata: FileMetadata,
        destination_metadata: FileMetadata,
        sync_direction: SyncDirection,
        source_is_main: bool
    ) -> ComparisonResult:
        """Compare file sizes when modification times are equal or unavailable."""
        if source_metadata.size != destination_metadata.size:
            if sync_direction == SyncDirection.FTP_TO_LOCAL:
                if source_is_main:
                    return ComparisonResult(
                        operation=SyncOperation.DOWNLOAD,
                        reason=f"Different file sizes (source: {source_metadata.size}, dest: {destination_metadata.size}) - source is main",
                        source_metadata=source_metadata,
                        destination_metadata=destination_metadata
                    )
                else:
                    return ComparisonResult(
                        operation=SyncOperation.CONFLICT,
                        reason=f"Different file sizes (source: {source_metadata.size}, dest: {destination_metadata.size}) - conflict",
                        source_metadata=source_metadata,
                        destination_metadata=destination_metadata
                    )
            elif sync_direction == SyncDirection.LOCAL_TO_FTP:
                if not source_is_main:
                    return ComparisonResult(
                        operation=SyncOperation.UPLOAD,
                        reason=f"Different file sizes (source: {source_metadata.size}, dest: {destination_metadata.size}) - destination is main",
                        source_metadata=source_metadata,
                        destination_metadata=destination_metadata
                    )
                else:
                    return ComparisonResult(
                        operation=SyncOperation.CONFLICT,
                        reason=f"Different file sizes (source: {source_metadata.size}, dest: {destination_metadata.size}) - conflict",
                        source_metadata=source_metadata,
                        destination_metadata=destination_metadata
                    )
            else:  # BIDIRECTIONAL
                if source_is_main:
                    return ComparisonResult(
                        operation=SyncOperation.DOWNLOAD,
                        reason=f"Different file sizes (source: {source_metadata.size}, dest: {destination_metadata.size}) - source is main",
                        source_metadata=source_metadata,
                        destination_metadata=destination_metadata
                    )
                else:
                    return ComparisonResult(
                        operation=SyncOperation.UPLOAD,
                        reason=f"Different file sizes (source: {source_metadata.size}, dest: {destination_metadata.size}) - destination is main",
                        source_metadata=source_metadata,
                        destination_metadata=destination_metadata
                    )
        
        # Files are identical
        return ComparisonResult(
            operation=SyncOperation.SKIP,
            reason="Files are identical (same size and modification time)",
            source_metadata=source_metadata,
            destination_metadata=destination_metadata
        )

    def _handle_newer_source(
        self,
        source_metadata: FileMetadata,
        destination_metadata: FileMetadata,
        sync_direction: SyncDirection,
        source_is_main: bool
    ) -> ComparisonResult:
        """Handle case where source file is newer."""
        if sync_direction == SyncDirection.FTP_TO_LOCAL:
            if source_is_main or sync_direction == SyncDirection.FTP_TO_LOCAL:
                return ComparisonResult(
                    operation=SyncOperation.DOWNLOAD,
                    reason="Source file is newer",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            else:
                return ComparisonResult(
                    operation=SyncOperation.CONFLICT,
                    reason="Source file is newer but not main source",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
        elif sync_direction == SyncDirection.LOCAL_TO_FTP:
            return ComparisonResult(
                operation=SyncOperation.UPLOAD,
                reason="Source file is newer",
                source_metadata=source_metadata,
                destination_metadata=destination_metadata
            )
        else:  # BIDIRECTIONAL
            operation = SyncOperation.DOWNLOAD if source_is_main else SyncOperation.UPLOAD
            return ComparisonResult(
                operation=operation,
                reason="Source file is newer",
                source_metadata=source_metadata,
                destination_metadata=destination_metadata
            )

    def _handle_newer_destination(
        self,
        source_metadata: FileMetadata,
        destination_metadata: FileMetadata,
        sync_direction: SyncDirection,
        source_is_main: bool
    ) -> ComparisonResult:
        """Handle case where destination file is newer."""
        if sync_direction == SyncDirection.FTP_TO_LOCAL:
            return ComparisonResult(
                operation=SyncOperation.SKIP,
                reason="Destination file is newer",
                source_metadata=source_metadata,
                destination_metadata=destination_metadata
            )
        elif sync_direction == SyncDirection.LOCAL_TO_FTP:
            if not source_is_main:
                return ComparisonResult(
                    operation=SyncOperation.SKIP,
                    reason="Destination file is newer and is main source",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            else:
                return ComparisonResult(
                    operation=SyncOperation.CONFLICT,
                    reason="Destination file is newer but source is main",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
        else:  # BIDIRECTIONAL
            if source_is_main:
                return ComparisonResult(
                    operation=SyncOperation.SKIP,
                    reason="Destination file is newer but source is main",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )
            else:
                return ComparisonResult(
                    operation=SyncOperation.SKIP,
                    reason="Destination file is newer",
                    source_metadata=source_metadata,
                    destination_metadata=destination_metadata
                )

    def get_local_file_metadata(self, local_path: str) -> Optional[FileMetadata]:
        """
        Get metadata for local file.
        
        Args:
            local_path: Local file path
            
        Returns:
            FileMetadata object or None if file doesn't exist
        """
        try:
            if not os.path.exists(local_path):
                return FileMetadata(path=local_path, size=0, modified=None, exists=False)
            
            stat_info = os.stat(local_path)
            modified = datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc)
            
            return FileMetadata(
                path=local_path,
                size=stat_info.st_size,
                modified=modified,
                exists=True
            )
        except Exception as e:
            logger.error(f"Error getting local file metadata for {local_path}: {e}")
            return None
