"""One-time backfill: populates distance_meters for workouts ingested
before distance parsing existed. The raw payload was never lost
(append-only), so this re-derives it directly — no new rows, no
re-triggered rolls, safe to rerun (only ever touches rows that are
still missing a value).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import IngestEvent, Workout
from app.rewards.movement import distance_to_meters
from app.schemas import IngestPayload


def backfill_workout_distance(db: Session) -> tuple[int, int]:
    """Returns (updated, skipped)."""
    missing = db.execute(select(Workout).where(Workout.distance_meters.is_(None))).scalars().all()

    updated = 0
    skipped = 0
    for workout in missing:
        event = db.get(IngestEvent, workout.ingest_event_id)
        payload = IngestPayload.model_validate_json(event.raw_payload)

        # SQLite round-trips DateTime(timezone=True) columns as naive
        # (same wall-clock numbers, tzinfo dropped) — workout.start_time
        # here is already naive, so the freshly re-parsed (aware) values
        # from the payload need the same normalization before comparing.
        match = next(
            (
                w
                for w in payload.data.workouts
                if w.start.replace(tzinfo=None) == workout.start_time
                and w.end.replace(tzinfo=None) == workout.end_time
            ),
            None,
        )
        if match is None or match.distance is None:
            skipped += 1
            continue

        meters = distance_to_meters(match.distance.qty, match.distance.units)
        if meters is None:
            skipped += 1
            continue

        workout.distance_meters = meters
        updated += 1

    db.commit()
    return updated, skipped


def main() -> None:
    db = SessionLocal()
    try:
        updated, skipped = backfill_workout_distance(db)
        print(f"backfilled {updated} workout(s), {skipped} left without distance data")
    finally:
        db.close()


if __name__ == "__main__":
    main()
