"""lowercase_item_names

Revision ID: 949bdd7b8b93
Revises: e578f75f531e
Create Date: 2026-04-17 18:27:50.566807

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '949bdd7b8b93'
down_revision: Union[str, Sequence[str], None] = 'e578f75f531e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE item SET name = LOWER(name)")


def downgrade() -> None:
    pass
