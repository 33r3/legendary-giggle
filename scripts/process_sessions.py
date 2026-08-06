"""Processes every workout that doesn't yet have roll results. Safe to
rerun — already-processed workouts are left untouched (see
app.rewards.session_execution.process_session).
"""

from sqlalchemy import select

from app.db import SessionLocal
from app.geo.attribution import load_region_polygons
from app.models import Region, Workout, WorkoutRollResult
from app.rewards.session import current_session_tier_config
from app.rewards.session_execution import process_session


def main() -> None:
    db = SessionLocal()
    try:
        session_config = current_session_tier_config(db)
        if session_config is None:
            raise RuntimeError("no session tier config materialized")

        loaded_regions = load_region_polygons(db.query(Region).all())

        processed_workout_ids = {
            row[0] for row in db.execute(select(WorkoutRollResult.workout_id).distinct())
        }
        pending = [w for w in db.query(Workout).all() if w.id not in processed_workout_ids]

        total_results = 0
        for workout in pending:
            results = process_session(db, workout, loaded_regions, session_config)
            total_results += len(results)

        print(f"processed {len(pending)} workout(s), {total_results} roll result(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
