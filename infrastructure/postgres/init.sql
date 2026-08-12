-- Service-owned schemas. Application migrations will own all tables from Phase 2 onward.
CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS users;
CREATE SCHEMA IF NOT EXISTS reminders;
CREATE SCHEMA IF NOT EXISTS audit;

