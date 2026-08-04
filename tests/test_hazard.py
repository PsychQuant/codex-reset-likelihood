import math

from core.decision_core import (
    MIN_EVENTS,
    decide,
    p24,
    parse_ts,
    weibull_mom,
)

# The 12 synthetic event days from the deployed index.html. The page
# computes k=3.16, lam=19.4d, mean=17.4d, and p24=1.7% at 6d10h elapsed
# IN THE BROWSER from these same gaps — this test pins the Python core
# to the shipped JS. If either side changes, this anchor breaks loudly.
JS_EVENT_DAYS = [17, 33, 51, 62, 86, 104, 121, 152, 161, 178, 191, 208]
DAY0 = parse_ts("2026-01-01T00:00:00Z")


def bonus_at(day):
    """A bonus-reset observation whose interval midpoint is exactly
    DAY0 + day*86400 (interval = midpoint +- 30 min)."""
    from datetime import datetime, timezone
    mid = DAY0 + day * 86400
    f = "%Y-%m-%dT%H:%M:%SZ"
    ts = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime(f)
    return {
        "v": 1,
        "source": "self-account",
        "observed_at": ts(mid + 1800),
        "occurred_at": [ts(mid - 1800), ts(mid + 1800)],
        "evidence_kind": "quota_jump",
        "payload": {
            "prev_observed_at": ts(mid - 1800),
            "prev_reset_at": ts(mid + 500000),  # well in the future: bonus
            "prev_remaining": 10,
            "curr_remaining": 99,
            "curr_reset_at": ts(mid + 604800),
            "window_source": "primary_window",
            "classified_as": "bonus_reset",
        },
        "signature": None,
    }


DRIFT = {
    "v": 1,
    "source": "self-account",
    "observed_at": "2026-08-01T00:00:00Z",
    "occurred_at": ["2026-08-01T00:00:00Z", "2026-08-01T00:00:00Z"],
    "evidence_kind": "schema_drift",
    "payload": {"reason": "rate_limit missing", "top_level_keys": []},
    "signature": None,
}

EVENTS = [bonus_at(d) for d in JS_EVENT_DAYS]
# now = day 208 + 6d10h, matching the deployed page's "SINCE 6 d 10 h"
NOW = DAY0 + int((208 + 6 + 10 / 24) * 86400)


def test_matches_the_deployed_js_parameters():
    k, lam, mean = weibull_mom([16, 18, 11, 24, 18, 17, 31, 9, 17, 13, 17])
    assert abs(k - 3.16) < 0.05
    assert abs(lam - 19.4) < 0.1
    assert abs(mean - 17.36) < 0.01


def test_p24_matches_the_deployed_js_readout():
    k, lam, _ = weibull_mom([16, 18, 11, 24, 18, 17, 31, 9, 17, 13, 17])
    assert abs(p24(k, lam, 6 + 10 / 24) - 0.017) < 0.002


def test_full_pipeline_reproduces_the_page():
    verdict = decide(EVENTS, NOW)
    assert verdict["status"] == "OK"
    hazard = verdict["hazard"]
    assert hazard["model"] == "weibull"
    assert abs(hazard["k"] - 3.16) < 0.05
    assert abs(hazard["lam_days"] - 19.4) < 0.1
    assert abs(hazard["elapsed_days"] - (6 + 10 / 24)) < 0.001
    assert abs(hazard["p24"] - 0.017) < 0.002


def test_insufficient_data_below_three_events():
    for n in (0, 1, 2):
        verdict = decide(EVENTS[:n], NOW)
        assert verdict["status"] == "INSUFFICIENT_DATA"
        assert verdict["hazard"] is None
    assert MIN_EVENTS == 3
    assert decide(EVENTS[:3], NOW)["status"] == "OK"


def test_schema_drift_halts_even_with_plenty_of_events():
    verdict = decide(EVENTS + [DRIFT], NOW)
    assert verdict["status"] == "HALT_SCHEMA_DRIFT"
    assert verdict["hazard"] is None
    # the measured facts are still listed; only inference stops
    assert len(verdict["events"]) == len(JS_EVENT_DAYS)


def test_equal_gaps_do_not_blow_up():
    # zero variance -> cv=0 -> k would be infinite; MIN_CV clamps it
    k, lam, mean = weibull_mom([14.0, 14.0, 14.0, 14.0])
    assert math.isfinite(k) and math.isfinite(lam)
    assert mean == 14.0


def test_p24_is_a_probability_even_for_negative_elapsed():
    k, lam, _ = weibull_mom([16, 18, 11, 24, 18, 17, 31, 9, 17, 13, 17])
    for t in (-1.0, 0.0, 0.5, 5.0, 50.0, 500.0):
        assert 0.0 <= p24(k, lam, t) <= 1.0
