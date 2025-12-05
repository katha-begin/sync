"""Change upload task to use single endpoint

Revision ID: 005_upload_single_endpoint
Revises: 004_add_shot_upload_tables
Create Date: 2025-01-31 12:00:00.000000

This migration changes the shot_upload_tasks table from using separate
source_endpoint_id and target_endpoint_id to a single endpoint_id.
The endpoint has both local_path (source) and remote_path (target).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_upload_single_endpoint'
down_revision = '004_add_shot_upload_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new endpoint_id column (initially nullable)
    op.add_column('shot_upload_tasks', 
        sa.Column('endpoint_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Copy target_endpoint_id to endpoint_id (target has both local_path and remote_path)
    op.execute("""
        UPDATE shot_upload_tasks 
        SET endpoint_id = target_endpoint_id
    """)
    
    # Make endpoint_id not nullable
    op.alter_column('shot_upload_tasks', 'endpoint_id', nullable=False)
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_shot_upload_tasks_endpoint',
        'shot_upload_tasks', 'endpoints',
        ['endpoint_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Create new index
    op.create_index('idx_shot_upload_task_endpoint', 'shot_upload_tasks', ['endpoint_id'])
    
    # Drop old indexes
    op.drop_index('idx_shot_upload_task_source', table_name='shot_upload_tasks')
    op.drop_index('idx_shot_upload_task_target', table_name='shot_upload_tasks')
    
    # Drop old foreign key constraints
    op.drop_constraint('shot_upload_tasks_source_endpoint_id_fkey', 'shot_upload_tasks', type_='foreignkey')
    op.drop_constraint('shot_upload_tasks_target_endpoint_id_fkey', 'shot_upload_tasks', type_='foreignkey')
    
    # Drop old columns
    op.drop_column('shot_upload_tasks', 'source_endpoint_id')
    op.drop_column('shot_upload_tasks', 'target_endpoint_id')


def downgrade() -> None:
    # Add back old columns
    op.add_column('shot_upload_tasks',
        sa.Column('source_endpoint_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.add_column('shot_upload_tasks',
        sa.Column('target_endpoint_id', postgresql.UUID(as_uuid=True), nullable=True)
    )
    
    # Copy endpoint_id to both columns
    op.execute("""
        UPDATE shot_upload_tasks 
        SET source_endpoint_id = endpoint_id,
            target_endpoint_id = endpoint_id
    """)
    
    # Make columns not nullable
    op.alter_column('shot_upload_tasks', 'source_endpoint_id', nullable=False)
    op.alter_column('shot_upload_tasks', 'target_endpoint_id', nullable=False)
    
    # Add foreign key constraints
    op.create_foreign_key(
        'shot_upload_tasks_source_endpoint_id_fkey',
        'shot_upload_tasks', 'endpoints',
        ['source_endpoint_id'], ['id'],
        ondelete='CASCADE'
    )
    op.create_foreign_key(
        'shot_upload_tasks_target_endpoint_id_fkey',
        'shot_upload_tasks', 'endpoints',
        ['target_endpoint_id'], ['id'],
        ondelete='CASCADE'
    )
    
    # Create old indexes
    op.create_index('idx_shot_upload_task_source', 'shot_upload_tasks', ['source_endpoint_id'])
    op.create_index('idx_shot_upload_task_target', 'shot_upload_tasks', ['target_endpoint_id'])
    
    # Drop new index
    op.drop_index('idx_shot_upload_task_endpoint', table_name='shot_upload_tasks')
    
    # Drop new foreign key constraint
    op.drop_constraint('fk_shot_upload_tasks_endpoint', 'shot_upload_tasks', type_='foreignkey')
    
    # Drop new column
    op.drop_column('shot_upload_tasks', 'endpoint_id')

