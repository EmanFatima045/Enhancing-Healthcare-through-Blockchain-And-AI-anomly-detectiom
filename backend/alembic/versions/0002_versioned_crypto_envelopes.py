"""Versioned WebCrypto and recipient key envelopes. Revision ID: 0002."""
from alembic import op
import sqlalchemy as sa
from backend.app.core.database import Base
from backend.app import models  # noqa: F401

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {c["name"] for c in inspector.get_columns("record_versions")}
    with op.batch_alter_table("record_versions") as batch:
        if "envelope_json" not in columns: batch.add_column(sa.Column("envelope_json", sa.JSON(), nullable=True))
        if "envelope_digest" not in columns: batch.add_column(sa.Column("envelope_digest", sa.String(71), nullable=True))
        if "key_version" not in columns: batch.add_column(sa.Column("key_version", sa.Integer(), nullable=False, server_default="1"))
    columns = {c["name"] for c in sa.inspect(bind).get_columns("encrypted_envelopes")}
    with op.batch_alter_table("encrypted_envelopes") as batch:
        if "recipient_key_version" not in columns: batch.add_column(sa.Column("recipient_key_version", sa.Integer(), nullable=False, server_default="1"))
        if "envelope_json" not in columns: batch.add_column(sa.Column("envelope_json", sa.JSON(), nullable=True))
        if "envelope_digest" not in columns: batch.add_column(sa.Column("envelope_digest", sa.String(71), nullable=True))
    columns = {c["name"] for c in sa.inspect(bind).get_columns("consent_projections")}
    with op.batch_alter_table("consent_projections") as batch:
        if "source" not in columns: batch.add_column(sa.Column("source", sa.String(24), nullable=False, server_default="LOCAL"))
    Base.metadata.create_all(bind)

def downgrade():
    pass
