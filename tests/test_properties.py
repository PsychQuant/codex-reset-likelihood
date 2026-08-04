"""Seeded-random property tests (spec section 10).

No hypothesis dependency: 200 fixed seeds x random logs. Failures
print the seed so any case is exactly reproducible.
"""

import copy
import random

from codex_reset_collector import build_drift_observation, build_observation, classify
from core.decision_core import decide

SEEDS = range(200)
BASE = 1754368000


def random_log(rng):
    """A random but structurally valid observation log."""
    events = []
    t = BASE
    prev = {
        "observed_at": t,
        "used_percent": rng.randint(0, 100),
        "reset_at": t + rng.randint(3600, 604800),
        "window_seconds": 604800,
        "window_source": "primary_window",
        "reset_credits": 0,
    }
    for _ in range(rng.randint(0, 25)):
        t += rng.randint(600, 172800)
        roll = rng.random()
        if roll < 0.1:
            events.append(
                build_drift_observation(t, "fuzzed drift", ["a", "b"])
            )
            continue
        curr = {
            "observed_at": t,
            "used_percent": rng.randint(0, 100),
            "reset_at": t + rng.randint(3600, 604800),
            "window_seconds": 604800,
            "window_source": "primary_window",
            "reset_credits": 0,
        }
        kind = classify(prev, curr)
        if kind is not None:
            events.append(build_observation(prev, curr, kind))
        prev = curr
    return events, t


def test_invariants_over_200_seeds():
    for seed in SEEDS:
        rng = random.Random(seed)
        events, t_end = random_log(rng)
        frozen = copy.deepcopy(events)
        verdict = decide(events, t_end + 3600)

        context = "seed=%d" % seed
        quota_jumps = [
            e for e in events if e["evidence_kind"] == "quota_jump"
        ]
        drifts = [e for e in events if e["evidence_kind"] == "schema_drift"]

        # 1. Track A events never exceed the quota_jump observations
        assert len(verdict["events"]) <= len(quota_jumps), context
        # 2. collector and auditor agree on collector-built observations
        assert verdict["mismatches"] == [], context
        # 3. drift halts; no drift never yields the drift status
        if drifts:
            assert verdict["status"] == "HALT_SCHEMA_DRIFT", context
            assert verdict["hazard"] is None, context
        else:
            assert verdict["status"] in ("OK", "INSUFFICIENT_DATA"), context
        # 4. below three events, never a number
        if len(verdict["events"]) < 3 and not drifts:
            assert verdict["status"] == "INSUFFICIENT_DATA", context
            assert verdict["hazard"] is None, context
        # 5. any published hazard is a probability
        if verdict["hazard"] is not None:
            assert 0.0 <= verdict["hazard"]["p24"] <= 1.0, context
        # 6. decide is pure: input unmutated, output deterministic
        assert events == frozen, context
        assert decide(events, t_end + 3600) == verdict, context
