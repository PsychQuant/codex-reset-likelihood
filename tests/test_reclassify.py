import copy

from core.decision_core import decide, midpoint, parse_ts, reclassify


def quota_jump(observed_at, prev_observed_at, prev_reset_at,
               prev_remaining, curr_remaining, classified_as):
    return {
        "v": 1,
        "source": "self-account",
        "observed_at": observed_at,
        "occurred_at": [prev_observed_at, observed_at],
        "evidence_kind": "quota_jump",
        "payload": {
            "prev_observed_at": prev_observed_at,
            "prev_reset_at": prev_reset_at,
            "prev_remaining": prev_remaining,
            "curr_remaining": curr_remaining,
            "curr_reset_at": "2026-08-12T00:00:00Z",
            "window_source": "primary_window",
            "classified_as": classified_as,
        },
        "signature": None,
    }


BONUS = quota_jump(
    "2026-08-05T05:26:40Z", "2026-08-05T04:26:40Z",
    "2026-08-10T04:26:40Z", 38, 99, "bonus_reset",
)
ROLLOVER = quota_jump(
    "2026-08-11T05:00:00Z", "2026-08-10T02:00:00Z",
    "2026-08-10T04:26:40Z", 9, 100, "rollover",
)


def test_parse_ts_roundtrip():
    assert parse_ts("1970-01-01T00:00:00Z") == 0
    assert parse_ts("2026-08-05T04:26:40Z") == 1785904000


def test_midpoint_of_interval():
    assert midpoint(["2026-08-05T04:26:40Z", "2026-08-05T05:26:40Z"]) == (
        1785904000 + 1785907600
    ) / 2


def test_reclassify_agrees_on_bonus_and_rollover():
    assert reclassify(BONUS) == "bonus_reset"
    assert reclassify(ROLLOVER) == "rollover"


def test_reclassify_no_rise_is_none():
    obs = quota_jump(
        "2026-08-05T05:26:40Z", "2026-08-05T04:26:40Z",
        "2026-08-10T04:26:40Z", 38, 38, "bonus_reset",
    )
    assert reclassify(obs) is None


def test_decide_flags_mismatch_and_trusts_recomputation():
    # collector (wrongly) filed a rollover as a bonus: observed AFTER
    # prev_reset_at. The core's own answer wins; the row is reported.
    lying = quota_jump(
        "2026-08-11T05:00:00Z", "2026-08-10T02:00:00Z",
        "2026-08-10T04:26:40Z", 9, 100, "bonus_reset",
    )
    verdict = decide([lying], parse_ts("2026-08-12T00:00:00Z"))
    assert len(verdict["mismatches"]) == 1
    assert verdict["mismatches"][0]["recorded_kind"] == "bonus_reset"
    assert verdict["mismatches"][0]["recomputed_kind"] == "rollover"
    assert verdict["events"] == []  # not counted as a Track A event


def test_decide_counts_only_recomputed_bonus_events():
    verdict = decide([BONUS, ROLLOVER], parse_ts("2026-08-12T00:00:00Z"))
    assert len(verdict["events"]) == 1
    assert verdict["events"][0]["recomputed_kind"] == "bonus_reset"
    assert verdict["mismatches"] == []


def test_event_row_lag_is_observed_minus_interval_midpoint():
    verdict = decide([BONUS], parse_ts("2026-08-12T00:00:00Z"))
    row = verdict["events"][0]
    assert row["lag_seconds"] == 1785907600 - (1785904000 + 1785907600) / 2


def test_decide_does_not_mutate_input():
    events = [copy.deepcopy(BONUS)]
    snapshot = copy.deepcopy(events)
    decide(events, parse_ts("2026-08-12T00:00:00Z"))
    assert events == snapshot


def test_decision_core_never_imports_the_collector():
    import core.decision_core as dc
    source = open(dc.__file__, encoding="utf-8").read()
    assert "codex_reset_collector" not in source
