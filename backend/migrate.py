"""Start-safe migration entrypoint for fresh and legacy HealerPlus databases."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from .app.core.database import SessionLocal, engine, initialize_database


def main() -> None:
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    tables = inspect(engine).get_table_names()
    if "alembic_version" not in tables:
        initialize_database()
        command.stamp(config, "head")
        return
    with SessionLocal() as db:
        revision = db.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    if revision:
        if revision == "0004" and "password_reset_tokens" in tables:
            command.stamp(config, "head")
            return
        command.upgrade(config, "head")
    else:
        initialize_database()
        command.stamp(config, "head")


if __name__ == "__main__":
    main()
