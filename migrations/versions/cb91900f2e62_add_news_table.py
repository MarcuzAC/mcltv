"""add_news_table

Revision ID: cb91900f2e62
Revises: b4d533f5ec3d
Create Date: 2025-05-29 16:06:02.600696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cb91900f2e62'
down_revision: Union[str, None] = 'b4d533f5ec3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
