FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN addgroup --system reminder && adduser --system --ingroup reminder reminder
COPY packages/reminder-common /tmp/reminder-common
COPY services/scheduler-service /app
RUN pip install --upgrade pip && pip install '/tmp/reminder-common' '.[dev]'
USER reminder
CMD ["celery", "-A", "app.celery_app:celery_app", "worker", "--loglevel=INFO"]

