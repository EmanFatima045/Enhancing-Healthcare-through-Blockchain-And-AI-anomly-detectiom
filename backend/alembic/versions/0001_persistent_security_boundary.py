"""Persistent security boundary. Revision ID: 0001."""
from alembic import op
import sqlalchemy as sa
from backend.app.core.database import Base
from backend.app import models  # noqa: F401

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        with op.batch_alter_table("users") as batch:
            if "is_active" not in columns:
                batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
            if "updated_at" not in columns:
                batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    Base.metadata.create_all(bind)

def downgrade():
    # Data-destructive downgrade is intentionally not automated.
    pass
