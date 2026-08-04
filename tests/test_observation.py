from codex_reset_collector import (
    SCHEMA_VERSION,
    build_drift_observation,
    build_observation,
)

SPEC_PAYLOAD_FIELDS = {
    "prev_observed_at",
    "prev_reset_at",
    "prev_remaining",
    "curr_remaining",
    "curr_reset_at",
}


def snap(observed_at, used_percent, reset_at):
    return {
        "observed_at": observed_at,
        "used_percent": used_percent,
        "reset_at": reset_at,
        "window_seconds": 604800,
        "window_source": "primary_window",
        "reset_credits": 0,
    }


def test_observation_shape_and_spec_payload_fields():
    prev = snap(1785904000, 62, 1786336000)
    curr = snap(1785907600, 1, 1786540800)
    obs = build_observation(prev, curr, "bonus_reset")
    assert obs["v"] == SCHEMA_VERSION
    assert obs["source"] == "self-account"
    assert obs["evidence_kind"] == "quota_jump"
    assert obs["signature"] is None
    assert SPEC_PAYLOAD_FIELDS <= set(obs["payload"])
    assert obs["payload"]["classified_as"] == "bonus_reset"


def test_occurred_at_is_the_poll_interval():
    prev = snap(1785904000, 62, 1786336000)
    curr = snap(1785907600, 1, 1786540800)
    obs = build_observation(prev, curr, "bonus_reset")
    assert obs["occurred_at"] == ["2026-08-05T04:26:40Z", "2026-08-05T05:26:40Z"]
    assert obs["observed_at"] == "2026-08-05T05:26:40Z"


def test_interval_crossing_utc_midnight():
    # 23:50:00Z -> 00:10:00Z next day; plain epoch arithmetic, no date bugs
    prev = snap(1785887400, 62, 1786336000)
    curr = snap(1785888600, 1, 1786540800)
    obs = build_observation(prev, curr, "bonus_reset")
    assert obs["occurred_at"] == ["2026-08-04T23:50:00Z", "2026-08-05T00:10:00Z"]


def test_remaining_is_100_minus_used_percent():
    prev = snap(1785904000, 62, 1786336000)
    curr = snap(1785907600, 1, 1786540800)
    payload = build_observation(prev, curr, "bonus_reset")["payload"]
    assert payload["prev_remaining"] == 38
    assert payload["curr_remaining"] == 99
    assert payload["prev_reset_at"] == "2026-08-10T04:26:40Z"
    assert payload["curr_reset_at"] == "2026-08-12T13:20:00Z"


def test_no_secrets_anywhere():
    prev = snap(1785904000, 62, 1786336000)
    curr = snap(1785907600, 1, 1786540800)
    text = str(build_observation(prev, curr, "bonus_reset"))
    for word in ("token", "account_id", "Bearer", "auth"):
        assert word not in text


def test_drift_observation_records_key_names_only():
    obs = build_drift_observation(
        1754368000, "rate_limit missing", ["credits", "promo", "user_id"]
    )
    assert obs["evidence_kind"] == "schema_drift"
    assert obs["occurred_at"] == [obs["observed_at"], obs["observed_at"]]
    assert obs["payload"] == {
        "reason": "rate_limit missing",
        "top_level_keys": ["credits", "promo", "user_id"],
    }
    assert obs["signature"] is None
