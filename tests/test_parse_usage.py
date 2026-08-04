import copy
import json
from pathlib import Path

import pytest

from codex_reset_collector import SchemaDrift, iso, parse_usage

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "usage_ok.json").read_text()
)
NOW = 1754368000


def body():
    return copy.deepcopy(FIXTURE)


def test_parses_weekly_window_from_primary():
    snap = parse_usage(body(), NOW)
    assert snap == {
        "observed_at": NOW,
        "used_percent": 37,
        "reset_at": 1754800000,
        "window_seconds": 604800,
        "window_source": "primary_window",
        "reset_credits": 0,
    }


def test_selects_secondary_when_it_is_the_weekly_one():
    b = body()
    # a 5-hour window in primary, the weekly one in secondary
    b["rate_limit"]["secondary_window"] = b["rate_limit"]["primary_window"]
    b["rate_limit"]["primary_window"] = {
        "used_percent": 12,
        "limit_window_seconds": 18000,
        "reset_after_seconds": 9000,
        "reset_at": 1754380000,
    }
    snap = parse_usage(b, NOW)
    assert snap["window_source"] == "secondary_window"
    assert snap["used_percent"] == 37


def test_missing_rate_limit_is_drift():
    b = body()
    del b["rate_limit"]
    with pytest.raises(SchemaDrift):
        parse_usage(b, NOW)


def test_no_window_at_all_is_drift():
    b = body()
    b["rate_limit"]["primary_window"] = None
    b["rate_limit"]["secondary_window"] = None
    with pytest.raises(SchemaDrift):
        parse_usage(b, NOW)


def test_no_week_like_window_is_drift():
    b = body()
    b["rate_limit"]["primary_window"]["limit_window_seconds"] = 18000
    with pytest.raises(SchemaDrift):
        parse_usage(b, NOW)


def test_used_percent_out_of_range_is_drift():
    b = body()
    b["rate_limit"]["primary_window"]["used_percent"] = 140
    with pytest.raises(SchemaDrift):
        parse_usage(b, NOW)


def test_used_percent_wrong_type_is_drift():
    b = body()
    b["rate_limit"]["primary_window"]["used_percent"] = "37%"
    with pytest.raises(SchemaDrift):
        parse_usage(b, NOW)


def test_non_dict_body_is_drift():
    with pytest.raises(SchemaDrift):
        parse_usage(["not", "an", "object"], NOW)


def test_absent_reset_credits_is_none_not_drift():
    b = body()
    del b["rate_limit_reset_credits"]
    assert parse_usage(b, NOW)["reset_credits"] is None


def test_malformed_reset_credits_is_drift():
    b = body()
    b["rate_limit_reset_credits"] = {"available_count": "three"}
    with pytest.raises(SchemaDrift):
        parse_usage(b, NOW)


def test_iso_is_utc_zulu():
    assert iso(0) == "1970-01-01T00:00:00Z"
    assert iso(1785904000) == "2026-08-05T04:26:40Z"
