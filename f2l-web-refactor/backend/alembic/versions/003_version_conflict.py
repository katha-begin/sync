"""Add version selection and conflict handling fields

Revision ID: 003_version_conflict
Revises: 002_add_shot_download_tables
Create Date: 2025-01-30 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_version_conflict'
down_revision = '002_add_shot_download_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add version and conflict fields to shot_download_tasks
    op.add_column('shot_download_tasks', 
        sa.Column('version_strategy', sa.String(length=20), nullable=False, server_default='latest')
    )
    op.add_column('shot_download_tasks', 
        sa.Column('specific_version', sa.String(length=20), nullable=True)
    )
    op.add_column('shot_download_tasks', 
        sa.Column('conflict_strategy', sa.String(length=20), nullable=False, server_default='skip')
    )
    
    # Add version and statistics fields to shot_download_items
    op.add_column('shot_download_items', 
        sa.Column('selected_version', sa.String(length=20), nullable=True)
    )
    op.add_column('shot_download_items', 
        sa.Column('available_versions', postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column('shot_download_items', 
        sa.Column('latest_version', sa.String(length=20), nullable=True)
    )
    op.add_column('shot_download_items', 
        sa.Column('files_skipped', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column('shot_download_items', 
        sa.Column('files_overwritten', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column('shot_download_items', 
        sa.Column('files_kept_both', sa.Integer(), nullable=False, server_default='0')
    )


def downgrade() -> None:
    # Remove fields from shot_download_items
    op.drop_column('shot_download_items', 'files_kept_both')
    op.drop_column('shot_download_items', 'files_overwritten')
    op.drop_column('shot_download_items', 'files_skipped')
    op.drop_column('shot_download_items', 'latest_version')
    op.drop_column('shot_download_items', 'available_versions')
    op.drop_column('shot_download_items', 'selected_version')
    
    # Remove fields from shot_download_tasks
    op.drop_column('shot_download_tasks', 'conflict_strategy')
    op.drop_column('shot_download_tasks', 'specific_version')
    op.drop_column('shot_download_tasks', 'version_strategy')

