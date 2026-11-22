import ssl
from functools import lru_cache
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import certifi
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def to_async_url(url: str) -> tuple[str, dict]:
    """Convert a Neon connection string into a SQLAlchemy asyncpg URL plus connect args.

    Neon gives strings like  postgresql://user:pw@host/db?sslmode=require&channel_binding=require
    asyncpg does not understand sslmode / channel_binding, so we translate them.
    """
    connect_args: dict = {}
    if not url.startswith(("postgres://", "postgresql")):
        return url, connect_args  # e.g. sqlite in tests: leave untouched
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.pop("sslmode", None)
    query.pop("channel_binding", None)

    if url.startswith("postgresql+asyncpg"):
        host = parts.hostname or ""
        if (sslmode and sslmode != "disable") or host.endswith(".neon.tech"):
            connect_args["ssl"] = ssl_context()
        if "-pooler" in host:
            # Neon's pooler is PgBouncer in transaction mode: no prepared statement cache.
            connect_args["statement_cache_size"] = 0
            connect_args["prepared_statement_cache_size"] = 0

    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
    return clean, connect_args


def make_engine(url: str) -> AsyncEngine:
    clean, connect_args = to_async_url(url)
    kwargs: dict = {"connect_args": connect_args}
    if clean.startswith("postgresql"):
        # Neon scales to zero and closes idle connections: check before use, recycle often.
        kwargs.update(pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=300)
    return create_async_engine(clean, **kwargs)


engine = make_engine(get_settings().database_url)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """One session per request. Services call `await db.commit()` explicitly."""
    async with SessionLocal() as session:
        yield session
