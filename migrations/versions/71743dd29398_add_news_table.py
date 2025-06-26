"""add_news_table

Revision ID: 71743dd29398
Revises: cb91900f2e62
Create Date: 2025-05-29 16:13:50.389958

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71743dd29398'
down_revision: Union[str, None] = 'cb91900f2e62'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
