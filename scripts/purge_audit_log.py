"""
Скрипт ретеншена журнала аудита: удаляет записи старше N дней.

Запуск (вручную или по cron/systemd-таймеру снаружи приложения):
    uv run python -m scripts.purge_audit_log --retention-days 365
"""

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.db.session import async_session_factory

DEFAULT_RETENTION_DAYS = 365


async def purge_audit_log(
    session: AsyncSession, retention_days: int = DEFAULT_RETENTION_DAYS
) -> int:
    """Удаляет записи аудита старше ``retention_days``; возвращает число удалённых."""
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    deleted = await AuditLogRepository(session).delete_older_than(cutoff)
    await session.commit()
    return deleted


async def _run(retention_days: int) -> int:
    async with async_session_factory() as session:
        return await purge_audit_log(session, retention_days)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Удалить устаревшие записи журнала аудита"
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help=f"Хранить записи не дольше N дней (по умолчанию {DEFAULT_RETENTION_DAYS})",
    )
    args = parser.parse_args()
    deleted = asyncio.run(_run(args.retention_days))
    print(f"Удалено записей аудита: {deleted}")


if __name__ == "__main__":
    main()
