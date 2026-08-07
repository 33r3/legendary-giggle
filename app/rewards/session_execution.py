"""Turns a completed workout into persisted roll results.

Unlike passive Fragments, this is not a pure function of raw data — real
randomness happens at roll-resolution time — so it's never recomputed.
Once a workout has results, re-processing it is a no-op.
"""

import random
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.geo.attribution import LoadedRegion, attribute_route_minutes, load_region_polygons
from app.loot.tables import load_table_for_region, resolve_roll
from app.models import Region, SessionTierConfig, Workout, WorkoutRollResult
from app.rewards.fragments import record_common_conversion
from app.rewards.movement import passes_movement_gate
from app.rewards.session import current_session_tier_config, session_roll_counts
from app.rewards.unlocks import is_region_unlocked


def process_session(
    db: Session,
    workout: Workout,
    loaded_regions: list[LoadedRegion],
    session_config: SessionTierConfig,
    rng: random.Random | None = None,
) -> list[WorkoutRollResult]:
    existing = db.execute(
        select(WorkoutRollResult).where(WorkoutRollResult.workout_id == workout.id)
    ).scalars().all()
    if existing:
        return list(existing)

    if not passes_movement_gate(workout):
        return []

    rng = rng or random.Random()

    minutes_by_region = attribute_route_minutes(workout.route_points, loaded_regions)
    rolls_by_region = session_roll_counts(minutes_by_region, session_config)

    results: list[WorkoutRollResult] = []
    for region_id, roll_count in rolls_by_region.items():
        region = db.get(Region, region_id)
        if region is None or not is_region_unlocked(db, region):
            continue

        table = load_table_for_region(db, region_id)
        if table is None:
            continue

        for _ in range(roll_count):
            outcome = resolve_roll(table, rng.randint(1, 100), rng=rng)
            if outcome is None:
                continue
            result = WorkoutRollResult(
                workout_id=workout.id,
                region_id=region_id,
                tier=outcome.tier,
                item_name=outcome.item_name,
                rolled_at=datetime.now(timezone.utc),
            )
            db.add(result)
            results.append(result)

            if outcome.tier == "common":
                record_common_conversion(db, outcome.item_name, region_id)

    db.commit()
    for result in results:
        db.refresh(result)
    return results


def process_pending_sessions(db: Session) -> tuple[int, list[WorkoutRollResult]]:
    """Processes every workout that doesn't yet have roll results. Safe to
    rerun — already-processed workouts are left untouched. Returns
    (workouts processed, all results produced)."""
    session_config = current_session_tier_config(db)
    if session_config is None:
        raise RuntimeError("no session tier config materialized")

    loaded_regions = load_region_polygons(db.query(Region).all())

    processed_workout_ids = {
        row[0] for row in db.execute(select(WorkoutRollResult.workout_id).distinct())
    }
    pending = [w for w in db.query(Workout).all() if w.id not in processed_workout_ids]

    all_results: list[WorkoutRollResult] = []
    for workout in pending:
        all_results.extend(process_session(db, workout, loaded_regions, session_config))

    return len(pending), all_results
