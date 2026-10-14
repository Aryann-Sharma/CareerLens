"""Store reviewed skills and trained extraction evidence."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analyses", sa.Column("extraction_details", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True))


def downgrade():
    op.drop_column("analyses", "extraction_details")
