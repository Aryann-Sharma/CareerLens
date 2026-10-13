"""Keep named learning plans and checked practice steps per account."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB(), "postgresql")
    op.create_table(
        "saved_roadmaps",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("client_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("plan", json_type, nullable=False),
        sa.Column("completed", json_type, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "client_id", name="uq_saved_roadmaps_user_client"),
        sa.CheckConstraint("version >= 1", name="ck_saved_roadmaps_version"),
    )
    op.create_index("ix_saved_roadmaps_user_updated", "saved_roadmaps", ["user_id", "updated_at"])


def downgrade():
    op.drop_index("ix_saved_roadmaps_user_updated", table_name="saved_roadmaps")
    op.drop_table("saved_roadmaps")
