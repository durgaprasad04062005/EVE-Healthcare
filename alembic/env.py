"""
Alembic environment configuration.

Key points:
- We read the database URL from our app's settings (not from alembic.ini),
  so there's a single source of truth.
- We import all models (via app.models) so Alembic can detect schema changes
  and generate accurate migrations automatically.
- We use run_async_migrations() because our engine is async (asyncpg).
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Our app's config and the shared metadata from all models
from app.core.config import settings
from app.db.database import Base

# Import all models here so Alembic sees them for autogenerate.
# Add new model modules here as they are created.
import app.models  # noqa: F401 — side-effect import to register all models

# Alembic Config object — gives access to alembic.ini values
config = context.config

# Set the database URL from our settings (overrides whatever is in alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The metadata object that Alembic inspects to detect schema changes
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a live database connection.
    Outputs SQL statements to stdout — useful for review or auditing.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations using an async engine.
    We must use run_sync() to execute the synchronous Alembic migration
    logic within an async context.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # no pooling needed for migrations
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
