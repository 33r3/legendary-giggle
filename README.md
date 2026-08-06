# legendary-giggle

Self-hosted exercise gamification service. Design doc: `exercise-rpg-design.md`.

## Status

- Phase 2 (minimal ingest): a FastAPI webhook that receives HealthKit export
  data and writes it to append-only raw storage.
- Phase 3 (passive tier): Fragment accrual from ambient step counts, computed
  as a derived layer from raw steps — never written during ingestion, always
  safe to recompute. The reward curve's actual numbers are generated from a
  seed at deploy time rather than committed (see "Content and tuning values"
  below).
- Phase 4 (session tier, partial): region polygon loading (from committed
  files under `content/regions/`) and time-weighted route attribution
  (bucketing a workout's minutes by region), plus the roll-count mechanic
  (how many table rolls a session earns per region). Region boundaries are
  flat for now — hierarchy is a later schema decision. Rolling against
  actual drop tables isn't built yet.

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

## Content and tuning values

Two different storage rules apply here, by design:

- **`content/`** (e.g. `content/regions/*.geojson`) holds real, committed
  game content — regions and, later, drop tables. If you don't want to see
  what's in a region or table ahead of finding it in play, don't open files
  under this directory; everything else in the repo (chat, commits, logs,
  tests) is written to avoid naming what's in there regardless.
- Reward-curve tuning (the passive-tier floor/rate/cap, the session-tier
  roll cap) is **generated from `GAME_SEED`, not committed** — set a real
  seed in production and keep it out of version control.

Materialize the current reward curves after migrating:

```
python scripts/materialize_economy.py
```

Recompute Fragment awards for a date range (safe to rerun any time; each
day is fully recomputed from raw, never accumulated) with:

```
python scripts/recompute_passive.py 2026-08-01 2026-08-07
```

Load all region boundaries from `content/regions/*.geojson` (safe to rerun
— upserts by slug) with:

```
python scripts/load_regions.py
```

Invalid geometry fails loudly at load time rather than silently corrupting
attribution later.

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
