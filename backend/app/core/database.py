"""SQLAlchemy database setup for SQLite development and PostgreSQL deployment."""

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def initialize_database() -> None:
    """Create a fresh schema and upgrade the one legacy SQLite users table safely."""
    from .. import models  # noqa: F401
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("users")}
        with engine.begin() as connection:
            if "is_active" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))
            if "updated_at" not in columns:
                connection.execute(text("ALTER TABLE users ADD COLUMN updated_at DATETIME"))
                connection.execute(text("UPDATE users SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
    if settings.DATABASE_URL.startswith("sqlite") and "record_versions" in inspector.get_table_names():
        with engine.begin() as connection:
            rv = {column["name"] for column in inspect(engine).get_columns("record_versions")}
            if "envelope_json" not in rv: connection.execute(text("ALTER TABLE record_versions ADD COLUMN envelope_json JSON"))
            if "envelope_digest" not in rv: connection.execute(text("ALTER TABLE record_versions ADD COLUMN envelope_digest VARCHAR(71)"))
            if "key_version" not in rv: connection.execute(text("ALTER TABLE record_versions ADD COLUMN key_version INTEGER NOT NULL DEFAULT 1"))
            ee = {column["name"] for column in inspect(engine).get_columns("encrypted_envelopes")}
            if "recipient_key_version" not in ee: connection.execute(text("ALTER TABLE encrypted_envelopes ADD COLUMN recipient_key_version INTEGER NOT NULL DEFAULT 1"))
            if "envelope_json" not in ee: connection.execute(text("ALTER TABLE encrypted_envelopes ADD COLUMN envelope_json JSON"))
            if "envelope_digest" not in ee: connection.execute(text("ALTER TABLE encrypted_envelopes ADD COLUMN envelope_digest VARCHAR(71)"))
            cp = {column["name"] for column in inspect(engine).get_columns("consent_projections")}
            if "source" not in cp: connection.execute(text("ALTER TABLE consent_projections ADD COLUMN source VARCHAR(24) NOT NULL DEFAULT 'LOCAL'"))
    Base.metadata.create_all(engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
