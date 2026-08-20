from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base shared by all ORM models."""


database_url = make_url(settings.DATABASE_URL)
connect_args: dict[str, object] = {}

# Supabase connection strings may use libpq's ``sslmode`` query parameter.
# asyncpg expects the equivalent option as ``ssl`` instead.
sslmode = database_url.query.get("sslmode")
if sslmode:
    connect_args["ssl"] = sslmode
    database_url = database_url.difference_update_query(["sslmode"])

engine = create_async_engine(
    database_url,
    echo=False,
    pool_pre_ping=True,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create tables for local development; production uses Alembic."""
    if not settings.DEBUG:
        return

    # Import models so they are registered on Base.metadata before create_all.
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
