import hashlib
import secrets
from datetime import timedelta
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from reminder_common.config import get_settings
from reminder_common.security import utc_now
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import RefreshToken, User

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = utc_now()
    return jwt.encode(
        {
            "sub": str(user.id),
            "role": user.role.value,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
            "jti": str(uuid4()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


async def issue_pair(session: AsyncSession, user: User, family_id: UUID | None = None) -> tuple[str, str, RefreshToken]:
    settings = get_settings()
    raw = secrets.token_urlsafe(48)
    record = RefreshToken(
        user_id=user.id,
        token_hash=_hash_token(raw),
        family_id=family_id or uuid4(),
        expires_at=utc_now() + timedelta(days=settings.refresh_token_ttl_days),
        created_at=utc_now(),
    )
    session.add(record)
    await session.flush()
    return create_access_token(user), f"{record.id}.{raw}", record


async def find_refresh(session: AsyncSession, presented: str) -> RefreshToken | None:
    token_id, separator, raw = presented.partition(".")
    if not separator:
        return None
    try:
        record = await session.get(RefreshToken, UUID(token_id))
    except ValueError:
        return None
    if record is None or not secrets.compare_digest(record.token_hash, _hash_token(raw)):
        return None
    return record


async def revoke_family(session: AsyncSession, family_id: UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )


async def user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email.strip().lower()))
