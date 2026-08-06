from datetime import datetime, timezone

from app.generation.economy import generate_session_tier_params
from app.models import SessionTierConfig
from app.rewards.session import session_roll_counts

TEST_CONFIG_KWARGS = {
    "roll_interval_minutes": 15,
    "max_rolls_per_session": 3,
    "effective_from": datetime(2020, 1, 1, tzinfo=timezone.utc),
}


def test_generator_is_deterministic_per_seed():
    assert generate_session_tier_params("seed-a") == generate_session_tier_params("seed-a")


def test_rolls_under_cap_pass_through_unscaled():
    config = SessionTierConfig(**TEST_CONFIG_KWARGS)
    minutes = {1: 15.0, 2: 15.0}  # 1 roll each, cap is 3
    assert session_roll_counts(minutes, config) == {1: 1, 2: 1}


def test_rolls_over_cap_are_scaled_down_proportionally():
    config = SessionTierConfig(**TEST_CONFIG_KWARGS)
    minutes = {1: 60.0, 2: 15.0}  # raw: region 1 = 4 rolls, region 2 = 1 roll, cap 3
    result = session_roll_counts(minutes, config)
    assert sum(result.values()) == 3
    assert result[1] > result.get(2, 0)


def test_zero_minute_regions_are_dropped():
    config = SessionTierConfig(**TEST_CONFIG_KWARGS)
    minutes = {1: 5.0, 2: 30.0}  # region 1 doesn't reach a full interval
    result = session_roll_counts(minutes, config)
    assert 1 not in result
    assert result[2] == 2
