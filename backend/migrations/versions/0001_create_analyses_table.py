"""Create the analyses table."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def skill_list_type() -> sa.JSON:
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_description", sa.Text(), nullable=False),
        sa.Column("user_skills", skill_list_type(), nullable=False),
        sa.Column("extracted_skills", skill_list_type(), nullable=False),
        sa.Column("matched_skills", skill_list_type(), nullable=False),
        sa.Column("missing_skills", skill_list_type(), nullable=False),
        sa.Column("match_score", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "match_score >= 0 AND match_score <= 100",
            name="ck_analyses_match_score_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_analyses_created_at",
        "analyses",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analyses_created_at", table_name="analyses")
    op.drop_table("analyses")
