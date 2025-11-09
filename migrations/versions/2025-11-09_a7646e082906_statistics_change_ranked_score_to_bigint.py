"""statistics: change ranked_score to BigInt

Revision ID: a7646e082906
Revises: 2d395ba2b4fd
Create Date: 2025-11-09 04:18:32.701283

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "a7646e082906"
down_revision: str | Sequence[str] | None = "2d395ba2b4fd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "lazer_user_statistics",
        "ranked_score",
        existing_type=sa.Integer(),
        type_=mysql.BIGINT(),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "lazer_user_statistics",
        "ranked_score",
        existing_type=mysql.BIGINT(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
