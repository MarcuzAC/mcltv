"""APK Download Url

Revision ID: 10bf295dd2a5
Revises: a7d42e747de7
Create Date: 2025-07-08 15:35:16.616177

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '10bf295dd2a5'
down_revision: Union[str, None] = 'a7d42e747de7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
