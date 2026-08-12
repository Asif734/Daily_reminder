from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, EmailStr, Field, field_validator
from reminder_common.security import Role


def valid_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("timezone must be a valid IANA timezone") from exc
    return value


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    temporary_password: str = Field(min_length=12, max_length=256)
    is_active: bool = True
    timezone: str = "UTC"

    _timezone = field_validator("timezone")(valid_timezone)


class MemberUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    timezone: str | None = None

    _timezone = field_validator("timezone")(valid_timezone)


class PasswordReset(BaseModel):
    temporary_password: str = Field(min_length=12, max_length=256)


class MemberView(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: Role
    is_active: bool
    timezone: str
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MemberPage(BaseModel):
    items: list[MemberView]
    total: int
    limit: int
    offset: int


class DeviceRegistration(BaseModel):
    device_identifier: str = Field(min_length=1, max_length=255)
    device_name: str = Field(min_length=1, max_length=200)
    platform: str = Field(min_length=1, max_length=32)
    app_version: str = Field(min_length=1, max_length=32)
    timezone: str = "UTC"

    _timezone = field_validator("timezone")(valid_timezone)


class DeviceView(DeviceRegistration):
    id: UUID
    user_id: UUID
    last_seen_at: datetime
