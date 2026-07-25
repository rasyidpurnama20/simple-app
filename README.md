# OBE System

An Outcome-Based Education (OBE) management system built as a **Django +
PostgreSQL modular monolith**. This repository currently implements **Task 1**
of the implementation plan: project scaffolding, Docker Compose, and the
shared/core foundation (production-readiness base model, explainable
validation, and the in-app Role_Switcher with a persistent development banner).

## Run it

You need Docker with the Compose plugin. From the repository root:

```bash
docker compose up -d --build
```

Then open:

```
http://localhost:8000
```

This starts two containers:

- **web** — the Django application. On startup it waits for the database,
  applies all migrations (which also seed a demo Program of Study and the
  Kaprodi / Lecturer demo users), then serves the app on port 8000.
- **db** — PostgreSQL 16 with a persistent named volume and a healthcheck.
  The web container starts only after the database is healthy.

The startup is safe to re-run: migrations and the demo seed are idempotent.

To stop everything:

```bash
docker compose down
```

To also remove the database volume:

```bash
docker compose down -v
```

## What you can see

The landing page (Home workspace) shows:

- A persistent **DEVELOPMENT — BUKAN DATA RESMI** banner (synthetic data,
  no real authentication).
- A **"Lihat sebagai <role>"** Role_Switcher that swaps the active demo user
  between Kaprodi and Lecturer. Switching the role changes the list of
  available actions.
- The five planned workspaces (Home, Timeline, Curriculum, Learning,
  Attainment & Quality). Only Home is functional in Task 1.

## Architecture

- **Thin views, fat services.** Views parse input and call exactly one service
  method; all business logic and validation live in the service layer and
  raise `DomainError`. This is the seam that makes a future JSON API a drop-in
  adapter.
- **Module packages.** Each module (`core`, `timeline`, `curriculum`, `rps`,
  `attainment`, `injection`, `web`) follows the convention of `models.py`,
  `services.py`, `validators.py`, `dtos.py`.
- **Production-readiness fields.** Every business entity extends the abstract
  `core.ProductionReadinessModel` (prodi, owner, status, version, creator,
  created_time, modified_time).
- **Schema via migrations only** — never ad-hoc seed scripts.
- **All DB access through the Django ORM** with parameterized queries.

## Configuration

Database connection settings are read from environment variables (with
defaults matching `docker-compose.yml`):

| Variable | Default |
|---|---|
| `POSTGRES_DB` | `obe_system` |
| `POSTGRES_USER` | `obe` |
| `POSTGRES_PASSWORD` | `obe_password` |
| `POSTGRES_HOST` | `db` |
| `POSTGRES_PORT` | `5432` |

## Tests (optional)

Property-based (Hypothesis) and unit tests for the core foundation run with
pytest inside the web container:

```bash
docker compose run --rm web pytest
```
