"""Materializes the current passive-tier reward curve into the database.

Run at deploy time (and again whenever a retune is decided). Never
overwrites a prior config row — retuning inserts a new version so
historical days keep recomputing against the curve that was live then.
"""

from datetime import datetime, timezone

from app.config import get_settings
from app.db import SessionLocal
from app.generation.economy import generate_passive_tier_params, generate_session_tier_params
from app.models import PassiveTierConfig, SessionTierConfig


def materialize_passive_tier_config() -> PassiveTierConfig:
    settings = get_settings()
    params = generate_passive_tier_params(settings.game_seed)

    db = SessionLocal()
    try:
        config = PassiveTierConfig(
            floor_steps=params["floor_steps"],
            steps_per_fragment=params["steps_per_fragment"],
            daily_cap_fragments=params["daily_cap_fragments"],
            effective_from=datetime.now(timezone.utc),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config
    finally:
        db.close()


def materialize_session_tier_config() -> SessionTierConfig:
    settings = get_settings()
    params = generate_session_tier_params(settings.game_seed)

    db = SessionLocal()
    try:
        config = SessionTierConfig(
            roll_interval_minutes=params["roll_interval_minutes"],
            max_rolls_per_session=params["max_rolls_per_session"],
            effective_from=datetime.now(timezone.utc),
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return config
    finally:
        db.close()


if __name__ == "__main__":
    materialize_passive_tier_config()
    materialize_session_tier_config()
