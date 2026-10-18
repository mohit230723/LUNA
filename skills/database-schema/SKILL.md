---
name: Database Schema
description: Design the relational schema, migrations and seed data in SQLite or Postgres.
capabilities: [implement_database]
technologies: [SQLite, Postgres]
checklist:
  - id: schema
    text: A versioned migration creates every table with primary keys, NOT NULL, foreign keys, and indexes on lookup columns.
  - id: seed
    text: A repeatable seed script loads realistic sample rows and can be re-run without duplicating data.
---
You define how the application stores data. Use SQLite for local or single-user apps and
when the request says sqlite; use Postgres when it says postgres or needs concurrent writers.

## Model the data
- List the entities and relationships from the request before writing SQL. One table per
  entity, snake_case plural names (`todos`, `projects`), snake_case columns.
- Every table has `id` (`INTEGER PRIMARY KEY AUTOINCREMENT` in SQLite, `BIGINT GENERATED
  ALWAYS AS IDENTITY` or `UUID DEFAULT gen_random_uuid()` in Postgres), `created_at` and
  `updated_at` timestamps.
- Mark required columns `NOT NULL`, add `UNIQUE` where the domain demands it, and use
  `CHECK` constraints for small enums (for example `status IN ('open', 'done')`).
- Foreign keys use `REFERENCES parent(id) ON DELETE CASCADE` or `SET NULL` deliberately;
  index every foreign key column and every column used in WHERE or ORDER BY.

## Migrations
- Store plain SQL migrations in `db/migrations/` named `001_init.sql`, `002_<change>.sql`.
  Never edit an applied migration; add a new one.
- Provide one command to apply them (`python -m db.migrate`, `npm run db:migrate`, or an
  Alembic/Prisma setup if the project already uses one) that records applied versions in a
  `schema_migrations` table.
- SQLite: run `PRAGMA foreign_keys = ON;` on every connection and keep the file at
  `data/app.db` (gitignored). Postgres: read `DATABASE_URL` from the environment.

## Seed data
- `db/seed.sql` or a seed script inserts 5 to 20 realistic rows per table that the frontend
  can display. Use `INSERT ... ON CONFLICT DO NOTHING` (both engines) so re-runs are safe.
- Never seed real personal data or credentials.

## Hand-off
- Document every table and column in `db/README.md` with its type and meaning.
- Expose a small data-access module (`api/db.py` or `api/src/db.ts`) that opens connections
  and runs parameterised queries, so the backend task does not write raw connection code.
- Run the migrations and seed against an empty database twice and report the row counts.
