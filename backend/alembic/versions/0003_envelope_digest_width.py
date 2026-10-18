"""Store the complete sha256: envelope digest. Revision ID: 0003."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("medical_records") as batch:
        batch.alter_column("data_hash", existing_type=sa.String(64), type_=sa.String(71), existing_nullable=False)


def downgrade():
    with op.batch_alter_table("medical_records") as batch:
        batch.alter_column("data_hash", existing_type=sa.String(71), type_=sa.String(64), existing_nullable=False)
