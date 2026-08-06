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
