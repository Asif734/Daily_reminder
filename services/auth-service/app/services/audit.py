from uuid import UUID

from reminder_common.security import utc_now
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth import AuditLog


def record_audit(
    session: AsyncSession,
    *,
    actor_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID,
    request_id: str | None,
    metadata: dict[str, object] | None = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            request_id=request_id,
            audit_metadata=metadata or {},
            created_at=utc_now(),
        )
    )
