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
  from common-tier results (session rolls and wager payoffs alike),
  which auto-convert to a Fragment the moment they're rolled — a common
  has no other use, so there's no separate action to take.
- The wager: a declared weekly set point (modest/standard/ambitious,
  generated thresholds and bonuses) that earns a bonus Payoff roll if met
  — rolled against whichever unlocked region got the most attributed
  minutes that period. A declaration always applies to the period after
  whichever one is current, so it can never target an already-started
  period. Missing the target forfeits the bonus with no other penalty.
- A web dashboard (`GET /`, HTTP Basic auth) — the same status
  information as `scripts/status.py`, plus buttons to unlock a region,
  declare next period's wager, and trigger a manual refresh. Same
  FastAPI app, no separate service or JS build.

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

**A workout only earns rolls (and only counts toward the wager) if it
implies actual movement, not just duration.** Starting a workout and not
moving would otherwise earn full credit for elapsed time alone. The gate
uses the workout's own reported `distance` — not summed point-to-point
GPS deltas, which accumulate meaningful fake distance from accuracy
noise alone at ~1Hz sampling — against a low minimum-pace bar (see
`app/rewards/movement.py`). A workout with no distance data passes by
default; this is a movement check, not a data-completeness requirement.

**A payload the current schema can't parse is still captured, never
lost.** The endpoint always stores the raw body first; if parsing then
fails, `raw_ingest_events.parse_error` records why and the response
reports `"parsed": false`, but nothing is dropped. Once `app/schemas.py`
is fixed to match, rerun parsing for every previously-failed delivery
with:

```
python scripts/reparse_ingest_events.py
```

That's for deliveries that failed to parse. A payload that parsed fine
under an *older* schema (e.g. before a new field like `distance` was
added) isn't in that queue at all — it already "succeeded." For that
case, a one-off backfill script re-derives the new field from the still-
intact raw payload without creating new rows or re-triggering rolls; see
`scripts/backfill_workout_distance.py` for the pattern if another field
ever needs the same treatment.

```
python scripts/backfill_workout_distance.py
```

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

Recompute passive Fragment awards (safe to rerun any time; each day is
fully recomputed from raw, never accumulated) with:

```
python scripts/recompute_passive.py                    # yesterday and today
python scripts/recompute_passive.py 2026-08-01 2026-08-07   # explicit range, e.g. backfill
```

In production this runs on a timer (`deploy/systemd/`) — see
`deploy/README.md`. There's no ingest-time trigger for this the way
there is for session rolls; passive accrual only becomes real Fragments
once something recomputes it.

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

Spend Fragments to unlock a non-free region (safe to rerun — a no-op if
already unlocked, never a double charge) with:

```
python scripts/unlock_region.py <slug>
```

## Processing sessions and the wager

After ingest, resolve any workouts that don't have roll results yet
(safe to rerun — already-processed workouts are left untouched, since
rolling involves genuine randomness that's never recomputed) with:

```
python scripts/process_sessions.py
```

Declare a wager tier (`modest`, `standard`, or `ambitious`) — always
applies to the period after the current one:

```
python scripts/declare_wager.py standard
```

Resolve every completed period that doesn't have a payoff yet (safe to
rerun; in-progress periods are left alone):

```
python scripts/resolve_wager_payoffs.py
```

In production both of these run on a schedule (`deploy/systemd/`) —
see `deploy/README.md`.

## Checking your status

Two ways to see where things stand — same underlying data
(`app/status.py`), either works:

```
python scripts/status.py
```

or run the app (`uvicorn app.main:app --reload`) and open `http://127.0.0.1:8000/`,
prompting for `WEB_UI_USERNAME` / `WEB_UI_PASSWORD` (set in `.env`). The
web dashboard also has buttons to unlock a region, declare next
period's wager, and trigger the same refresh as
`process_sessions.py` + `resolve_wager_payoffs.py` combined.

`/collection` is the permanent view: every uncommon-or-better find
(session rolls and wager payoffs both), grouped rarest-first. Commons
convert straight to Fragments and never appear there — "recent finds"
on the dashboard is the short, mixed-tier activity feed; `/collection`
is the trophy case.

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
