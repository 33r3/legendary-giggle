from sqlalchemy.orm import Session

from app.models import IngestEvent, StepSample, Workout, WorkoutRoutePoint
from app.schemas import IngestPayload

STEP_METRIC_NAME = "step_count"


def persist_ingest_payload(db: Session, raw_body: str, payload: IngestPayload) -> IngestEvent:
    """Write one webhook delivery to raw storage, unmodified and in full.

    Never updates or deduplicates existing rows — append-only. Any
    reward-relevant aggregation (e.g. cross-source step dedup) happens
    later, in the derived layer, computed from this raw data.
    """
    event = IngestEvent(raw_payload=raw_body)
    db.add(event)
    db.flush()

    for metric in payload.data.metrics:
        if metric.name != STEP_METRIC_NAME:
            continue
        for entry in metric.data:
            db.add(
                StepSample(
                    ingest_event_id=event.id,
                    source=entry.source,
                    period_start=entry.date,
                    period_end=entry.date,
                    quantity=entry.qty,
                    units=metric.units,
                )
            )

    for workout_payload in payload.data.workouts:
        duration_seconds = (workout_payload.end - workout_payload.start).total_seconds()
        workout = Workout(
            ingest_event_id=event.id,
            external_id=workout_payload.id,
            workout_type=workout_payload.name,
            source=workout_payload.source,
            start_time=workout_payload.start,
            end_time=workout_payload.end,
            duration_seconds=duration_seconds,
        )
        db.add(workout)
        db.flush()

        for index, point in enumerate(workout_payload.route):
            db.add(
                WorkoutRoutePoint(
                    workout_id=workout.id,
                    sequence_index=index,
                    latitude=point.lat,
                    longitude=point.lon,
                    altitude=point.altitude,
                    recorded_at=point.timestamp,
                )
            )

    db.commit()
    db.refresh(event)
    return event
