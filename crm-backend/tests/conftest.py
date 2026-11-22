import os

# Must be set before the app is imported (settings are read at import time).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite://"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.shared.models  # noqa: E402,F401
from app.core.base import Base  # noqa: E402
from app.core.database import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.scripts.seed import seed_all  # noqa: E402

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "Admin-pass-12345"


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        await seed_all(db, ADMIN_EMAIL, ADMIN_PASSWORD, "Test Admin")
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as db:
            yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as c:
        yield c
    fastapi_app.dependency_overrides.clear()


async def login(client: AsyncClient, email: str, password: str) -> dict:
    """Log in and return the headers (CSRF) to use for later write requests."""
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"X-CSRF-Token": r.json()["csrf_token"]}
