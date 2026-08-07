"""Guards against crediting a session where nothing actually happened —
started a workout, didn't move. Uses the workout's own reported distance
(HealthKit's fused accelerometer+GPS figure) rather than summing raw
point-to-point GPS deltas: at ~1Hz sampling, GPS accuracy noise alone
(a meter or two per reading) accumulates into meaningful fake distance
over thousands of samples, so naive point-math would credit standing
still almost as readily as walking.
"""

from app.models import Workout

# Well below normal walking pace (~1.1-1.4 m/s) — only meant to catch
# genuine idling, not to grade effort.
MIN_ACTIVE_PACE_METERS_PER_SECOND = 0.3

_METERS_PER_UNIT = {"m": 1.0, "km": 1000.0, "mi": 1609.344, "ft": 0.3048}


def distance_to_meters(qty: float, units: str) -> float | None:
    factor = _METERS_PER_UNIT.get(units.lower())
    if factor is None:
        return None
    return qty * factor


def passes_movement_gate(workout: Workout) -> bool:
    """A workout with no distance data at all passes by default — this
    is a movement check, not a data-completeness requirement, and
    missing data isn't grounds to withhold credit duration alone would
    already justify."""
    if workout.distance_meters is None:
        return True
    if workout.duration_seconds <= 0:
        return False
    pace = workout.distance_meters / workout.duration_seconds
    return pace >= MIN_ACTIVE_PACE_METERS_PER_SECOND
