"""user: store online status in database

Revision ID: d430db6fc051
Revises: 57641cb601f4
Create Date: 2025-12-06 12:57:44.247351

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "d430db6fc051"
down_revision: str | Sequence[str] | None = "57641cb601f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "lazer_users",
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("lazer_users", "is_online")
