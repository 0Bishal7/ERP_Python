"""Delete expired and revoked sessions older than 7 days.  Run daily (cron / scheduled task):

    python -m app.scripts.cleanup_sessions
"""
import asyncio
from datetime import timedelta

from sqlalchemy import delete, or_

from app.core.database import SessionLocal
from app.core.utils import utcnow
from app.shared.auth.models import AuthSession


async def main() -> None:
    cutoff = utcnow() - timedelta(days=7)
    async with SessionLocal() as db:
        result = await db.execute(
            delete(AuthSession).where(
                or_(AuthSession.expires_at < cutoff, AuthSession.revoked_at < cutoff)
            )
        )
        await db.commit()
    print(f"Deleted {result.rowcount} old sessions.")


if __name__ == "__main__":
    asyncio.run(main())
