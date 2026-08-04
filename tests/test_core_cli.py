import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "core.decision_core", *args],
        capture_output=True, text=True, cwd=ROOT,
    )


def test_empty_log_is_insufficient_data(tmp_path):
    log = tmp_path / "observations.jsonl"
    log.write_text("")
    result = run_cli(str(log), "--now", "2026-08-04T00:00:00Z")
    assert result.returncode == 0
    verdict = json.loads(result.stdout)
    assert verdict["status"] == "INSUFFICIENT_DATA"
    assert verdict["hazard"] is None


def test_committed_log_exists_and_is_empty():
    log = ROOT / "data" / "observations.jsonl"
    assert log.exists()
    assert log.read_text() == ""


def test_malformed_log_line_fails_loud(tmp_path):
    log = tmp_path / "observations.jsonl"
    log.write_text('{"v": 1, "evidence_kind": "quota_jump"}\nnot json\n')
    result = run_cli(str(log), "--now", "2026-08-04T00:00:00Z")
    assert result.returncode != 0
    assert "line 2" in result.stderr
