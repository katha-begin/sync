"""Add shot upload tables

Revision ID: 004_add_shot_upload_tables
Revises: 003_version_conflict
Create Date: 2025-01-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004_add_shot_upload_tables'
down_revision = '003_version_conflict'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create shot upload task status enum
    shot_upload_task_status = postgresql.ENUM(
        'pending', 'running', 'completed', 'failed', 'cancelled',
        name='shotuploadtaskstatus',
        create_type=False
    )
    shot_upload_task_status.create(op.get_bind(), checkfirst=True)

    # Create shot upload item status enum
    shot_upload_item_status = postgresql.ENUM(
        'pending', 'uploading', 'completed', 'failed', 'skipped',
        name='shotuploaditemstatus',
        create_type=False
    )
    shot_upload_item_status.create(op.get_bind(), checkfirst=True)

    # Create shot_upload_tasks table
    op.create_table(
        'shot_upload_tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('source_endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_endpoint_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', shot_upload_task_status, nullable=False, server_default='pending'),
        sa.Column('version_strategy', sa.String(length=20), nullable=False, server_default='latest'),
        sa.Column('specific_version', sa.String(length=20), nullable=True),
        sa.Column('conflict_strategy', sa.String(length=20), nullable=False, server_default='skip'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('uploaded_size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['source_endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_shot_upload_task_source', 'shot_upload_tasks', ['source_endpoint_id'])
    op.create_index('idx_shot_upload_task_target', 'shot_upload_tasks', ['target_endpoint_id'])
    op.create_index('idx_shot_upload_task_status', 'shot_upload_tasks', ['status'])
    op.create_index('idx_shot_upload_task_created', 'shot_upload_tasks', ['created_at'])

    # Create shot_upload_items table
    op.create_table(
        'shot_upload_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('episode', sa.String(length=50), nullable=False),
        sa.Column('sequence', sa.String(length=50), nullable=False),
        sa.Column('shot', sa.String(length=50), nullable=False),
        sa.Column('department', sa.String(length=50), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=True),
        sa.Column('source_path', sa.Text(), nullable=False),
        sa.Column('target_path', sa.Text(), nullable=False),
        sa.Column('relative_path', sa.Text(), nullable=False),
        sa.Column('status', shot_upload_item_status, nullable=False, server_default='pending'),
        sa.Column('file_size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('uploaded_size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('target_exists', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('target_size', sa.BigInteger(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['task_id'], ['shot_upload_tasks.id'], ondelete='CASCADE'),
    )
    op.create_index('idx_shot_upload_item_task', 'shot_upload_items', ['task_id'])
    op.create_index('idx_shot_upload_item_status', 'shot_upload_items', ['status'])
    op.create_index('idx_shot_upload_item_shot', 'shot_upload_items', ['episode', 'sequence', 'shot'])

    # Create shot_upload_history table
    op.create_table(
        'shot_upload_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('item_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('task_name', sa.String(length=255), nullable=False),
        sa.Column('episode', sa.String(length=50), nullable=False),
        sa.Column('sequence', sa.String(length=50), nullable=False),
        sa.Column('shot', sa.String(length=50), nullable=False),
        sa.Column('department', sa.String(length=50), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('source_path', sa.Text(), nullable=False),
        sa.Column('target_path', sa.Text(), nullable=False),
        sa.Column('source_endpoint_name', sa.String(length=255), nullable=False),
        sa.Column('target_endpoint_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('uploaded_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_upload_history_task', 'shot_upload_history', ['task_id'])
    op.create_index('idx_upload_history_shot', 'shot_upload_history', ['episode', 'sequence', 'shot'])
    op.create_index('idx_upload_history_date', 'shot_upload_history', ['uploaded_at'])
    op.create_index('idx_upload_history_status', 'shot_upload_history', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index('idx_upload_history_status', table_name='shot_upload_history')
    op.drop_index('idx_upload_history_date', table_name='shot_upload_history')
    op.drop_index('idx_upload_history_shot', table_name='shot_upload_history')
    op.drop_index('idx_upload_history_task', table_name='shot_upload_history')
    op.drop_table('shot_upload_history')

    op.drop_index('idx_shot_upload_item_shot', table_name='shot_upload_items')
    op.drop_index('idx_shot_upload_item_status', table_name='shot_upload_items')
    op.drop_index('idx_shot_upload_item_task', table_name='shot_upload_items')
    op.drop_table('shot_upload_items')

    op.drop_index('idx_shot_upload_task_created', table_name='shot_upload_tasks')
    op.drop_index('idx_shot_upload_task_status', table_name='shot_upload_tasks')
    op.drop_index('idx_shot_upload_task_target', table_name='shot_upload_tasks')
    op.drop_index('idx_shot_upload_task_source', table_name='shot_upload_tasks')
    op.drop_table('shot_upload_tasks')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS shotuploaditemstatus')
    op.execute('DROP TYPE IF EXISTS shotuploadtaskstatus')

