from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from reminder_common.security import Role, require_admin, require_principal, utc_now
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import db
from app.models.auth import Device, RefreshToken, User
from app.schemas.users import (
    DeviceRegistration,
    DeviceView,
    MemberCreate,
    MemberPage,
    MemberUpdate,
    MemberView,
    PasswordReset,
)
from app.services.audit import record_audit
from app.services.auth import hash_password

router = APIRouter(prefix="/api/v1/users", tags=["users"])
device_router = APIRouter(prefix="/api/v1/devices", tags=["devices"])
Session = Annotated[AsyncSession, Depends(db)]


def member_view(user: User) -> MemberView:
    return MemberView.model_validate(user, from_attributes=True)


def request_id(request: Request) -> str | None:
    return request.headers.get("X-Request-ID")


async def get_member(session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if user is None or user.role is not Role.MEMBER:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member was not found")
    return user


@router.get("", response_model=MemberPage)
async def list_members(
    request: Request,
    session: Session,
    search: str | None = Query(default=None, max_length=200),
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MemberPage:
    require_admin(request)
    filters = [User.role == Role.MEMBER]
    if search:
        term = f"%{search.strip().lower()}%"
        filters.append(or_(func.lower(User.name).like(term), func.lower(User.email).like(term)))
    if active is not None:
        filters.append(User.is_active == active)
    total = await session.scalar(select(func.count()).select_from(User).where(*filters))
    users = (
        await session.scalars(
            select(User).where(*filters).order_by(User.name, User.id).limit(limit).offset(offset)
        )
    ).all()
    return MemberPage(
        items=[member_view(user) for user in users],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=MemberView, status_code=status.HTTP_201_CREATED)
async def create_member(body: MemberCreate, request: Request, session: Session) -> MemberView:
    actor = require_admin(request)
    user = User(
        name=body.name.strip(),
        email=str(body.email).strip().lower(),
        password_hash=hash_password(body.temporary_password),
        role=Role.MEMBER,
        is_active=body.is_active,
        timezone=body.timezone,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered") from exc
    record_audit(
        session,
        actor_id=actor.user_id,
        action="ADMIN_CREATED_USER",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id(request),
        metadata={"email": user.email},
    )
    await session.commit()
    return member_view(user)


@router.get("/{user_id}", response_model=MemberView)
async def view_member(user_id: UUID, request: Request, session: Session) -> MemberView:
    require_admin(request)
    return member_view(await get_member(session, user_id))


@router.patch("/{user_id}", response_model=MemberView)
async def edit_member(
    user_id: UUID, body: MemberUpdate, request: Request, session: Session
) -> MemberView:
    actor = require_admin(request)
    user = await get_member(session, user_id)
    changes = body.model_dump(exclude_unset=True)
    if "email" in changes:
        changes["email"] = str(changes["email"]).strip().lower()
    if "name" in changes:
        changes["name"] = str(changes["name"]).strip()
    for field, value in changes.items():
        setattr(user, field, value)
    record_audit(
        session,
        actor_id=actor.user_id,
        action="ADMIN_UPDATED_USER",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id(request),
        metadata={"fields": list(changes)},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already registered") from exc
    return member_view(user)


async def set_active(
    user_id: UUID, active: bool, request: Request, session: AsyncSession
) -> MemberView:
    actor = require_admin(request)
    user = await get_member(session, user_id)
    user.is_active = active
    action = "ADMIN_REACTIVATED_USER" if active else "ADMIN_DEACTIVATED_USER"
    if not active:
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
    record_audit(
        session,
        actor_id=actor.user_id,
        action=action,
        resource_type="user",
        resource_id=user.id,
        request_id=request_id(request),
    )
    await session.commit()
    return member_view(user)


@router.post("/{user_id}/deactivate", response_model=MemberView)
async def deactivate(user_id: UUID, request: Request, session: Session) -> MemberView:
    return await set_active(user_id, False, request, session)


@router.post("/{user_id}/activate", response_model=MemberView)
async def activate(user_id: UUID, request: Request, session: Session) -> MemberView:
    return await set_active(user_id, True, request, session)


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: UUID, body: PasswordReset, request: Request, session: Session
) -> None:
    actor = require_admin(request)
    user = await get_member(session, user_id)
    user.password_hash = hash_password(body.temporary_password)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    record_audit(
        session,
        actor_id=actor.user_id,
        action="ADMIN_RESET_USER_PASSWORD",
        resource_type="user",
        resource_id=user.id,
        request_id=request_id(request),
    )
    await session.commit()


@device_router.post("/register", response_model=DeviceView)
async def register_device(
    body: DeviceRegistration, request: Request, session: Session
) -> DeviceView:
    principal = require_principal(request)
    device = await session.scalar(
        select(Device).where(
            Device.user_id == principal.user_id,
            Device.device_identifier == body.device_identifier,
        )
    )
    now = utc_now()
    if device is None:
        device = Device(user_id=principal.user_id, last_seen_at=now, **body.model_dump())
        session.add(device)
    else:
        for field, value in body.model_dump().items():
            setattr(device, field, value)
        device.last_seen_at = now
    await session.commit()
    return DeviceView.model_validate(device, from_attributes=True)
