"""Add user ownership to analyses."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_analyses_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_analyses_user_id_created_at",
            ["user_id", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.drop_index("ix_analyses_user_id_created_at")
        batch_op.drop_constraint(
            "fk_analyses_user_id_users",
            type_="foreignkey",
        )
        batch_op.drop_column("user_id")
