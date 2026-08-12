FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN addgroup --system reminder && adduser --system --ingroup reminder reminder
COPY packages/reminder-common /tmp/reminder-common
COPY services/api-gateway /app
RUN pip install --upgrade pip && pip install '/tmp/reminder-common' '.[dev]'
USER reminder
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

