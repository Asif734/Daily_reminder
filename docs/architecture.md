# Reminder Platform Architecture

## Repository structure

```text
apps/
  admin-web/                 # Next.js admin application (Phase 6)
  desktop/                   # Tauri member application (Phase 7)
services/
  api-gateway/               # Public REST boundary and request routing
  auth-service/              # Credentials, JWTs, refresh sessions and RBAC identity
  user-service/              # Member profile, lifecycle and device management
  reminder-service/          # Definitions, assignments, occurrences and reports
  scheduler-service/         # Periodic occurrence generation and delivery eligibility
packages/
  reminder-common/           # Small Python observability/config package
  api-client/                # Generated OpenAPI TypeScript client (later phase)
  shared-types/              # UI-only shared types (later phase)
infrastructure/
  postgres/                  # Database initialization
docs/                        # Architecture and delivery plans
docker-compose.yml
```

The initial deployment uses one PostgreSQL cluster and one database, with service-owned
schemas (`auth`, `users`, `reminders`, `audit`). Cross-service writes are forbidden. This is
a pragmatic modular-monolith data topology for the MVP: services remain independently
deployable, and a schema can move to its own database later behind the owning API.

## Service boundaries

| Service | Owns | Does not own |
| --- | --- | --- |
| API Gateway | Public `/api/v1`, correlation IDs, CORS, routing, coarse rate limiting | Business data or credentials |
| Auth | Password hashes, login, access/refresh tokens, token rotation/revocation, identity claims | Member profile editing or reminders |
| User | Member profiles, active state, timezones, devices | Password verification or reminder rules |
| Reminder | Reminder definitions, assignment snapshots, occurrences, snoozes, completion, reports | Authentication or desktop delivery |
| Scheduler | Stateless periodic scans, occurrence generation requests, notification eligibility events | Canonical reminder records |
| Notification/delivery | Deferred until required; desktop pull/sync is MVP delivery | Canonical occurrence status |

The gateway is the only client-facing backend. Internal REST endpoints are network-private.
Services validate signed JWTs themselves rather than trusting forwarded role headers.

## PostgreSQL model

All IDs are UUIDs and timestamps are timezone-aware UTC (`timestamptz`). Human reminder
times are stored as `time` and interpreted using the assignment user's IANA timezone.

| Table | Important fields and relationships |
| --- | --- |
| `auth.users` | `id`, unique normalized `email`, `password_hash`, `role`, `is_active`, `last_login_at`, timestamps |
| `auth.refresh_tokens` | `id`, `user_id -> users`, unique token hash, token family, expiry/revocation/replacement timestamps |
| `users.profiles` | `user_id -> auth.users`, name, timezone, timestamps |
| `users.devices` | `id`, `user_id`, unique `(user_id, device_identifier)`, name, platform, app version, timezone, last seen |
| `reminders.reminders` | definition, type, local reminder time, monthly due day, days before, priority, active/deleted timestamps, creator |
| `reminders.assignments` | `reminder_id`, `user_id`, assigned timezone snapshot, unique pair; `ALL` expands to rows transactionally |
| `reminders.occurrences` | `reminder_id`, `assignment_id`, `user_id`, cycle key, scheduled/due/next-notification timestamps, status, snooze/completion/device fields; unique assignment + cycle |
| `reminders.snooze_events` | immutable occurrence/user/from/until/device record |
| `audit.audit_logs` | actor, action, resource type/id, JSON metadata, request ID, timestamp; append-only |
| `reminders.outbox_events` | aggregate, event type, JSON payload, created/published/attempt fields |

Assignments are a snapshot: selecting all members means all currently active members, not
future members. Occurrence `cycle_key` is the user's local date for daily reminders and
`YYYY-MM` for monthly reminders. Foreign IDs crossing service ownership are UUID references
without database foreign keys; each owning service maintains its own referential integrity.

## Communication

- Clients call the gateway using HTTPS REST. The gateway proxies to the owning service and
  propagates `X-Request-ID`, authorization, and trace context.
- Auth/user/reminder synchronous validation uses private REST with short timeouts and no
  retry on mutations unless an idempotency key is supplied.
- Domain changes write an outbox event in the same transaction. A publisher dispatches
  `user.created`, `user.deactivated`, `reminder.created`, `reminder.updated`,
  `reminder.assigned`, `reminder.completed`, and `reminder.snoozed` through Redis/Celery.
- Celery Beat triggers coarse scans. Workers ask the reminder service to atomically claim
  due work. No permanent per-reminder Celery schedules are created.
- Desktop incremental sync uses an opaque cursor derived from `updated_at` plus UUID, and
  mutations carry idempotency keys. The client outbox retries completion/snooze safely.

Redis is transport and ephemeral coordination, never the system of record. PostgreSQL is
authoritative. A transactional outbox prevents committed state from losing its event.

## Docker topology

`postgres` and `redis` live on a private backend network with persistent volumes. Four
FastAPI containers and Celery worker/beat containers use the same immutable scheduler image.
Only the gateway port is required by clients; service ports are published in the development
profile for diagnostics. Startup uses health-gated dependencies and application readiness
checks verify PostgreSQL and Redis.

## Edge cases and decisions

- DST gaps/overlaps: calculate in the user's IANA timezone. Shift nonexistent local times
  forward to the first valid instant; choose the earlier instant for ambiguous times and
  guarantee uniqueness with `cycle_key`.
- Timezone changes affect future unmaterialized occurrences; already-created occurrences
  remain fixed UTC instants for auditability.
- Monthly day 29-31 clamps to the month's last calendar day. `days_before` may cross a month
  or year boundary. Leap years use Gregorian calendar rules.
- Daily completion belongs to one local calendar date. Monthly completion belongs to one
  `YYYY-MM` cycle and never alters the definition.
- Concurrent workers use row locking/claim timestamps and unique constraints so occurrence
  generation and notification delivery are idempotent.
- Snooze after completion is rejected. Completion is idempotent. Multiple devices converge
  on server state; stale client writes return the canonical occurrence.
- Deactivation and reminder disablement prevent future generation/delivery but retain all
  definitions, assignments, occurrences, snoozes, and audits.
- Delete is soft delete. Reactivation does not retroactively create occurrences unless an
  explicit future policy says so.
- An overdue monthly reminder continues daily at local configured time. `next_notification_at`
  prevents duplicate delivery and allows frequency to become configurable.
- All-members assignment races are handled in one transaction against an active-user
  snapshot. A member activated after that transaction is not assigned.
- Offline queues require stable device IDs, idempotency keys, bounded retry/backoff, and a
  server cursor that does not lose rows sharing the same `updated_at`.

