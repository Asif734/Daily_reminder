import argparse
import asyncio
import os

from reminder_common.config import get_settings
from reminder_common.security import Role
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.auth import User
from app.services.auth import hash_password, user_by_email


async def seed(email: str, password: str, name: str) -> None:
    engine = create_async_engine(get_settings().database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        if await user_by_email(session, email):
            print("Admin already exists")
        else:
            session.add(
                User(
                    email=email.strip().lower(),
                    name=name,
                    password_hash=hash_password(password),
                    role=Role.ADMIN,
                    is_active=True,
                    timezone="UTC",
                )
            )
            await session.commit()
            print("Admin created")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=os.getenv("INITIAL_ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.getenv("INITIAL_ADMIN_PASSWORD"))
    parser.add_argument("--name", default=os.getenv("INITIAL_ADMIN_NAME", "System Administrator"))
    args = parser.parse_args()
    if not args.email or not args.password:
        parser.error(
            "admin credentials are required through arguments or INITIAL_ADMIN_EMAIL and "
            "INITIAL_ADMIN_PASSWORD"
        )
    if len(args.password) < 12:
        parser.error("INITIAL_ADMIN_PASSWORD must contain at least 12 characters")
    asyncio.run(seed(args.email, args.password, args.name))
