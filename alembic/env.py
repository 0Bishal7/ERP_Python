from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine

def run_migrations_online():
    connectable = create_async_engine(settings.DATABASE_URL, poolclass=pool.NullPool)
    # ...standard async alembic boilerplate