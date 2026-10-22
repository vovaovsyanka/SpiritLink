"""Подключение к PostgreSQL (SQLAlchemy 2, asyncpg)."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app import settings

engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """Зависимость FastAPI: сессия на время запроса."""
    async with SessionLocal() as session:
        yield session
