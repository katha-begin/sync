"""
SQLAlchemy ORM Models for F2L Sync Application.
Implements the complete PostgreSQL schema.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime, Text, JSON, Float,
    ForeignKey, Enum, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
import uuid
import enum


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# Enums
# -----

class EndpointType(str, enum.Enum):
    """Endpoint type enumeration."""
    FTP = "ftp"
    SFTP = "sftp"
    S3 = "s3"
    LOCAL = "local"


class SyncDirection(str, enum.Enum):
    """Sync direction enumeration."""
    SOURCE_TO_DEST = "source_to_dest"
    DEST_TO_SOURCE = "dest_to_source"
    BIDIRECTIONAL = "bidirectional"


class FolderMatchMode(str, enum.Enum):
    """Folder matching mode enumeration."""
    EXACT = "exact"
    CONTAINS = "contains"
    STARTSWITH = "startswith"


class ExecutionStatus(str, enum.Enum):
    """Execution status enumeration."""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationType(str, enum.Enum):
    """Operation type enumeration."""
    UPLOAD = "upload"
    DOWNLOAD = "download"
    DELETE = "delete"
    SKIP = "skip"


class OperationStatus(str, enum.Enum):
    """Operation status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class LogLevel(str, enum.Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class ScheduleUnit(str, enum.Enum):
    """Schedule unit enumeration."""
    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"


# Models
# ------

class Endpoint(Base):
    """
    Endpoint model - Stores FTP/SFTP/S3/Local endpoint configurations.
    """
    __tablename__ = "endpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint_type: Mapped[EndpointType] = mapped_column(Enum(EndpointType, values_callable=lambda x: [e.value for e in x]), nullable=False)

    # FTP/SFTP Fields
    host: Mapped[Optional[str]] = mapped_column(String(255))
    port: Mapped[Optional[int]] = mapped_column(Integer)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    password_encrypted: Mapped[Optional[str]] = mapped_column(Text)  # Fernet encrypted
    remote_path: Mapped[Optional[str]] = mapped_column(String(1024))

    # S3 Fields
    s3_bucket: Mapped[Optional[str]] = mapped_column(String(255))
    s3_region: Mapped[Optional[str]] = mapped_column(String(50))
    s3_access_key: Mapped[Optional[str]] = mapped_column(String(255))
    s3_secret_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)  # Fernet encrypted
    s3_endpoint_url: Mapped[Optional[str]] = mapped_column(String(512))  # For S3-compatible services
    s3_use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)

    # Local Fields
    local_path: Mapped[Optional[str]] = mapped_column(String(1024))

    # Status & Monitoring
    connection_status: Mapped[str] = mapped_column(String(50), default="unknown")  # connected, disconnected, unknown
    last_health_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    health_check_message: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    source_sessions: Mapped[list["SyncSession"]] = relationship(
        "SyncSession", back_populates="source_endpoint", foreign_keys="SyncSession.source_endpoint_id"
    )
    destination_sessions: Mapped[list["SyncSession"]] = relationship(
        "SyncSession", back_populates="destination_endpoint", foreign_keys="SyncSession.destination_endpoint_id"
    )

    # Indexes
    __table_args__ = (
        Index("idx_endpoint_type", "endpoint_type"),
        Index("idx_endpoint_status", "connection_status"),
        Index("idx_endpoint_active", "is_active"),
    )

    def __repr__(self):
        return f"<Endpoint(id={self.id}, name='{self.name}', type={self.endpoint_type})>"


class SyncSession(Base):
    """
    Sync Session model - Stores sync configuration between two endpoints.
    """
    __tablename__ = "sync_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Endpoint References
    source_endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"))
    destination_endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"))

    # Paths
    source_path: Mapped[str] = mapped_column(String(1024), default="/")
    destination_path: Mapped[str] = mapped_column(String(1024), default="/")

    # Sync Configuration
    sync_direction: Mapped[SyncDirection] = mapped_column(Enum(SyncDirection, values_callable=lambda x: [e.value for e in x]), default=SyncDirection.SOURCE_TO_DEST)

    # Folder Filtering
    folder_filter_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    folder_names: Mapped[Optional[list]] = mapped_column(JSONB)  # List of folder names
    folder_match_mode: Mapped[FolderMatchMode] = mapped_column(Enum(FolderMatchMode, values_callable=lambda x: [e.value for e in x]), default=FolderMatchMode.CONTAINS)
    folder_case_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)

    # File Pattern Filtering
    file_pattern_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    file_patterns: Mapped[Optional[list]] = mapped_column(JSONB)  # List of patterns like ["*.jpg", "*.pdf"]

    # Sync Options
    force_overwrite: Mapped[bool] = mapped_column(Boolean, default=False)
    delete_missing: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scheduling
    schedule_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule_interval: Mapped[Optional[int]] = mapped_column(Integer)  # Number value
    schedule_unit: Mapped[Optional[ScheduleUnit]] = mapped_column(Enum(ScheduleUnit, values_callable=lambda x: [e.value for e in x]))  # minutes, hours, days
    auto_start_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_running: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_run_status: Mapped[Optional[str]] = mapped_column(String(50))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    source_endpoint: Mapped["Endpoint"] = relationship("Endpoint", foreign_keys=[source_endpoint_id], back_populates="source_sessions")
    destination_endpoint: Mapped["Endpoint"] = relationship("Endpoint", foreign_keys=[destination_endpoint_id], back_populates="destination_sessions")
    executions: Mapped[list["SyncExecution"]] = relationship("SyncExecution", back_populates="session", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_session_active", "is_active"),
        Index("idx_session_running", "is_running"),
        Index("idx_session_schedule", "schedule_enabled", "next_run_at"),
        CheckConstraint("source_endpoint_id != destination_endpoint_id", name="check_different_endpoints"),
    )

    def __repr__(self):
        return f"<SyncSession(id={self.id}, name='{self.name}', direction={self.sync_direction})>"


class SyncExecution(Base):
    """
    Sync Execution model - Records each execution of a sync session.
    """
    __tablename__ = "sync_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_sessions.id", ondelete="CASCADE"))

    # Execution Details
    status: Mapped[ExecutionStatus] = mapped_column(Enum(ExecutionStatus, values_callable=lambda x: [e.value for e in x]), default=ExecutionStatus.QUEUED)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timing
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)

    # Progress Tracking
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    files_synced: Mapped[int] = mapped_column(Integer, default=0)
    files_failed: Mapped[int] = mapped_column(Integer, default=0)
    files_skipped: Mapped[int] = mapped_column(Integer, default=0)
    bytes_transferred: Mapped[int] = mapped_column(Integer, default=0)
    progress_percentage: Mapped[float] = mapped_column(Float, default=0.0)

    # Current State
    current_file: Mapped[Optional[str]] = mapped_column(String(1024))
    current_operation: Mapped[Optional[str]] = mapped_column(String(50))

    # Results
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_stack_trace: Mapped[Optional[str]] = mapped_column(Text)
    summary: Mapped[Optional[dict]] = mapped_column(JSONB)  # JSON summary of execution

    # Celery Task
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255))

    # Relationships
    session: Mapped["SyncSession"] = relationship("SyncSession", back_populates="executions")
    operations: Mapped[list["SyncOperation"]] = relationship("SyncOperation", back_populates="execution", cascade="all, delete-orphan")
    logs: Mapped[list["Log"]] = relationship("Log", back_populates="execution", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_execution_status", "status"),
        Index("idx_execution_session", "session_id", "queued_at"),
        Index("idx_execution_celery_task", "celery_task_id"),
    )

    def __repr__(self):
        return f"<SyncExecution(id={self.id}, session_id={self.session_id}, status={self.status})>"


class SyncOperation(Base):
    """
    Sync Operation model - Records individual file operations within an execution.
    """
    __tablename__ = "sync_operations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_executions.id", ondelete="CASCADE"))

    # Operation Details
    operation_type: Mapped[OperationType] = mapped_column(Enum(OperationType, values_callable=lambda x: [e.value for e in x]))
    status: Mapped[OperationStatus] = mapped_column(Enum(OperationStatus, values_callable=lambda x: [e.value for e in x]), default=OperationStatus.PENDING)

    # File Details
    source_path: Mapped[str] = mapped_column(String(1024))
    destination_path: Mapped[str] = mapped_column(String(1024))
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_modified_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Execution
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer)  # Milliseconds

    # Result
    bytes_transferred: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    execution: Mapped["SyncExecution"] = relationship("SyncExecution", back_populates="operations")

    # Indexes
    __table_args__ = (
        Index("idx_operation_execution", "execution_id", "status"),
        Index("idx_operation_type", "operation_type"),
    )

    def __repr__(self):
        return f"<SyncOperation(id={self.id}, type={self.operation_type}, status={self.status})>"


class Log(Base):
    """
    Log model - Stores application logs.
    """
    __tablename__ = "logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Log Details
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel, values_callable=lambda x: [e.value for e in x]), default=LogLevel.INFO)
    message: Mapped[str] = mapped_column(Text)
    logger_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Context
    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sync_executions.id", ondelete="CASCADE"))
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    endpoint_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    # Extra Data
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Timing
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    execution: Mapped[Optional["SyncExecution"]] = relationship("SyncExecution", back_populates="logs")

    # Indexes
    __table_args__ = (
        Index("idx_log_level", "level"),
        Index("idx_log_timestamp", "timestamp"),
        Index("idx_log_execution", "execution_id"),
        Index("idx_log_session", "session_id"),
    )

    def __repr__(self):
        return f"<Log(id={self.id}, level={self.level}, message='{self.message[:50]}...')>"


class ScanCache(Base):
    """
    Scan Cache model - Caches directory scan results for performance.
    """
    __tablename__ = "scan_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Cache Key
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"))
    path: Mapped[str] = mapped_column(String(1024))

    # Cache Data
    file_list: Mapped[dict] = mapped_column(JSONB)  # Cached file listing
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    total_size: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)

    # Indexes
    __table_args__ = (
        UniqueConstraint("endpoint_id", "path", name="uq_scan_cache_endpoint_path"),
        Index("idx_scan_cache_expires", "expires_at", "is_valid"),
    )

    def __repr__(self):
        return f"<ScanCache(id={self.id}, endpoint_id={self.endpoint_id}, path='{self.path}')>"


class AppSetting(Base):
    """
    App Setting model - Stores application-level settings as key-value pairs.
    """
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
    value_type: Mapped[str] = mapped_column(String(50), default="string")  # string, int, bool, json
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<AppSetting(key='{self.key}', value='{self.value}')>"


# Shot Download Models
# --------------------

class ShotStructureCache(Base):
    """
    Shot Structure Cache - Lightweight cache of Episodes/Sequences/Shots directory structure.
    Only stores directory names, not file contents.
    """
    __tablename__ = "shot_structure_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"))

    # Shot hierarchy
    episode: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[str] = mapped_column(String(50), nullable=False)
    shot: Mapped[str] = mapped_column(String(50), nullable=False)

    # Availability flags
    exists_on_ftp: Mapped[bool] = mapped_column(Boolean, default=False)
    exists_locally: Mapped[bool] = mapped_column(Boolean, default=False)
    has_anim: Mapped[bool] = mapped_column(Boolean, default=False)
    has_lighting: Mapped[bool] = mapped_column(Boolean, default=False)

    # Cache metadata
    last_scanned: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    cache_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Indexes
    __table_args__ = (
        Index("idx_shot_structure_lookup", "endpoint_id", "episode", "sequence", "shot"),
        Index("idx_shot_structure_episode", "endpoint_id", "episode"),
        Index("idx_shot_structure_sequence", "endpoint_id", "episode", "sequence"),
        Index("idx_shot_cache_expiry", "cache_expires_at"),
        UniqueConstraint("endpoint_id", "episode", "sequence", "shot", name="uq_shot_structure"),
    )

    def __repr__(self):
        return f"<ShotStructureCache(endpoint={self.endpoint_id}, shot={self.episode}/{self.sequence}/{self.shot})>"


class ShotCacheMetadata(Base):
    """
    Shot Cache Metadata - Track cache status and scan history for endpoints.
    """
    __tablename__ = "shot_cache_metadata"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"), unique=True)

    # Scan timestamps
    last_full_scan: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_full_scan: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Statistics
    total_episodes: Mapped[int] = mapped_column(Integer, default=0)
    total_sequences: Mapped[int] = mapped_column(Integer, default=0)
    total_shots: Mapped[int] = mapped_column(Integer, default=0)
    scan_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Indexes
    __table_args__ = (
        Index("idx_shot_cache_endpoint", "endpoint_id"),
        Index("idx_shot_cache_next_scan", "next_full_scan"),
    )

    def __repr__(self):
        return f"<ShotCacheMetadata(endpoint={self.endpoint_id}, shots={self.total_shots})>"


class ShotDownloadTaskStatus(str, enum.Enum):
    """Shot download task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ShotDownloadTask(Base):
    """
    Shot Download Task - Represents a download task created by user.
    Contains multiple shot/department items to download.
    """
    __tablename__ = "shot_download_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"))

    # Status
    status: Mapped[ShotDownloadTaskStatus] = mapped_column(Enum(ShotDownloadTaskStatus, values_callable=lambda x: [e.value for e in x]), default=ShotDownloadTaskStatus.PENDING)

    # Version Control
    version_strategy: Mapped[str] = mapped_column(String(20), default='latest')  # 'latest', 'specific', 'all', 'custom'
    specific_version: Mapped[Optional[str]] = mapped_column(String(20))  # Used when version_strategy = 'specific'

    # File Conflict Handling
    conflict_strategy: Mapped[str] = mapped_column(String(20), default='skip')  # 'skip', 'overwrite', 'compare', 'keep_both'

    # Progress tracking
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)

    # Size tracking
    total_size: Mapped[int] = mapped_column(Integer, default=0)  # bytes
    downloaded_size: Mapped[int] = mapped_column(Integer, default=0)  # bytes

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # User info
    created_by: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    items: Mapped[list["ShotDownloadItem"]] = relationship("ShotDownloadItem", back_populates="task", cascade="all, delete-orphan")

    # Indexes
    __table_args__ = (
        Index("idx_shot_task_endpoint", "endpoint_id"),
        Index("idx_shot_task_status", "status"),
        Index("idx_shot_task_created", "created_at"),
    )

    def __repr__(self):
        return f"<ShotDownloadTask(id={self.id}, name='{self.name}', status={self.status})>"


class ShotDownloadItemStatus(str, enum.Enum):
    """Shot download item status enumeration."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


class ShotDownloadItem(Base):
    """
    Shot Download Item - Individual shot/department combination within a download task.
    """
    __tablename__ = "shot_download_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shot_download_tasks.id", ondelete="CASCADE"))

    # Shot information
    episode: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[str] = mapped_column(String(50), nullable=False)
    shot: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)  # 'anim' or 'lighting'

    # Version information
    ftp_version: Mapped[Optional[str]] = mapped_column(String(50))
    local_version: Mapped[Optional[str]] = mapped_column(String(50))

    # Version Control (for custom version selection)
    selected_version: Mapped[Optional[str]] = mapped_column(String(20))  # Used when task.version_strategy = 'custom'
    available_versions: Mapped[Optional[list]] = mapped_column(JSONB)  # List of available versions from FTP
    latest_version: Mapped[Optional[str]] = mapped_column(String(20))  # Latest available version

    # Paths
    ftp_path: Mapped[str] = mapped_column(Text, nullable=False)
    local_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Status
    status: Mapped[ShotDownloadItemStatus] = mapped_column(Enum(ShotDownloadItemStatus, values_callable=lambda x: [e.value for e in x]), default=ShotDownloadItemStatus.PENDING)

    # Progress tracking
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    total_size: Mapped[int] = mapped_column(Integer, default=0)  # bytes
    downloaded_size: Mapped[int] = mapped_column(Integer, default=0)  # bytes

    # File Statistics (for conflict handling)
    files_skipped: Mapped[int] = mapped_column(Integer, default=0)
    files_overwritten: Mapped[int] = mapped_column(Integer, default=0)
    files_kept_both: Mapped[int] = mapped_column(Integer, default=0)

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    task: Mapped["ShotDownloadTask"] = relationship("ShotDownloadTask", back_populates="items")

    # Indexes
    __table_args__ = (
        Index("idx_shot_item_task", "task_id"),
        Index("idx_shot_item_status", "status"),
        Index("idx_shot_item_shot", "episode", "sequence", "shot"),
    )

    def __repr__(self):
        return f"<ShotDownloadItem(id={self.id}, shot={self.episode}/{self.sequence}/{self.shot}/{self.department}, status={self.status})>"


# Shot Upload Models
# ------------------

class ShotUploadTaskStatus(str, enum.Enum):
    """Shot upload task status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ShotUploadItemStatus(str, enum.Enum):
    """Shot upload item status enumeration."""
    PENDING = "pending"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ShotUploadTask(Base):
    """
    Shot Upload Task - Represents an upload task created by user.
    Contains multiple shot/department items to upload from local to FTP.
    Uses single endpoint that has both local_path (source) and remote_path (target).
    """
    __tablename__ = "shot_upload_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Single endpoint with both local_path (source) and remote_path (target)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id", ondelete="CASCADE"))

    # Status
    status: Mapped[ShotUploadTaskStatus] = mapped_column(Enum(ShotUploadTaskStatus, values_callable=lambda x: [e.value for e in x]), default=ShotUploadTaskStatus.PENDING)

    # Version Control
    version_strategy: Mapped[str] = mapped_column(String(20), default='latest')  # 'latest', 'specific', 'all', 'custom'
    specific_version: Mapped[Optional[str]] = mapped_column(String(20))  # Used when version_strategy = 'specific'

    # File Conflict Handling
    conflict_strategy: Mapped[str] = mapped_column(String(20), default='skip')  # 'skip', 'overwrite'

    # Progress tracking
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    completed_items: Mapped[int] = mapped_column(Integer, default=0)
    failed_items: Mapped[int] = mapped_column(Integer, default=0)
    skipped_items: Mapped[int] = mapped_column(Integer, default=0)

    # Size tracking
    total_size: Mapped[int] = mapped_column(BigInteger, default=0)  # bytes
    uploaded_size: Mapped[int] = mapped_column(BigInteger, default=0)  # bytes

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # User info
    created_by: Mapped[Optional[str]] = mapped_column(String(255))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    items: Mapped[list["ShotUploadItem"]] = relationship("ShotUploadItem", back_populates="task", cascade="all, delete-orphan")
    endpoint: Mapped["Endpoint"] = relationship("Endpoint", foreign_keys=[endpoint_id])

    # Indexes
    __table_args__ = (
        Index("idx_shot_upload_task_endpoint", "endpoint_id"),
        Index("idx_shot_upload_task_status", "status"),
        Index("idx_shot_upload_task_created", "created_at"),
    )

    def __repr__(self):
        return f"<ShotUploadTask(id={self.id}, name='{self.name}', status={self.status})>"


class ShotUploadItem(Base):
    """
    Shot Upload Item - Individual file to upload within an upload task.
    """
    __tablename__ = "shot_upload_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shot_upload_tasks.id", ondelete="CASCADE"))

    # Shot information
    episode: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[str] = mapped_column(String(50), nullable=False)
    shot: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)  # 'comp', etc.

    # File information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(50))  # e.g., 'v001'

    # Paths
    source_path: Mapped[str] = mapped_column(Text, nullable=False)  # Full local path
    target_path: Mapped[str] = mapped_column(Text, nullable=False)  # Full FTP path
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)  # Path relative to root

    # Status
    status: Mapped[ShotUploadItemStatus] = mapped_column(Enum(ShotUploadItemStatus, values_callable=lambda x: [e.value for e in x]), default=ShotUploadItemStatus.PENDING)

    # Size tracking
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)  # bytes
    uploaded_size: Mapped[int] = mapped_column(BigInteger, default=0)  # bytes

    # Target file info (for conflict detection)
    target_exists: Mapped[bool] = mapped_column(Boolean, default=False)
    target_size: Mapped[Optional[int]] = mapped_column(BigInteger)  # bytes

    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    task: Mapped["ShotUploadTask"] = relationship("ShotUploadTask", back_populates="items")

    # Indexes
    __table_args__ = (
        Index("idx_shot_upload_item_task", "task_id"),
        Index("idx_shot_upload_item_status", "status"),
        Index("idx_shot_upload_item_shot", "episode", "sequence", "shot"),
    )

    def __repr__(self):
        return f"<ShotUploadItem(id={self.id}, file={self.filename}, status={self.status})>"


class ShotUploadHistory(Base):
    """
    Shot Upload History - Track all uploads for auditing and reporting.
    """
    __tablename__ = "shot_upload_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Link to original task/item (may be null if task deleted)
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Shot information
    episode: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[str] = mapped_column(String(50), nullable=False)
    shot: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)

    # File information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[Optional[str]] = mapped_column(String(50))
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)

    # Paths
    source_path: Mapped[str] = mapped_column(Text, nullable=False)
    target_path: Mapped[str] = mapped_column(Text, nullable=False)

    # Endpoint information (stored for history even if endpoint deleted)
    source_endpoint_name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_endpoint_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Result
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'completed', 'failed', 'skipped'
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # User info
    uploaded_by: Mapped[Optional[str]] = mapped_column(String(255))

    # Indexes
    __table_args__ = (
        Index("idx_upload_history_task", "task_id"),
        Index("idx_upload_history_shot", "episode", "sequence", "shot"),
        Index("idx_upload_history_date", "uploaded_at"),
        Index("idx_upload_history_status", "status"),
    )

    def __repr__(self):
        return f"<ShotUploadHistory(id={self.id}, file={self.filename}, status={self.status})>"


class User(Base):
    """
    User model - Optional multi-user support.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Indexes
    __table_args__ = (
        Index("idx_user_email", "email"),
        Index("idx_user_active", "is_active"),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"
