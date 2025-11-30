"""Add shot download tables

Revision ID: 002_add_shot_download_tables
Revises: 001_initial_schema
Create Date: 2025-01-30 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_shot_download_tables'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create shot_structure_cache table
    op.create_table('shot_structure_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('episode', sa.String(length=50), nullable=False),
        sa.Column('sequence', sa.String(length=50), nullable=False),
        sa.Column('shot', sa.String(length=50), nullable=False),
        sa.Column('exists_on_ftp', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('exists_locally', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('has_anim', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('has_lighting', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_scanned', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('cache_expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('endpoint_id', 'episode', 'sequence', 'shot', name='uq_shot_structure')
    )
    
    # Create indexes for shot_structure_cache
    op.create_index('idx_shot_structure_lookup', 'shot_structure_cache', ['endpoint_id', 'episode', 'sequence', 'shot'])
    op.create_index('idx_shot_structure_episode', 'shot_structure_cache', ['endpoint_id', 'episode'])
    op.create_index('idx_shot_structure_sequence', 'shot_structure_cache', ['endpoint_id', 'episode', 'sequence'])
    op.create_index('idx_shot_cache_expiry', 'shot_structure_cache', ['cache_expires_at'])

    # Create shot_cache_metadata table
    op.create_table('shot_cache_metadata',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('last_full_scan', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_full_scan', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_episodes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_sequences', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_shots', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('scan_duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('endpoint_id')
    )
    
    # Create indexes for shot_cache_metadata
    op.create_index('idx_shot_cache_endpoint', 'shot_cache_metadata', ['endpoint_id'])
    op.create_index('idx_shot_cache_next_scan', 'shot_cache_metadata', ['next_full_scan'])

    # Create shot_download_tasks table
    op.create_table('shot_download_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled',
                                   name='shotdownloadtaskstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('downloaded_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['endpoint_id'], ['endpoints.id'], ondelete='CASCADE')
    )
    
    # Create indexes for shot_download_tasks
    op.create_index('idx_shot_task_endpoint', 'shot_download_tasks', ['endpoint_id'])
    op.create_index('idx_shot_task_status', 'shot_download_tasks', ['status'])
    op.create_index('idx_shot_task_created', 'shot_download_tasks', ['created_at'])

    # Create shot_download_items table
    op.create_table('shot_download_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('episode', sa.String(length=50), nullable=False),
        sa.Column('sequence', sa.String(length=50), nullable=False),
        sa.Column('shot', sa.String(length=50), nullable=False),
        sa.Column('department', sa.String(length=50), nullable=False),
        sa.Column('ftp_version', sa.String(length=50), nullable=True),
        sa.Column('local_version', sa.String(length=50), nullable=True),
        sa.Column('ftp_path', sa.Text(), nullable=False),
        sa.Column('local_path', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'downloading', 'completed', 'failed',
                                   name='shotdownloaditemstatus', create_type=False), nullable=False, server_default='pending'),
        sa.Column('file_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('downloaded_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['shot_download_tasks.id'], ondelete='CASCADE')
    )
    
    # Create indexes for shot_download_items
    op.create_index('idx_shot_item_task', 'shot_download_items', ['task_id'])
    op.create_index('idx_shot_item_status', 'shot_download_items', ['status'])
    op.create_index('idx_shot_item_shot', 'shot_download_items', ['episode', 'sequence', 'shot'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_shot_item_shot', table_name='shot_download_items')
    op.drop_index('idx_shot_item_status', table_name='shot_download_items')
    op.drop_index('idx_shot_item_task', table_name='shot_download_items')
    op.drop_table('shot_download_items')
    
    op.drop_index('idx_shot_task_created', table_name='shot_download_tasks')
    op.drop_index('idx_shot_task_status', table_name='shot_download_tasks')
    op.drop_index('idx_shot_task_endpoint', table_name='shot_download_tasks')
    op.drop_table('shot_download_tasks')
    
    op.drop_index('idx_shot_cache_next_scan', table_name='shot_cache_metadata')
    op.drop_index('idx_shot_cache_endpoint', table_name='shot_cache_metadata')
    op.drop_table('shot_cache_metadata')
    
    op.drop_index('idx_shot_cache_expiry', table_name='shot_structure_cache')
    op.drop_index('idx_shot_structure_sequence', table_name='shot_structure_cache')
    op.drop_index('idx_shot_structure_episode', table_name='shot_structure_cache')
    op.drop_index('idx_shot_structure_lookup', table_name='shot_structure_cache')
    op.drop_table('shot_structure_cache')
    
    # Drop enum types
    op.execute("DROP TYPE shotdownloaditemstatus")
    op.execute("DROP TYPE shotdownloadtaskstatus")

