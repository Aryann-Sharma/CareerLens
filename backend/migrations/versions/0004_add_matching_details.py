"""Store semantic matching evidence alongside each analysis."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("matching_details", sa.JSON().with_variant(postgresql.JSONB(), "postgresql")),
    )


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.drop_column("matching_details")
