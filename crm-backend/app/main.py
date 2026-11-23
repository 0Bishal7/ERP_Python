from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registers all tables)
from app.api import api_router
from app.core.config import get_settings
from app.core.database import engine
from app.core.errors import register_error_handlers

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,  # needed for the session cookie
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

register_error_handlers(app)
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}
