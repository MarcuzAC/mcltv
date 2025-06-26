"""add_news_table

Revision ID: 262a975e4e71
Revises: 71743dd29398
Create Date: 2025-05-30 11:49:42.024404

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '262a975e4e71'
down_revision: Union[str, None] = '71743dd29398'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
