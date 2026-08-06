# legendary-giggle

Self-hosted exercise gamification service. Design doc: `exercise-rpg-design.md`.

## Status

- Phase 2 (minimal ingest): a FastAPI webhook that receives HealthKit export
  data and writes it to append-only raw storage.
- Phase 3 (passive tier): Fragment accrual from ambient step counts, computed
  as a derived layer from raw steps — never written during ingestion, always
  safe to recompute. The reward curve's actual numbers are generated from a
  seed at deploy time rather than committed (see "Content and tuning values"
  below), same as regions and drop tables will be.
- Phase 4 (session tier, partial): region polygon loading and time-weighted
  route attribution (bucketing a workout's minutes by region), plus the
  roll-count mechanic (how many table rolls a session earns per region).
  Region boundaries are flat for now — hierarchy is a later schema decision.
  Rolling against actual drop tables (the content layer: item names, rarity,
  odds) isn't built yet.

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

Region, item, and reward-curve values are generated from `GAME_SEED`, not
committed as literals — set a real seed in production and keep it out of
version control. After migrating, materialize the current passive-tier
curve with:

```
python scripts/materialize_economy.py
```

Recompute Fragment awards for a date range (safe to rerun any time; each
day is fully recomputed from raw, never accumulated) with:

```
python scripts/recompute_passive.py 2026-08-01 2026-08-07
```

Region boundaries are different: only the player knows their own real-world
geography, so they aren't generated — they're supplied as a GeoJSON
`FeatureCollection` (`REGIONS_GEOJSON_PATH`, default `./data/regions.geojson`,
never committed) where each feature has `properties.slug`, `properties.name`,
and a `Polygon` geometry. Load it with:

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
