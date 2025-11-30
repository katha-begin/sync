"""Initial schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-01-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE IF NOT EXISTS endpointtype AS ENUM ('ftp', 'sftp', 's3', 'local')")
    op.execute("CREATE TYPE IF NOT EXISTS syncdirection AS ENUM ('source_to_dest', 'dest_to_source', 'bidirectional')")
    op.execute("CREATE TYPE IF NOT EXISTS foldermatchmode AS ENUM ('exact', 'contains', 'startswith')")
    op.execute("CREATE TYPE IF NOT EXISTS executionstatus AS ENUM ('queued', 'running', 'completed', 'failed', 'cancelled')")
    op.execute("CREATE TYPE IF NOT EXISTS operationtype AS ENUM ('upload', 'download', 'delete', 'skip')")
    op.execute("CREATE TYPE IF NOT EXISTS operationstatus AS ENUM ('pending', 'in_progress', 'completed', 'failed', 'skipped')")
    op.execute("CREATE TYPE IF NOT EXISTS loglevel AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')")
    op.execute("CREATE TYPE IF NOT EXISTS scheduleunit AS ENUM ('minutes', 'hours', 'days')")

    # Create endpoints table
    op.create_table('endpoints',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('endpoint_type', postgresql.ENUM('ftp', 'sftp', 's3', 'local', name='endpointtype'), nullable=False),
        sa.Column('host', sa.String(length=255), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=255), nullable=True),
        sa.Column('password_encrypted', sa.Text(), nullable=True),
        sa.Column('remote_path', sa.String(length=1024), nullable=True),
        sa.Column('s3_bucket', sa.String(length=255), nullable=True),
        sa.Column('s3_region', sa.String(length=50), nullable=True),
        sa.Column('s3_access_key', sa.String(length=255), nullable=True),
        sa.Column('s3_secret_key_encrypted', sa.Text(), nullable=True),
        sa.Column('s3_endpoint_url', sa.String(length=512), nullable=True),
        sa.Column('s3_use_ssl', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('local_path', sa.String(length=1024), nullable=True),
        sa.Column('connection_status', sa.String(length=50), nullable=False, server_default='unknown'),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_check_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_endpoint_type', 'endpoints', ['endpoint_type'])
    op.create_index('idx_endpoint_status', 'endpoints', ['connection_status'])
    op.create_index('idx_endpoint_active', 'endpoints', ['is_active'])

    # Create sync_sessions table
    op.create_table('sync_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('source_endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('destination_endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_path', sa.String(length=1024), nullable=False, server_default='/'),
        sa.Column('destination_path', sa.String(length=1024), nullable=False, server_default='/'),
        sa.Column('sync_direction', postgresql.ENUM('source_to_dest', 'dest_to_source', 'bidirectional', name='syncdirection'), nullable=False),
        sa.Column('folder_filter_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('folder_names', postgresql.JSONB(), nullable=True),
        sa.Column('folder_match_mode', postgresql.ENUM('exact', 'contains', 'startswith', name='foldermatchmode'), nullable=False),
        sa.Column('folder_case_sensitive', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('file_pattern_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('file_patterns', postgresql.JSONB(), nullable=True),
        sa.Column('force_overwrite', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('delete_missing', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('schedule_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('schedule_interval', sa.Integer(), nullable=True),
        sa.Column('schedule_unit', postgresql.ENUM('minutes', 'hours', 'days', name='scheduleunit'), nullable=True),
        sa.Column('auto_start_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_running', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.CheckConstraint('source_endpoint_id != destination_endpoint_id', name='check_different_endpoints'),
        sa.ForeignKeyConstraint(['source_endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['destination_endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_session_active', 'sync_sessions', ['is_active'])
    op.create_index('idx_session_running', 'sync_sessions', ['is_running'])
    op.create_index('idx_session_schedule', 'sync_sessions', ['schedule_enabled', 'next_run_at'])

    # Create sync_executions table
    op.create_table('sync_executions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', postgresql.ENUM('queued', 'running', 'completed', 'failed', 'cancelled', name='executionstatus'), nullable=False),
        sa.Column('is_dry_run', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('queued_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('total_files', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('files_synced', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('files_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('files_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('bytes_transferred', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress_percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_file', sa.String(length=1024), nullable=True),
        sa.Column('current_operation', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_stack_trace', sa.Text(), nullable=True),
        sa.Column('summary', postgresql.JSONB(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sync_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_execution_status', 'sync_executions', ['status'])
    op.create_index('idx_execution_session', 'sync_executions', ['session_id', 'queued_at'])
    op.create_index('idx_execution_celery_task', 'sync_executions', ['celery_task_id'])

    # Create sync_operations table
    op.create_table('sync_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('operation_type', postgresql.ENUM('upload', 'download', 'delete', 'skip', name='operationtype'), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'in_progress', 'completed', 'failed', 'skipped', name='operationstatus'), nullable=False),
        sa.Column('source_path', sa.String(length=1024), nullable=False),
        sa.Column('destination_path', sa.String(length=1024), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('file_modified_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('bytes_transferred', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['execution_id'], ['sync_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_operation_execution', 'sync_operations', ['execution_id', 'status'])
    op.create_index('idx_operation_type', 'sync_operations', ['operation_type'])

    # Create logs table
    op.create_table('logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('level', postgresql.ENUM('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', name='loglevel'), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('logger_name', sa.String(length=255), nullable=True),
        sa.Column('execution_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['sync_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_log_level', 'logs', ['level'])
    op.create_index('idx_log_timestamp', 'logs', ['timestamp'])
    op.create_index('idx_log_execution', 'logs', ['execution_id'])
    op.create_index('idx_log_session', 'logs', ['session_id'])

    # Create scan_cache table
    op.create_table('scan_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('file_list', postgresql.JSONB(), nullable=False),
        sa.Column('total_files', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False, server_default='true'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint_id', 'path', name='uq_scan_cache_endpoint_path')
    )
    op.create_index('idx_scan_cache_expires', 'scan_cache', ['expires_at', 'is_valid'])

    # Create app_settings table
    op.create_table('app_settings',
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('value_type', sa.String(length=50), nullable=False, server_default='string'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('key')
    )

    # Create users table
    op.create_table('users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('idx_user_email', 'users', ['email'])
    op.create_index('idx_user_active', 'users', ['is_active'])


def downgrade() -> None:
    # Drop tables
    op.drop_table('users')
    op.drop_table('app_settings')
    op.drop_table('scan_cache')
    op.drop_table('logs')
    op.drop_table('sync_operations')
    op.drop_table('sync_executions')
    op.drop_table('sync_sessions')
    op.drop_table('endpoints')

    # Drop enum types
    op.execute('DROP TYPE scheduleunit')
    op.execute('DROP TYPE loglevel')
    op.execute('DROP TYPE operationstatus')
    op.execute('DROP TYPE operationtype')
    op.execute('DROP TYPE executionstatus')
    op.execute('DROP TYPE foldermatchmode')
    op.execute('DROP TYPE syncdirection')
    op.execute('DROP TYPE endpointtype')
