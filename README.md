# Reminder Platform

Production-oriented monorepo for an internal reminder system. Phase 1 provides the backend
runtime foundation; domain APIs, web UI, and desktop client arrive in the documented phases.

## Prerequisites

- Docker Engine with Docker Compose v2
- Optional for host-side development: Python 3.11

## Start the Phase 1 stack

```bash
cp .env.example .env
# Replace JWT_SECRET and, outside throwaway local development, POSTGRES_PASSWORD.
docker compose up --build -d
docker compose ps
curl http://localhost:8000/health/live
curl http://localhost:8000/health/ready
```

Development diagnostic ports are `8001` (auth), `8002` (users), `8003` (reminders),
`5432` (PostgreSQL), and `6379` (Redis). Client applications should use only the gateway on
port `8000`. Swagger is available at `http://localhost:8000/docs` outside production.

Set the initial administrator in `.env` before the first startup:

```bash
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=replace-with-a-strong-password
INITIAL_ADMIN_NAME=System Administrator
```

The auth container creates this administrator after applying migrations. Bootstrap is
idempotent: if the email already exists, startup does not overwrite its password. Use the
authenticated change-password API to rotate an existing administrator password.

Authentication and member management are exposed through `http://localhost:8000/api/v1`:

- `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`, `/auth/change-password`
- `/users` list/create and `/users/{id}` view/edit
- `/users/{id}/activate`, `/deactivate`, and `/reset-password`
- `/devices/register` for authenticated desktop clients

Member listing supports `search`, `active`, `limit`, and `offset`. Member management requires
an `ADMIN` access token.

Reminder management is available at `/api/v1/reminders`. Administrators can create daily or
monthly definitions assigned to one, multiple, or all currently active members; list, view,
edit, enable, disable, and soft-delete them. Members can list or view only reminders assigned
to them. Definition and assignment events are recorded in the transactional outbox.

The reminder engine materializes idempotent daily and monthly occurrences every minute.
Members use `/api/v1/me/reminders` (with optional incremental `cursor`) and its `today`,
`upcoming`, `overdue`, and `completed` sections. Occurrences support `/complete` and `/snooze`;
valid snooze durations are 10, 30, 60, and 120 minutes.

The admin dashboard is available at `http://localhost:3000`. It includes login, operational
dashboard cards, member search/filter/create/lifecycle controls, reminder listing and creation,
reports navigation, and settings. Run its standalone checks with:

```bash
cd apps/admin-web
npm ci
npm run lint
npm test
npm run build
```

The Tauri 2 member client lives in `apps/desktop`. It provides local SQLite caching, an offline
action outbox, native notification scheduling, secure session persistence, two-minute sync,
system-tray behavior, and autostart. See `apps/desktop/README.md` for platform prerequisites.

Stop containers without deleting data:

```bash
docker compose down
```

To deliberately remove local database/Redis state, use `docker compose down --volumes`.
That command is destructive and should never be used against a valued environment.

## Verification

Validate Compose, execute tests, and lint each independently deployable image:

```bash
docker compose config --quiet
make test
make lint
```

For a full boot smoke test:

```bash
docker compose up --build -d --wait
docker compose ps
docker compose logs scheduler-worker scheduler-beat
```

Read [architecture decisions](docs/architecture.md) and the
[implementation plan](docs/implementation-plan.md) before adding domain behavior.

## Configuration

Configuration is environment-only and typed with Pydantic Settings. `.env.example` documents
safe development defaults but `.env` is ignored. PostgreSQL uses a persistent named volume;
Redis uses AOF persistence for local resilience. All application logs are JSON and every HTTP
response includes or propagates `X-Request-ID`.

## Database changes

The initialization script creates only service-owned schemas. Beginning in Phase 2, Alembic
is the sole mechanism for table/schema changes; applications will never call `create_all()`.
