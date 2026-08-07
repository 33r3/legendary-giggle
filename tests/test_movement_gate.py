from datetime import datetime, timezone

from app.models import IngestEvent, Workout
from app.rewards.movement import distance_to_meters, passes_movement_gate


def make_workout(distance_meters, duration_seconds) -> Workout:
    return Workout(
        ingest_event_id=1,
        workout_type="Walk",
        source="Test",
        start_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        duration_seconds=duration_seconds,
        distance_meters=distance_meters,
    )


def test_distance_to_meters_converts_known_units():
    assert distance_to_meters(1, "km") == 1000
    assert distance_to_meters(1, "m") == 1
    assert distance_to_meters(1, "mi") == 1609.344


def test_distance_to_meters_unknown_unit_returns_none():
    assert distance_to_meters(1, "furlongs") is None


def test_missing_distance_passes_by_default():
    assert passes_movement_gate(make_workout(distance_meters=None, duration_seconds=2700)) is True


def test_idle_workout_fails_gate():
    # 45 minutes, ~30m of GPS jitter — far below any real walking pace.
    assert passes_movement_gate(make_workout(distance_meters=30, duration_seconds=2700)) is False


def test_real_walk_passes_gate():
    # ~0.6km in 7.5 minutes, matching an actual captured walk.
    assert passes_movement_gate(make_workout(distance_meters=600, duration_seconds=450)) is True


def test_zero_duration_fails_gate():
    assert passes_movement_gate(make_workout(distance_meters=100, duration_seconds=0)) is False
