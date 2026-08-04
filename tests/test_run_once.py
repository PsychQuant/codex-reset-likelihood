import copy
import json
from pathlib import Path

from codex_reset_collector import load_state, run_once

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "usage_ok.json").read_text()
)


def usage(used_percent, reset_at=1754800000):
    b = copy.deepcopy(FIXTURE)
    b["rate_limit"]["primary_window"]["used_percent"] = used_percent
    b["rate_limit"]["primary_window"]["reset_at"] = reset_at
    return b


def paths(tmp_path):
    return tmp_path / "state.json", tmp_path / "observations.jsonl"


def read_log(log):
    if not Path(log).exists():
        return []
    return [json.loads(l) for l in Path(log).read_text().splitlines()]


def test_first_run_records_baseline_and_no_event(tmp_path):
    state, log = paths(tmp_path)
    code = run_once(lambda: usage(37), 1754368000, state, log)
    assert code == 0
    assert load_state(state)["used_percent"] == 37
    assert read_log(log) == []


def test_quota_rise_before_reset_at_appends_bonus_event(tmp_path):
    state, log = paths(tmp_path)
    run_once(lambda: usage(62), 1754368000, state, log)
    code = run_once(lambda: usage(1), 1754371600, state, log)
    assert code == 0
    events = read_log(log)
    assert len(events) == 1
    assert events[0]["evidence_kind"] == "quota_jump"
    assert events[0]["payload"]["classified_as"] == "bonus_reset"
    # state advanced to the new snapshot
    assert load_state(state)["used_percent"] == 1


def test_rollover_is_recorded_and_classified_rollover(tmp_path):
    state, log = paths(tmp_path)
    run_once(lambda: usage(62), 1754368000, state, log)
    code = run_once(
        lambda: usage(1, reset_at=1755404800), 1754803600, state, log
    )
    assert code == 0
    events = read_log(log)
    assert len(events) == 1
    assert events[0]["payload"]["classified_as"] == "rollover"


def test_no_change_appends_nothing(tmp_path):
    state, log = paths(tmp_path)
    run_once(lambda: usage(37), 1754368000, state, log)
    run_once(lambda: usage(41), 1754371600, state, log)
    assert read_log(log) == []


def test_schema_drift_recorded_state_preserved_exit_2(tmp_path):
    state, log = paths(tmp_path)
    run_once(lambda: usage(37), 1754368000, state, log)
    baseline = load_state(state)
    code = run_once(lambda: {"totally": "different"}, 1754371600, state, log)
    assert code == 2
    events = read_log(log)
    assert len(events) == 1
    assert events[0]["evidence_kind"] == "schema_drift"
    assert events[0]["payload"]["top_level_keys"] == ["totally"]
    # the last good baseline survives so recovery can resume comparing
    assert load_state(state) == baseline


def test_drift_on_non_dict_body_records_empty_keys(tmp_path):
    state, log = paths(tmp_path)
    code = run_once(lambda: "gateway error page", 1754368000, state, log)
    assert code == 2
    assert read_log(log)[0]["payload"]["top_level_keys"] == []
