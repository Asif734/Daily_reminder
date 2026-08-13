import json
from typing import Annotated
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from reminder_common.security import Role, require_admin, require_principal, utc_now
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reminder import Assignment, OutboxEvent, Reminder, ReminderType
from app.schemas.reminders import (
    AddAssignments,
    AssignmentMode,
    ReminderCreate,
    ReminderPage,
    ReminderUpdate,
    ReminderView,
)

router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


async def db(request: Request):  # type: ignore[no-untyped-def]
    async with request.app.state.session_factory() as session:
        yield session


Session = Annotated[AsyncSession, Depends(db)]


async def reminder_view(session: AsyncSession, reminder: Reminder) -> ReminderView:
    user_ids = list(
        await session.scalars(
            select(Assignment.user_id)
            .where(Assignment.reminder_id == reminder.id)
            .order_by(Assignment.user_id)
        )
    )
    return ReminderView(
        **{
            field: getattr(reminder, field)
            for field in ReminderView.model_fields
            if field != "assigned_user_ids"
        },
        assigned_user_ids=user_ids,
    )


def add_outbox(
    session: AsyncSession, reminder: Reminder, event_type: str, payload: dict[str, object]
) -> None:
    session.add(
        OutboxEvent(
            aggregate_type="reminder",
            aggregate_id=reminder.id,
            event_type=event_type,
            payload=payload,
            created_at=utc_now(),
            attempts=0,
        )
    )


async def add_audit(
    session: AsyncSession,
    request: Request,
    *,
    actor_id: UUID,
    action: str,
    reminder_id: UUID,
    metadata: dict[str, object] | None = None,
) -> None:
    await session.execute(
        text(
            """INSERT INTO audit.audit_logs
            (id, actor_id, action, resource_type, resource_id, metadata, request_id, created_at)
            VALUES (:id, :actor_id, :action, 'reminder', :resource_id,
                    CAST(:metadata AS json), :request_id, :created_at)"""
        ),
        {
            "id": str(uuid4()),
            "actor_id": str(actor_id),
            "action": action,
            "resource_id": str(reminder_id),
            "metadata": json.dumps(metadata or {}),
            "request_id": request.headers.get("X-Request-ID"),
            "created_at": utc_now(),
        },
    )


async def fetch_users(request: Request, body: ReminderCreate) -> list[dict[str, object]]:
    principal = require_admin(request)
    headers = {"Authorization": request.headers["Authorization"]}
    base_url = request.app.state.settings.auth_service_url
    async with httpx.AsyncClient(timeout=10) as client:
        if body.assignment_mode is AssignmentMode.ALL:
            response = await client.get(
                f"{base_url}/api/v1/users", params={"active": "true", "limit": 100}, headers=headers
            )
            if response.status_code != 200:
                raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "User service unavailable")
            data = response.json()
            if data["total"] > len(data["items"]):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Too many active users")
            return data["items"]
        users: list[dict[str, object]] = []
        for user_id in body.user_ids:
            response = await client.get(f"{base_url}/api/v1/users/{user_id}", headers=headers)
            if response.status_code != 200:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid member: {user_id}")
            member = response.json()
            if not member["is_active"]:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Inactive member: {user_id}")
            users.append(member)
    _ = principal
    return users


async def get_reminder(session: AsyncSession, reminder_id: UUID) -> Reminder:
    reminder = await session.get(Reminder, reminder_id)
    if reminder is None or reminder.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder was not found")
    return reminder


@router.post("", response_model=ReminderView, status_code=status.HTTP_201_CREATED)
async def create_reminder(body: ReminderCreate, request: Request, session: Session) -> ReminderView:
    principal = require_admin(request)
    users = await fetch_users(request, body)
    if not users:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No active members selected")
    reminder = Reminder(
        title=body.title.strip(),
        description=body.description,
        type=body.type,
        reminder_time=body.reminder_time,
        secondary_reminder_time=body.secondary_reminder_time,
        monthly_due_day=body.monthly_due_day,
        days_before=body.days_before,
        priority=body.priority,
        is_active=True,
        created_by=principal.user_id,
    )
    session.add(reminder)
    await session.flush()
    for user in users:
        session.add(
            Assignment(
                reminder_id=reminder.id,
                user_id=UUID(str(user["id"])),
                timezone=str(user["timezone"]),
                created_at=utc_now(),
            )
        )
    add_outbox(session, reminder, "reminder.created", {"assignment_count": len(users)})
    add_outbox(
        session,
        reminder,
        "reminder.assigned",
        {"user_ids": [str(user["id"]) for user in users]},
    )
    await add_audit(
        session,
        request,
        actor_id=principal.user_id,
        action="ADMIN_CREATED_REMINDER",
        reminder_id=reminder.id,
        metadata={"assignment_count": len(users)},
    )
    await session.commit()
    return await reminder_view(session, reminder)


@router.get("", response_model=ReminderPage)
async def list_reminders(
    request: Request,
    session: Session,
    active: bool | None = None,
    reminder_type: Annotated[ReminderType | None, Query(alias="type")] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ReminderPage:
    principal = require_principal(request)
    filters = [Reminder.deleted_at.is_(None)]
    query = select(Reminder)
    if principal.role is Role.MEMBER:
        query = query.join(Assignment).where(Assignment.user_id == principal.user_id)
    if active is not None:
        filters.append(Reminder.is_active == active)
    if reminder_type is not None:
        filters.append(Reminder.type == reminder_type)
    query = query.where(*filters)
    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query)
    reminders = list(
        await session.scalars(query.order_by(Reminder.created_at.desc()).limit(limit).offset(offset))
    )
    return ReminderPage(
        items=[await reminder_view(session, reminder) for reminder in reminders],
        total=total or 0,
        limit=limit,
        offset=offset,
    )


@router.get("/{reminder_id}", response_model=ReminderView)
async def view_reminder(reminder_id: UUID, request: Request, session: Session) -> ReminderView:
    principal = require_principal(request)
    reminder = await get_reminder(session, reminder_id)
    if principal.role is Role.MEMBER:
        assignment = await session.scalar(
            select(Assignment.id).where(
                Assignment.reminder_id == reminder.id, Assignment.user_id == principal.user_id
            )
        )
        if assignment is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder was not found")
    return await reminder_view(session, reminder)


@router.patch("/{reminder_id}", response_model=ReminderView)
async def update_reminder(
    reminder_id: UUID, body: ReminderUpdate, request: Request, session: Session
) -> ReminderView:
    principal = require_admin(request)
    reminder = await get_reminder(session, reminder_id)
    changes = body.model_dump(exclude_unset=True)
    if reminder.type is ReminderType.DAILY and changes.get("monthly_due_day") is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Daily reminders have no due day")
    if reminder.type is ReminderType.MONTHLY and changes.get("secondary_reminder_time") is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Monthly reminders have no second time")
    primary = changes.get("reminder_time", reminder.reminder_time)
    secondary = changes.get("secondary_reminder_time", reminder.secondary_reminder_time)
    if secondary is not None and secondary == primary:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Daily reminder times must be different")
    for field, value in changes.items():
        setattr(reminder, field, value)
    add_outbox(session, reminder, "reminder.updated", {"fields": list(changes)})
    await add_audit(
        session,
        request,
        actor_id=principal.user_id,
        action="ADMIN_UPDATED_REMINDER",
        reminder_id=reminder.id,
        metadata={"fields": list(changes)},
    )
    await session.commit()
    return await reminder_view(session, reminder)


async def set_enabled(
    reminder_id: UUID, enabled: bool, request: Request, session: AsyncSession
) -> ReminderView:
    principal = require_admin(request)
    reminder = await get_reminder(session, reminder_id)
    reminder.is_active = enabled
    add_outbox(session, reminder, "reminder.updated", {"is_active": enabled})
    await add_audit(
        session,
        request,
        actor_id=principal.user_id,
        action="ADMIN_ENABLED_REMINDER" if enabled else "ADMIN_DISABLED_REMINDER",
        reminder_id=reminder.id,
    )
    await session.commit()
    return await reminder_view(session, reminder)


@router.post("/{reminder_id}/enable", response_model=ReminderView)
async def enable(reminder_id: UUID, request: Request, session: Session) -> ReminderView:
    return await set_enabled(reminder_id, True, request, session)


@router.post("/{reminder_id}/assignments", response_model=ReminderView)
async def add_assignments(reminder_id: UUID, body: AddAssignments, request: Request, session: Session) -> ReminderView:
    principal = require_admin(request)
    reminder = await get_reminder(session, reminder_id)
    existing = set(await session.scalars(select(Assignment.user_id).where(Assignment.reminder_id == reminder.id)))
    requested = list(dict.fromkeys(body.user_ids))
    headers = {"Authorization": request.headers["Authorization"]}
    added: list[str] = []
    async with httpx.AsyncClient(timeout=10) as client:
        for user_id in requested:
            if user_id in existing:
                continue
            response = await client.get(f"{request.app.state.settings.auth_service_url}/api/v1/users/{user_id}", headers=headers)
            if response.status_code != 200 or not response.json()["is_active"]:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid or inactive member: {user_id}")
            member = response.json()
            session.add(Assignment(reminder_id=reminder.id, user_id=user_id, timezone=member["timezone"], created_at=utc_now()))
            added.append(str(user_id))
    if added:
        add_outbox(session, reminder, "reminder.assigned", {"user_ids": added})
        await add_audit(session, request, actor_id=principal.user_id, action="ADMIN_ASSIGNED_REMINDER", reminder_id=reminder.id, metadata={"user_ids": added})
        await session.commit()
    return await reminder_view(session, reminder)


@router.post("/{reminder_id}/disable", response_model=ReminderView)
async def disable(reminder_id: UUID, request: Request, session: Session) -> ReminderView:
    return await set_enabled(reminder_id, False, request, session)


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete(reminder_id: UUID, request: Request, session: Session) -> None:
    principal = require_admin(request)
    reminder = await get_reminder(session, reminder_id)
    reminder.is_active = False
    reminder.deleted_at = utc_now()
    add_outbox(session, reminder, "reminder.deleted", {})
    await add_audit(
        session,
        request,
        actor_id=principal.user_id,
        action="ADMIN_DELETED_REMINDER",
        reminder_id=reminder.id,
    )
    await session.commit()
