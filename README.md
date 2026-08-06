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
- Phase 4 (session tier): region polygon loading (from committed files
  under `content/regions/`), time-weighted route attribution (bucketing a
  workout's minutes by region), the roll-count mechanic (how many table
  rolls a session earns per region), drop tables (`content/tables/`, one
  per region), and end-to-end session execution — a workout resolves real
  rolls and persists them, gated on the region being unlocked. Rolling is
  never recomputed (genuine randomness happens at resolution time), unlike
  the passive tier. Region boundaries are flat for now — hierarchy is a
  later schema decision.
- Phase 5 (region unlocks, the sink): Fragments spend to unlock a region
  permanently. Home is free (`always_unlocked`); other regions have a
  generated-not-committed cost. Fragments come from passive accrual and
  from converting common session results back to Fragments. The weekly
  wager/payoff-roll mechanic isn't wired up yet — sessions currently roll
  a plain d100 with no bonus.

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
and workouts) matching the shape produced by the Health Auto Export app's
REST API automation, and requires `Authorization: Bearer
<INGEST_WEBHOOK_TOKEN>`. Workouts have no stable id or source field in
that app's export — the schema treats both as optional.

Every delivery is stored verbatim in `raw_ingest_events`, plus parsed into
`raw_step_samples`, `raw_workouts`, and `raw_workout_route_points`. Step
samples are never deduplicated or updated at ingest time — cross-source
and cross-delivery dedup happens later, in the derived layer, computed
from this raw data (see `dedup_daily_steps`), so retuning it never
requires re-ingesting.

Workouts are the one exception: a workout with the same start/end as one
already ingested is skipped rather than appended, because export
automations typically resend a rolling window on every run, and unlike
passive Fragments, a session roll is never recomputed once it happens —
a duplicate workout row would mean a duplicate, permanent payout.

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

Then load drop tables from `content/tables/*.json` (safe to rerun — each
region's bands/items are fully replaced; requires that region's boundary
to already be loaded) with:

```
python scripts/load_drop_tables.py
```

Then materialize unlock costs for every non-free region (deterministic
per seed + region slug, so rerunning is a no-op unless `GAME_SEED`
changes) with:

```
python scripts/materialize_unlock_costs.py
```

Full local setup order: `alembic upgrade head`, then the four scripts
above (economy, regions, drop tables, unlock costs) in that order —
drop tables and unlock costs both need regions loaded first.

## Processing sessions

After ingest, resolve any workouts that don't have roll results yet
(safe to rerun — already-processed workouts are left untouched, since
rolling involves genuine randomness that's never recomputed) with:

```
python scripts/process_sessions.py
```

## Deployment

See `deploy/README.md` for the Ubuntu/nginx/systemd setup, secrets
handling, and backups.

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
