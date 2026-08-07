"""Derives passive-tier reward-curve parameters from a seed.

Chosen values are never committed as literals — they're generated here
from whatever seed the deploy environment provides, then materialized
into the database (see scripts/materialize_economy.py). A different seed
(e.g. for local dev) produces different, non-production values from the
same mechanism.
"""

import hashlib

_FLOOR_STEPS_CANDIDATES = [2000, 2500, 3000, 3500, 4000, 4500, 5000, 6000]
_STEPS_PER_FRAGMENT_CANDIDATES = [300, 400, 500, 600, 750, 1000]
_DAILY_CAP_FRAGMENTS_CANDIDATES = [6, 8, 10, 12, 15, 20]


def _pick(seed: str, salt: str, candidates: list[int]) -> int:
    digest = hashlib.sha256(f"{seed}:{salt}".encode("utf-8")).hexdigest()
    return candidates[int(digest, 16) % len(candidates)]


def generate_passive_tier_params(seed: str) -> dict[str, int]:
    return {
        "floor_steps": _pick(seed, "floor_steps", _FLOOR_STEPS_CANDIDATES),
        "steps_per_fragment": _pick(seed, "steps_per_fragment", _STEPS_PER_FRAGMENT_CANDIDATES),
        "daily_cap_fragments": _pick(seed, "daily_cap_fragments", _DAILY_CAP_FRAGMENTS_CANDIDATES),
    }


# The 15-minute roll interval is fixed by the design doc (already public);
# only the per-session cap is a tunable balance number, so only it is
# seed-generated.
_ROLL_INTERVAL_MINUTES = 15
_MAX_ROLLS_PER_SESSION_CANDIDATES = [2, 3, 4, 5, 6]


def generate_session_tier_params(seed: str) -> dict[str, int]:
    return {
        "roll_interval_minutes": _ROLL_INTERVAL_MINUTES,
        "max_rolls_per_session": _pick(seed, "max_rolls_per_session", _MAX_ROLLS_PER_SESSION_CANDIDATES),
    }


_REGION_UNLOCK_COST_CANDIDATES = [15, 20, 25, 30, 35, 40, 50, 60, 80, 100]


def generate_region_unlock_cost(seed: str, region_slug: str) -> int:
    """Per-region, not just per-seed, so each region gets its own cost
    rather than all non-free regions sharing one price."""
    return _pick(seed, f"region_unlock_cost:{region_slug}", _REGION_UNLOCK_COST_CANDIDATES)


# Non-overlapping candidate ranges guarantee modest < standard < ambitious
# thresholds and standard < ambitious bonuses by construction, without
# needing to generate-then-validate an ordering.
_MODEST_SESSION_THRESHOLD_CANDIDATES = [1, 2]
_STANDARD_SESSION_THRESHOLD_CANDIDATES = [3, 4]
_STANDARD_BONUS_CANDIDATES = [3, 5, 8]
_AMBITIOUS_SESSION_THRESHOLD_CANDIDATES = [5, 6, 7]
_AMBITIOUS_BONUS_CANDIDATES = [12, 15, 20, 25]


def generate_wager_config_params(seed: str) -> dict[str, int]:
    return {
        "modest_session_threshold": _pick(seed, "modest_session_threshold", _MODEST_SESSION_THRESHOLD_CANDIDATES),
        "standard_session_threshold": _pick(
            seed, "standard_session_threshold", _STANDARD_SESSION_THRESHOLD_CANDIDATES
        ),
        "standard_bonus": _pick(seed, "standard_bonus", _STANDARD_BONUS_CANDIDATES),
        "ambitious_session_threshold": _pick(
            seed, "ambitious_session_threshold", _AMBITIOUS_SESSION_THRESHOLD_CANDIDATES
        ),
        "ambitious_bonus": _pick(seed, "ambitious_bonus", _AMBITIOUS_BONUS_CANDIDATES),
    }
