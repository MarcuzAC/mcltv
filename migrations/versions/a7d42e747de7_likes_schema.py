"""likes schema

Revision ID: a7d42e747de7
Revises: e15fa1bb99ea
Create Date: 2025-07-07 23:12:58.073323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d42e747de7'
down_revision: Union[str, None] = 'e15fa1bb99ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
