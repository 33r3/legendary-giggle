import json
from datetime import datetime, timezone

from app.ingest import store_raw_event
from app.models import Workout
from scripts.backfill_workout_distance import backfill_workout_distance

# Shape of a real delivery from before distance parsing existed — no
# "distance" key at all on the workout.
OLD_PAYLOAD = {
    "data": {
        "metrics": [],
        "workouts": [
            {
                "id": "old-workout-1",
                "name": "Outdoor Walk",
                "start": "2026-08-01 09:00:00 -0500",
                "end": "2026-08-01 09:20:00 -0500",
                "route": [],
            }
        ],
    }
}

NEW_PAYLOAD = {
    "data": {
        "metrics": [],
        "workouts": [
            {
                "id": "new-workout-1",
                "name": "Outdoor Walk",
                "start": "2026-08-02 09:00:00 -0500",
                "end": "2026-08-02 09:20:00 -0500",
                "distance": {"qty": 1.5, "units": "km"},
                "route": [],
            }
        ],
    }
}


def make_old_workout(db_session, payload_dict) -> Workout:
    """Simulates a workout that was ingested (and successfully parsed)
    before distance_meters existed — inserted directly, bypassing the
    current ingest path, with the raw payload stored as it really would
    have been."""
    event = store_raw_event(db_session, json.dumps(payload_dict))
    workout_payload = payload_dict["data"]["workouts"][0]
    workout = Workout(
        ingest_event_id=event.id,
        external_id=workout_payload["id"],
        workout_type=workout_payload["name"],
        source="unknown",
        start_time=datetime.strptime(workout_payload["start"], "%Y-%m-%d %H:%M:%S %z"),
        end_time=datetime.strptime(workout_payload["end"], "%Y-%m-%d %H:%M:%S %z"),
        duration_seconds=1200,
        distance_meters=None,
    )
    db_session.add(workout)
    db_session.commit()
    db_session.refresh(workout)
    return workout


def test_backfill_populates_distance_from_raw_payload(db_session):
    workout = make_old_workout(db_session, NEW_PAYLOAD)

    updated, skipped = backfill_workout_distance(db_session)

    assert (updated, skipped) == (1, 0)
    db_session.refresh(workout)
    assert workout.distance_meters == 1500


def test_backfill_skips_workouts_with_no_distance_in_raw_payload(db_session):
    make_old_workout(db_session, OLD_PAYLOAD)

    updated, skipped = backfill_workout_distance(db_session)

    assert (updated, skipped) == (0, 1)


def test_backfill_does_not_touch_already_populated_workouts(db_session):
    workout = make_old_workout(db_session, NEW_PAYLOAD)
    workout.distance_meters = 42.0
    db_session.commit()

    updated, skipped = backfill_workout_distance(db_session)

    assert (updated, skipped) == (0, 0)
    db_session.refresh(workout)
    assert workout.distance_meters == 42.0
