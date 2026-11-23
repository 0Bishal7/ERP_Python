from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "CRM Backend"
    environment: str = "local"  # local | staging | production

    # Neon PostgreSQL
    database_url: str  # pooled connection string (used by the app)
    database_url_direct: str | None = None  # direct connection string (used by Alembic)

    # CORS (only needed if frontend and API are on different origins)
    cors_origins: list[str] = ["http://localhost:5173"]

    # Session cookie
    cookie_name: str = "session_id"
    cookie_secure: bool = False  # True in staging/production (HTTPS only)
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None
    session_idle_minutes: int = 480
    session_absolute_hours: int = 72

    # Login protection
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    min_password_length: int = 10

    # First admin (used by the seed script only)
    first_admin_email: str | None = None
    first_admin_password: str | None = None
    first_admin_name: str = "System Admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
