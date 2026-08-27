"""
Служебный скрипт создания администратора.
"""

import argparse
import asyncio

from app.auth.models import UserRole
from app.auth.repository import UserRepository
from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import async_session_factory


async def create_admin(email: str, password: str, full_name: str) -> None:
    async with async_session_factory() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(email)
        if existing is not None:
            print(f"Администратор {existing.email} уже существует (id={existing.id}).")
            return
        user = await repo.create(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.admin,
        )
        await session.commit()
        print(f"Администратор создан: {user.email} (id={user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Создать администратора")
    parser.add_argument("--email", required=True, help="Email администратора")
    parser.add_argument("--password", required=True, help="Пароль администратора")
    parser.add_argument(
        "--full-name",
        default="Администратор",
        help="ФИО (по умолчанию «Администратор»)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if len(args.password) < settings.password_min_length:
        parser.error(
            f"Пароль должен быть не короче {settings.password_min_length} символов"
        )

    asyncio.run(create_admin(args.email, args.password, args.full_name))


if __name__ == "__main__":
    main()
