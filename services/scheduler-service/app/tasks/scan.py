import logging
from typing import Any

import httpx
from reminder_common.config import get_settings

from app.celery_app import celery_app

logger = logging.LoggerAdapter(logging.getLogger(__name__), {"service": "scheduler-service"})


@celery_app.task(name="scheduler.scan_due_occurrences")
def scan_due_occurrences() -> dict[str, Any]:
    """Ask the authoritative reminder service to materialize and transition occurrences."""
    settings = get_settings()
    with httpx.Client(timeout=20) as client:
        response = client.post(f"{settings.reminder_service_url}/internal/v1/scheduler/scan")
        response.raise_for_status()
    result: dict[str, Any] = response.json()
    logger.info("scheduler scan completed", extra={"request_id": None, "user_id": None})
    return result
