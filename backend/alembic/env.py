import sys
from logging.config import fileConfig
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import settings
from app.core.database import Base
from app.models import *  # noqa: F401,F403

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    if len(heads) != 1:
        head_rev = "heads"
    else:
        head_rev = heads[0]

    with connectable.connect() as connection:
        is_sqlite = connection.dialect.name == "sqlite"
        if not is_sqlite:
            # DDL must commit per statement; a pooled connection without AUTOCOMMIT can leave
            # migrations visible in logs but rolled back when the connection closes.
            connection = connection.execution_options(isolation_level="AUTOCOMMIT")
        insp = inspect(connection)
        empty = not insp.has_table("users")

        if is_sqlite and empty:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                # Greenfield SQLite: create_all matches current models; incremental revisions
                # mostly duplicate columns and fail. Stamp head (same as migrate_production.py).
                target_metadata.create_all(bind=connection)
                if not insp.has_table("alembic_version"):
                    connection.execute(
                        text(
                            "CREATE TABLE alembic_version "
                            "(version_num VARCHAR(32) NOT NULL PRIMARY KEY)"
                        )
                    )
                connection.execute(text("DELETE FROM alembic_version"))
                connection.execute(
                    text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                    {"rev": head_rev},
                )
            return

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=is_sqlite,
        )
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
