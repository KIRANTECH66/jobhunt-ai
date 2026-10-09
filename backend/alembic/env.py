"""Alembic migration environment.

Uses the application's own SQLAlchemy models (``app.models.Base``) as the
target metadata, so migrations are generated from the ORM definitions. The
connection URL is read from the application settings (``DATABASE_URL``), so
the same migration pipeline works against SQLite and PostgreSQL.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.models._base import Base  # noqa: F401  (imported for metadata)

# Alembic Config object, accessible as ``config`` inside migration scripts.
config = context.config

# Interpret the config file for Python logging, if present.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The target metadata used for ``alembic revision --autogenerate``.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and emits SQL to stdout.
    """
    url = settings.database_url
    config.set_main_option("sqlalchemy.url", url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an Engine and associates a connection with the context.
    """
    # Use the application's database URL for the migration connection.
    config.set_main_option("sqlalchemy.url", settings.database_url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


# Run migrations.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()