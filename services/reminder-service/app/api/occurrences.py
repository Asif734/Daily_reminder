import base64
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from reminder_common.security import require_admin, require_principal, utc_now
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.reminders import add_audit, add_outbox, db
from app.models.reminder import Occurrence, OccurrenceStatus, Reminder, SnoozeEvent
from app.schemas.occurrences import (
    CompleteRequest,
    DashboardStats,
    OccurrencePage,
    OccurrenceView,
    ReportOccurrence,
    ReportPage,
    ScanResult,
    SnoozeRequest,
)
from app.services.occurrences import materialize, update_due_states

router = APIRouter(tags=["occurrences"])
Session = Annotated[AsyncSession, Depends(db)]


def occurrence_view(occurrence: Occurrence, reminder: Reminder) -> OccurrenceView:
    return OccurrenceView(
        id=occurrence.id,
        reminder_id=occurrence.reminder_id,
        title=reminder.title,
        description=reminder.description,
        type=reminder.type,
        priority=reminder.priority,
        scheduled_date=occurrence.scheduled_at.date(),
        scheduled_at=occurrence.scheduled_at,
        due_at=occurrence.due_at,
        status=occurrence.status,
        snoozed_until=occurrence.snoozed_until,
        completed_at=occurrence.completed_at,
        updated_at=occurrence.updated_at,
    )


async def owned_occurrence(
    session: AsyncSession, occurrence_id: UUID, user_id: UUID
) -> tuple[Occurrence, Reminder]:
    row = (
        await session.execute(
            select(Occurrence, Reminder)
            .join(Reminder, Reminder.id == Occurrence.reminder_id)
            .where(
                Occurrence.id == occurrence_id,
                Occurrence.user_id == user_id,
                Reminder.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reminder occurrence was not found")
    return row


async def list_for_member(
    request: Request,
    session: AsyncSession,
    section: Literal["all", "today", "upcoming", "overdue", "completed"],
    cursor: str | None = None,
) -> OccurrencePage:
    principal = require_principal(request)
    now = utc_now()
    query = (
        select(Occurrence, Reminder)
        .join(Reminder, Reminder.id == Occurrence.reminder_id)
        .where(
            Occurrence.user_id == principal.user_id,
            Reminder.is_active.is_(True),
            Reminder.deleted_at.is_(None),
        )
    )
    if section == "today":
        start = datetime.combine(now.date(), datetime.min.time(), UTC)
        query = query.where(Occurrence.scheduled_at >= start, Occurrence.scheduled_at < start + timedelta(days=1))
    elif section == "upcoming":
        query = query.where(Occurrence.scheduled_at > now, Occurrence.status != OccurrenceStatus.COMPLETED)
    elif section == "overdue":
        query = query.where(Occurrence.status == OccurrenceStatus.OVERDUE)
    elif section == "completed":
        query = query.where(Occurrence.status == OccurrenceStatus.COMPLETED)
    if cursor:
        try:
            stamp, identifier = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
            updated, occurrence_id = datetime.fromisoformat(stamp), UUID(identifier)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid sync cursor") from exc
        query = query.where(
            or_(
                Occurrence.updated_at > updated,
                and_(Occurrence.updated_at == updated, Occurrence.id > occurrence_id),
            )
        )
    rows = (await session.execute(query.order_by(Occurrence.updated_at, Occurrence.id).limit(201))).all()
    page_rows = rows[:200]
    next_cursor = None
    if page_rows:
        last = page_rows[-1][0]
        next_cursor = base64.urlsafe_b64encode(f"{last.updated_at.isoformat()}|{last.id}".encode()).decode()
    return OccurrencePage(
        items=[occurrence_view(occurrence, reminder) for occurrence, reminder in page_rows],
        next_cursor=next_cursor,
    )


@router.get("/api/v1/me/reminders", response_model=OccurrencePage)
async def my_reminders(request: Request, session: Session, cursor: str | None = None) -> OccurrencePage:
    return await list_for_member(request, session, "all", cursor)


@router.get("/api/v1/me/reminders/{section}", response_model=OccurrencePage)
async def my_reminder_section(
    section: Literal["today", "upcoming", "overdue", "completed"], request: Request, session: Session
) -> OccurrencePage:
    return await list_for_member(request, session, section)


@router.get("/api/v1/reports/occurrences", response_model=ReportPage)
async def occurrence_report(request: Request, session: Session) -> ReportPage:
    require_admin(request)
    rows = (await session.execute(select(Occurrence, Reminder).join(Reminder, Reminder.id == Occurrence.reminder_id).where(Reminder.deleted_at.is_(None)).order_by(Occurrence.updated_at.desc()).limit(200))).all()
    total = await session.scalar(select(func.count()).select_from(Occurrence))
    user_ids = {item.user_id for item, _ in rows}
    names: dict[UUID, str] = {}
    headers = {"Authorization": request.headers["Authorization"]}
    async with httpx.AsyncClient(timeout=10) as client:
        for user_id in user_ids:
            response = await client.get(
                f"{request.app.state.settings.auth_service_url}/api/v1/users/{user_id}",
                headers=headers,
            )
            if response.status_code == 200:
                names[user_id] = response.json()["name"]
    return ReportPage(items=[ReportOccurrence(**occurrence_view(item, reminder).model_dump(), user_id=item.user_id, user_name=names.get(item.user_id, "Unknown member")) for item, reminder in rows], total=total or 0)


@router.get("/api/v1/reports/dashboard", response_model=DashboardStats)
async def dashboard_stats(request: Request, session: Session) -> DashboardStats:
    require_admin(request)
    now = utc_now()
    start = datetime.combine(now.date(), datetime.min.time(), UTC)
    end = start + timedelta(days=1)
    async def count(*filters: object) -> int:
        return (await session.scalar(select(func.count()).select_from(Occurrence).where(*filters))) or 0
    return DashboardStats(
        pending_today=await count(Occurrence.scheduled_at >= start, Occurrence.scheduled_at < end, Occurrence.status == OccurrenceStatus.PENDING),
        completed_today=await count(Occurrence.completed_at >= start, Occurrence.completed_at < end),
        overdue=await count(Occurrence.status == OccurrenceStatus.OVERDUE),
        snoozed=await count(Occurrence.status == OccurrenceStatus.SNOOZED),
    )


@router.post("/api/v1/reminder-occurrences/{occurrence_id}/complete", response_model=OccurrenceView)
async def complete(
    occurrence_id: UUID, body: CompleteRequest, request: Request, session: Session
) -> OccurrenceView:
    principal = require_principal(request)
    occurrence, reminder = await owned_occurrence(session, occurrence_id, principal.user_id)
    if occurrence.status is not OccurrenceStatus.COMPLETED:
        occurrence.status = OccurrenceStatus.COMPLETED
        occurrence.completed_at = utc_now()
        occurrence.completed_device_id = body.device_id
        occurrence.snoozed_until = None
        occurrence.next_notification_at = None
        add_outbox(session, reminder, "reminder.completed", {"occurrence_id": str(occurrence.id)})
        await add_audit(
            session,
            request,
            actor_id=principal.user_id,
            action="MEMBER_COMPLETED_REMINDER",
            reminder_id=reminder.id,
            metadata={"occurrence_id": str(occurrence.id)},
        )
        await session.commit()
    return occurrence_view(occurrence, reminder)


@router.post("/api/v1/reminder-occurrences/{occurrence_id}/snooze", response_model=OccurrenceView)
async def snooze(
    occurrence_id: UUID, body: SnoozeRequest, request: Request, session: Session
) -> OccurrenceView:
    if body.minutes not in body.allowed_minutes():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unsupported snooze duration")
    principal = require_principal(request)
    occurrence, reminder = await owned_occurrence(session, occurrence_id, principal.user_id)
    if occurrence.status is OccurrenceStatus.COMPLETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Completed reminders cannot be snoozed")
    now = utc_now()
    until = now + timedelta(minutes=body.minutes)
    occurrence.status = OccurrenceStatus.SNOOZED
    occurrence.snoozed_until = until
    occurrence.next_notification_at = until
    session.add(
        SnoozeEvent(
            occurrence_id=occurrence.id,
            user_id=principal.user_id,
            snoozed_from=now,
            snoozed_until=until,
            device_id=body.device_id,
            created_at=now,
        )
    )
    add_outbox(session, reminder, "reminder.snoozed", {"occurrence_id": str(occurrence.id), "until": until.isoformat()})
    await add_audit(
        session,
        request,
        actor_id=principal.user_id,
        action="MEMBER_SNOOZED_REMINDER",
        reminder_id=reminder.id,
        metadata={"occurrence_id": str(occurrence.id), "until": until.isoformat()},
    )
    await session.commit()
    return occurrence_view(occurrence, reminder)


@router.post("/internal/v1/scheduler/scan", response_model=ScanResult, include_in_schema=False)
async def scan(session: Session) -> ScanResult:
    now = utc_now()
    created = await materialize(session, now)
    changed = await update_due_states(session, now)
    await session.commit()
    return ScanResult(created=created, state_changes=changed)
