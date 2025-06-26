"""add_news_table

Revision ID: b4d533f5ec3d
Revises: f5b345f33ac4
Create Date: 2025-05-29 15:40:05.141207

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b4d533f5ec3d'
down_revision: Union[str, None] = 'f5b345f33ac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create the news table
    op.create_table('news',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('image_url', sa.String(length=255), nullable=True),
        sa.Column('is_published', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        
        # Foreign key constraint
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='CASCADE'),
        
        # Add comment for documentation
        sa.PrimaryKeyConstraint('id'),
        comment='News articles created by users'
    )
    
    # Create index for better query performance
    op.create_index('ix_news_author_id', 'news', ['author_id'], unique=False)
    op.create_index('ix_news_created_at', 'news', ['created_at'], unique=False)


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('ix_news_created_at', table_name='news')
    op.drop_index('ix_news_author_id', table_name='news')
    
    # Then drop the table
    op.drop_table('news')