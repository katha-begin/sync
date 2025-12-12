"""Fix download task and item size columns to BigInteger.

Revision ID: 010_fix_download_size_columns
Revises: 009_fix_upload_size_columns
Create Date: 2025-12-12

Changes INTEGER columns to BIGINT to support files larger than 2GB.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '010_fix_download_size_columns'
down_revision = '009_fix_upload_size_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fix shot_download_tasks table
    op.alter_column('shot_download_tasks', 'total_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)
    op.alter_column('shot_download_tasks', 'downloaded_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)

    # Fix shot_download_items table
    op.alter_column('shot_download_items', 'total_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)
    op.alter_column('shot_download_items', 'downloaded_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)


def downgrade() -> None:
    # Revert shot_download_items table
    op.alter_column('shot_download_items', 'downloaded_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)
    op.alter_column('shot_download_items', 'total_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

    # Revert shot_download_tasks table
    op.alter_column('shot_download_tasks', 'downloaded_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)
    op.alter_column('shot_download_tasks', 'total_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)

