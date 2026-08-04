import json

import pytest

from codex_reset_collector import (
    StateCorrupt,
    append_observation,
    load_state,
    save_state,
)

SNAP = {
    "observed_at": 1754368000,
    "used_percent": 37,
    "reset_at": 1754800000,
    "window_seconds": 604800,
    "window_source": "primary_window",
    "reset_credits": 0,
}


def test_load_missing_state_is_none(tmp_path):
    assert load_state(tmp_path / "nope" / "state.json") is None


def test_save_then_load_roundtrip(tmp_path):
    path = tmp_path / ".collector-state" / "last_observation.json"
    save_state(path, SNAP)
    assert load_state(path) == SNAP


def test_corrupt_state_fails_loud(tmp_path):
    # Silently treating a corrupt baseline as first-run could swallow a
    # real event. Crash with a clear message instead.
    path = tmp_path / "state.json"
    path.write_text("{not json")
    with pytest.raises(StateCorrupt):
        load_state(path)


def test_append_is_one_line_per_observation(tmp_path):
    log = tmp_path / "data" / "observations.jsonl"
    append_observation(log, {"a": 1})
    append_observation(log, {"b": [2, 3]})
    lines = log.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == {"a": 1}
    assert json.loads(lines[1]) == {"b": [2, 3]}


def test_append_preserves_existing_lines(tmp_path):
    log = tmp_path / "observations.jsonl"
    log.write_text('{"old": true}\n')
    append_observation(log, {"new": True})
    lines = log.read_text().splitlines()
    assert json.loads(lines[0]) == {"old": True}
    assert json.loads(lines[1]) == {"new": True}
