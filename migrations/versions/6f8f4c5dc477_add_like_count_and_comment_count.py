"""add like_count and comment_count

Revision ID: [new_revision_id]
Revises: [previous_revision_id]
Create Date: [current_date]

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text

# revision identifiers
revision = '[new_revision_id]'
down_revision = '[previous_revision_id]'
branch_labels = None
depends_on = None

def upgrade():
    # Add columns as nullable first
    op.add_column('videos', sa.Column('like_count', sa.Integer(), nullable=True))
    op.add_column('videos', sa.Column('comment_count', sa.Integer(), nullable=True))
    
    # Set default values for existing rows
    conn = op.get_bind()
    conn.execute(text("UPDATE videos SET like_count = 0 WHERE like_count IS NULL"))
    conn.execute(text("UPDATE videos SET comment_count = 0 WHERE comment_count IS NULL"))
    
    # Now alter columns to be NOT NULL
    op.alter_column('videos', 'like_count', nullable=False)
    op.alter_column('videos', 'comment_count', nullable=False)

def downgrade():
    op.drop_column('videos', 'comment_count')
    op.drop_column('videos', 'like_count')