"""lowercase_categories

Revision ID: e578f75f531e
Revises: fff8c3848c24
Create Date: 2026-04-14 14:03:17.559136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e578f75f531e'
down_revision: Union[str, Sequence[str], None] = 'fff8c3848c24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE item SET category = LOWER(category)")


def downgrade() -> None:
    pass
