from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.database import Base

# Import all models so Alembic sees every mapped table.
import app.models  # noqa: F401, E402


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url_without_libpq_sslmode() -> tuple[str, dict[str, object]]:
    """Convert a Supabase URL into an asyncpg-compatible URL and options."""
    database_url = make_url(settings.DATABASE_URL)
    connect_args: dict[str, object] = {}
    sslmode = database_url.query.get("sslmode")
    if sslmode:
        connect_args["ssl"] = sslmode
        database_url = database_url.difference_update_query(["sslmode"])
    # SQLAlchemy masks passwords when URL objects are converted with str().
    # Alembic needs the unmasked value internally to establish the connection;
    # it is never logged or printed here.
    return database_url.render_as_string(hide_password=False), connect_args


def run_migrations_offline() -> None:
    url, _ = database_url_without_libpq_sslmode()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url, connect_args = database_url_without_libpq_sslmode()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    import asyncio

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
