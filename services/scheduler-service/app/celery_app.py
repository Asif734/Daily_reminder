from celery import Celery
from celery.schedules import crontab
from reminder_common.config import get_settings
from reminder_common.logging import configure_logging

settings = get_settings().model_copy(update={"service_name": "scheduler-service"})
configure_logging(settings.service_name, settings.log_level)

celery_app = Celery(
    "reminder_scheduler",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.scan"],
)
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    enable_utc=True,
    timezone="UTC",
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scan-due-occurrences-every-minute": {
            "task": "scheduler.scan_due_occurrences",
            "schedule": crontab(minute="*"),
        }
    },
)
