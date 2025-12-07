"""Fix upload size columns to BigInteger

Revision ID: 009_fix_upload_size_columns
Revises: 008_schedule_history
Create Date: 2025-12-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_fix_upload_size_columns'
down_revision: Union[str, None] = '008_schedule_history'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix shot_upload_tasks columns
    op.alter_column('shot_upload_tasks', 'total_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    op.alter_column('shot_upload_tasks', 'uploaded_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    # Fix shot_upload_items columns
    op.alter_column('shot_upload_items', 'file_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    op.alter_column('shot_upload_items', 'uploaded_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    op.alter_column('shot_upload_items', 'target_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=True)
    
    # Fix shot_upload_history columns
    op.alter_column('shot_upload_history', 'file_size',
                    existing_type=sa.Integer(),
                    type_=sa.BigInteger(),
                    existing_nullable=False,
                    existing_server_default='0')


def downgrade() -> None:
    # Revert shot_upload_history columns
    op.alter_column('shot_upload_history', 'file_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    # Revert shot_upload_items columns
    op.alter_column('shot_upload_items', 'target_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=True)
    
    op.alter_column('shot_upload_items', 'uploaded_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    op.alter_column('shot_upload_items', 'file_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    # Revert shot_upload_tasks columns
    op.alter_column('shot_upload_tasks', 'uploaded_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                    existing_server_default='0')
    
    op.alter_column('shot_upload_tasks', 'total_size',
                    existing_type=sa.BigInteger(),
                    type_=sa.Integer(),
                    existing_nullable=False,
                    existing_server_default='0')

