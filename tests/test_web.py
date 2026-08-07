import json
from datetime import date, datetime, timezone

from app.models import IngestEvent, PassiveTierConfig, Region, SessionTierConfig, WagerConfig, Workout, WorkoutRollResult
from tests.conftest import WEB_UI_PASSWORD, WEB_UI_USERNAME


def auth():
    return (WEB_UI_USERNAME, WEB_UI_PASSWORD)


def make_region(db_session, slug="home", always_unlocked=True, cost=None) -> Region:
    region = Region(
        slug=slug, name="Test Region", polygon_geojson="{}", always_unlocked=always_unlocked, unlock_cost_fragments=cost
    )
    db_session.add(region)
    db_session.commit()
    db_session.refresh(region)
    return region


def make_session_config(db_session) -> None:
    db_session.add(
        SessionTierConfig(
            roll_interval_minutes=15, max_rolls_per_session=5, effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc)
        )
    )
    db_session.commit()


def make_wager_config(db_session) -> None:
    db_session.add(
        WagerConfig(
            modest_session_threshold=1,
            standard_session_threshold=2,
            standard_bonus=5,
            ambitious_session_threshold=3,
            ambitious_bonus=20,
            effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )
    )
    db_session.commit()


def test_dashboard_requires_auth(client):
    assert client.get("/").status_code == 401


def test_dashboard_rejects_wrong_credentials(client):
    response = client.get("/", auth=(WEB_UI_USERNAME, "wrong"))
    assert response.status_code == 401


def test_dashboard_renders_with_correct_credentials(client, db_session):
    make_region(db_session)
    response = client.get("/", auth=auth())
    assert response.status_code == 200
    assert "Fragments" in response.text
    assert "Regions" in response.text
    assert "Test Region" in response.text


def test_declare_wager_action_redirects_with_message(client, db_session):
    make_wager_config(db_session)
    response = client.post("/wager/declare", data={"tier": "standard"}, auth=auth(), follow_redirects=False)
    assert response.status_code == 303
    assert "message=" in response.headers["location"]


def test_declare_wager_action_rejects_bad_tier(client, db_session):
    make_wager_config(db_session)
    response = client.post("/wager/declare", data={"tier": "extreme"}, auth=auth(), follow_redirects=False)
    assert response.status_code == 303
    assert "error=" in response.headers["location"]


def test_unlock_action_fails_cleanly_without_enough_fragments(client, db_session):
    make_region(db_session, always_unlocked=False, cost=50)
    response = client.post("/regions/home/unlock", auth=auth(), follow_redirects=False)
    assert response.status_code == 303
    assert "error=" in response.headers["location"]


def test_unlock_action_unknown_region(client, db_session):
    response = client.post("/regions/does-not-exist/unlock", auth=auth(), follow_redirects=False)
    assert response.status_code == 303
    assert "error=" in response.headers["location"]


def test_refresh_action_requires_auth(client):
    assert client.post("/refresh").status_code == 401


def test_refresh_action_runs_and_redirects(client, db_session):
    make_session_config(db_session)
    response = client.post("/refresh", auth=auth(), follow_redirects=False)
    assert response.status_code == 303
    assert "message=" in response.headers["location"]


def test_flash_message_renders_on_dashboard(client, db_session):
    make_session_config(db_session)
    response = client.post("/refresh", auth=auth())
    assert response.status_code == 200
    assert "Processed" in response.text


def test_collection_requires_auth(client):
    assert client.get("/collection").status_code == 401


def test_collection_renders_grouped_by_tier(client, db_session):
    region = make_region(db_session)
    event = IngestEvent(raw_payload="{}")
    db_session.add(event)
    db_session.flush()
    workout = Workout(
        ingest_event_id=event.id,
        workout_type="Walk",
        source="Test",
        start_time=datetime(2026, 8, 1, 9, tzinfo=timezone.utc),
        end_time=datetime(2026, 8, 1, 9, 20, tzinfo=timezone.utc),
        duration_seconds=1200,
    )
    db_session.add(workout)
    db_session.commit()
    db_session.add(
        WorkoutRollResult(
            workout_id=workout.id,
            region_id=region.id,
            tier="rare",
            item_name="Test Rare Item",
            rolled_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    )
    db_session.add(
        WorkoutRollResult(
            workout_id=workout.id,
            region_id=region.id,
            tier="common",
            item_name="Test Common Item",
            rolled_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    response = client.get("/collection", auth=auth())
    assert response.status_code == 200
    assert "Test Rare Item" in response.text
    assert "Test Common Item" not in response.text


def test_collection_shows_empty_state(client, db_session):
    response = client.get("/collection", auth=auth())
    assert response.status_code == 200
    assert "keep walking" in response.text.lower()
