"""Wallet challenges, verified chain receipts, outbox idempotency and emergency delivery."""
from alembic import op
import sqlalchemy as sa
from backend.app.core.database import Base
from backend.app import models  # noqa
revision="0004";down_revision="0003";branch_labels=None;depends_on=None
def upgrade():
    bind=op.get_bind();inspector=sa.inspect(bind);cols={c["name"] for c in inspector.get_columns("chain_transactions")}
    additions=[("block_hash",sa.String(66),True,None),("chain_id",sa.Integer(),False,"31337"),("sender",sa.String(42),True,None),("contract_address",sa.String(42),True,None),("expected_call",sa.String(80),True,None),("expected_args",sa.JSON(),False,"{}"),("confirmations",sa.Integer(),False,"0"),("last_checked_at",sa.DateTime(timezone=True),True,None)]
    with op.batch_alter_table("chain_transactions") as batch:
        for name,kind,nullable,default in additions:
            if name not in cols:batch.add_column(sa.Column(name,kind,nullable=nullable,server_default=default))
    out={c["name"] for c in inspector.get_columns("outbox_jobs")}
    with op.batch_alter_table("outbox_jobs") as batch:
        if "dedupe_key" not in out:batch.add_column(sa.Column("dedupe_key",sa.String(160),nullable=True))
        batch.create_unique_constraint("uq_outbox_dedupe_key",["dedupe_key"])
    Base.metadata.create_all(bind)
def downgrade(): pass
