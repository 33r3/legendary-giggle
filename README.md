# legendary-giggle

Self-hosted exercise gamification service. Design doc: `exercise-rpg-design.md`.

## Status

Phase 2 (minimal ingest) scaffold: a FastAPI webhook that receives HealthKit
export data and writes it to append-only raw storage. No reward computation,
regions, or drop tables live here — those are derived layers built on top of
this raw data later.

## Running locally

```
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # set INGEST_WEBHOOK_TOKEN
alembic upgrade head
uvicorn app.main:app --reload
```

## Ingest

`POST /ingest/healthkit` accepts a JSON export payload (step-count metrics
and workouts, following the shape produced by common HealthKit export apps
that support posting to a custom REST endpoint) and requires
`Authorization: Bearer <INGEST_WEBHOOK_TOKEN>`.

Every delivery is stored verbatim in `raw_ingest_events`, plus parsed into
`raw_step_samples`, `raw_workouts`, and `raw_workout_route_points`. Nothing
is deduplicated or updated at ingest time — per the project's raw-data
invariant, cross-source step dedup and any other aggregation happens later
in a derived layer, computed from this raw data, so retuning it never
requires re-ingesting.

## Migrations

Schema changes go through Alembic:

```
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Tests

```
python -m pytest
```
