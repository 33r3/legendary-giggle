from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IngestEvent, StepSample, Workout, WorkoutRoutePoint
from app.schemas import IngestPayload

STEP_METRIC_NAME = "step_count"


def store_raw_event(db: Session, raw_body: str) -> IngestEvent:
    """Persists a webhook delivery byte-for-byte. Always succeeds — this
    must never depend on whether the schema currently understands the
    payload, per the raw-data-is-append-only invariant.
    """
    event = IngestEvent(raw_payload=raw_body)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def apply_parsed_payload(db: Session, event: IngestEvent, payload: IngestPayload) -> None:
    """Extracts typed rows from an already-parsed payload for an
    already-stored event.

    Step samples are never deduplicated — append-only. Any reward-relevant
    aggregation (e.g. cross-source step dedup) happens later, in the
    derived layer, computed from this raw data.

    Workouts are the one exception: export automations typically resend a
    rolling window on every run, and unlike passive Fragments, session
    rolls involve genuine randomness that's never recomputed once
    persisted — so a duplicate workout row would mean a real duplicate
    payout, not just a duplicate raw record. Dedup happens here, before
    that row can ever reach roll processing.
    """
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
        already_ingested = db.execute(
            select(Workout).where(
                Workout.start_time == workout_payload.start,
                Workout.end_time == workout_payload.end,
            )
        ).scalar_one_or_none()
        if already_ingested is not None:
            continue

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
                    latitude=point.latitude,
                    longitude=point.longitude,
                    altitude=point.altitude,
                    recorded_at=point.timestamp,
                )
            )

    event.parse_error = None
    db.commit()


def persist_ingest_payload(db: Session, raw_body: str) -> IngestEvent:
    """Stores the raw delivery, then attempts to parse and extract it. A
    payload the current schema can't handle is still fully captured —
    parse_error records why, and scripts/reparse_ingest_events.py can
    retry it later once the schema is fixed, with nothing lost.
    """
    event = store_raw_event(db, raw_body)

    try:
        payload = IngestPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        event.parse_error = str(exc)
        db.commit()
        db.refresh(event)
        return event

    apply_parsed_payload(db, event, payload)
    db.refresh(event)
    return event
