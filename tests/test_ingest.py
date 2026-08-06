import json

from app.models import IngestEvent, StepSample, Workout, WorkoutRoutePoint
from tests.conftest import WEBHOOK_TOKEN

SAMPLE_PAYLOAD = {
    "data": {
        "metrics": [
            {
                "name": "step_count",
                "units": "count",
                "data": [
                    {"date": "2026-08-06 08:00:00 -0500", "qty": 1200, "source": "Test iPhone"},
                    {"date": "2026-08-06 08:00:00 -0500", "qty": 1180, "source": "Test Watch"},
                ],
            }
        ],
        "workouts": [
            {
                "id": "test-workout-1",
                "name": "Outdoor Walk",
                "source": "Test Watch",
                "start": "2026-08-06 09:00:00 -0500",
                "end": "2026-08-06 09:20:00 -0500",
                "route": [
                    {"lat": 1.111, "lon": 2.222, "altitude": 300.0, "timestamp": "2026-08-06 09:00:05 -0500"},
                    {"lat": 1.112, "lon": 2.223, "altitude": 301.0, "timestamp": "2026-08-06 09:00:20 -0500"},
                ],
            }
        ],
    }
}


def auth_headers():
    return {"Authorization": f"Bearer {WEBHOOK_TOKEN}"}


def test_rejects_missing_auth(client):
    response = client.post("/ingest/healthkit", content=json.dumps(SAMPLE_PAYLOAD))
    assert response.status_code in (401, 422)


def test_rejects_wrong_token(client):
    response = client.post(
        "/ingest/healthkit",
        content=json.dumps(SAMPLE_PAYLOAD),
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


def test_persists_raw_payload_and_parsed_rows(client, db_session):
    response = client.post(
        "/ingest/healthkit",
        content=json.dumps(SAMPLE_PAYLOAD),
        headers=auth_headers(),
    )
    assert response.status_code == 200
    event_id = response.json()["ingest_event_id"]

    event = db_session.get(IngestEvent, event_id)
    assert event is not None
    assert json.loads(event.raw_payload) == SAMPLE_PAYLOAD

    step_samples = db_session.query(StepSample).filter_by(ingest_event_id=event_id).all()
    assert len(step_samples) == 2
    assert {s.source for s in step_samples} == {"Test iPhone", "Test Watch"}

    workouts = db_session.query(Workout).filter_by(ingest_event_id=event_id).all()
    assert len(workouts) == 1
    assert workouts[0].external_id == "test-workout-1"
    assert workouts[0].duration_seconds == 1200

    route_points = (
        db_session.query(WorkoutRoutePoint).filter_by(workout_id=workouts[0].id).order_by(WorkoutRoutePoint.sequence_index).all()
    )
    assert [p.sequence_index for p in route_points] == [0, 1]


def test_raw_events_and_step_samples_are_append_only_across_repeated_deliveries(client, db_session):
    for _ in range(2):
        response = client.post(
            "/ingest/healthkit",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers=auth_headers(),
        )
        assert response.status_code == 200

    assert db_session.query(IngestEvent).count() == 2
    assert db_session.query(StepSample).count() == 4


def test_workouts_are_deduped_across_repeated_deliveries(client, db_session):
    """Export automations resend a rolling window on every run — a
    workout with the same start/end arriving twice must not create a
    second row, since a duplicate row would trigger a duplicate,
    irreversible session roll downstream."""
    for _ in range(2):
        response = client.post(
            "/ingest/healthkit",
            content=json.dumps(SAMPLE_PAYLOAD),
            headers=auth_headers(),
        )
        assert response.status_code == 200

    assert db_session.query(Workout).count() == 1
    assert db_session.query(WorkoutRoutePoint).count() == 2


def test_workout_without_id_is_accepted(client, db_session):
    payload = json.loads(json.dumps(SAMPLE_PAYLOAD))
    del payload["data"]["workouts"][0]["id"]

    response = client.post(
        "/ingest/healthkit",
        content=json.dumps(payload),
        headers=auth_headers(),
    )
    assert response.status_code == 200

    workout = db_session.query(Workout).one()
    assert workout.external_id is None
