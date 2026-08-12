# Incremental implementation plan

## Phase 1 — Infrastructure (complete)

- Monorepo skeleton and architectural decisions
- PostgreSQL 16, Redis 7, gateway, three domain API services, Celery worker and beat
- Typed environment settings, JSON structured logs and correlation IDs
- Liveness/readiness endpoints, Docker health checks and persistent volumes
- Smoke tests, lint/type-check configuration and local operator documentation

## Phase 2 — Authentication (complete)

- Alembic foundation and initial auth migration
- User/refresh-token models, Argon2 hashing, JWT access tokens and rotating refresh families
- Login throttling, logout/revocation, `/me`, password change and initial-admin seed command
- Authentication, disabled-user, rotation/replay and RBAC tests

## Phase 3 — User management (complete)

- Member/device migrations and admin-only CRUD/lifecycle APIs
- Search/filter/pagination, password reset orchestration and audit records
- Deactivation preserves history and revokes active refresh sessions

## Phase 4 — Reminder management (complete)

- Reminder/assignment migrations and CRUD
- Transactional single/multiple/all-active assignment snapshot semantics
- Validation, soft delete, audit/outbox and member visibility APIs

## Phase 5 — Reminder engine (complete)

- Timezone-safe daily/monthly occurrence calculator and calendar edge-case tests
- Idempotent materialization, claim loop, overdue transitions, snooze and completion
- Celery periodic scans, notification eligibility, incremental desktop sync API

## Phase 6 — Admin web (complete)

- Next.js strict TypeScript application, shadcn/ui, Tailwind and TanStack Query
- Generated API client, authentication shell, dashboard, members, reminders and reports
- Essential component, accessibility and API-boundary tests

## Phase 7 — Desktop (source complete; native build verification requires Rust)

- Tauri 2 shell, secure token storage, SQLite cache/migrations and sync outbox
- Local scheduler/native notifications, compact action window, tray and autostart
- Offline, conflict, reconnect and local scheduling tests; Windows-first packaging

## Phase 8 — hardening

- Full integration/e2e suite, OpenTelemetry-ready observability, indexes and query review
- Secrets/TLS/deployment guidance, backups/restore, dependency scanning and runbooks
- Load tests for scheduler claiming and sync endpoints
