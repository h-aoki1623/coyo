"""Async database engine and session factory."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from coto.config import get_settings


@lru_cache(maxsize=1)
def get_engine():
    """Lazily create and cache the async database engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_session_factory():
    """Lazily create and cache the async session factory."""
    return async_sessionmaker(
        get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )
