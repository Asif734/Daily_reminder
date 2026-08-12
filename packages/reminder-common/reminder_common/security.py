from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status
from jwt import InvalidTokenError

from reminder_common.config import get_settings


class Role(StrEnum):
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    role: Role


def decode_access_token(token: str) -> Principal:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("type") != "access":
            raise InvalidTokenError("incorrect token type")
        return Principal(user_id=UUID(payload["sub"]), role=Role(payload["role"]))
    except (InvalidTokenError, KeyError, ValueError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authentication token") from exc


def require_principal(request: Request) -> Principal:
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return decode_access_token(token)


def require_admin(request: Request) -> Principal:
    principal = require_principal(request)
    if principal.role is not Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator role required")
    return principal


def utc_now() -> datetime:
    return datetime.now(UTC)
