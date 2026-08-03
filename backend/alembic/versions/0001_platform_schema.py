"""Create the initial modular platform schema."""

from alembic import op

from app.database import Base
from app import domain_models  # noqa: F401

revision = "0001_platform_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    # Production data is intentionally not dropped by an automatic downgrade.
    pass
