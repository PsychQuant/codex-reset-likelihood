"""codex-reset-likelihood — pure decision core.

Input: the observation log (a list of dicts). Output: a verdict dict.
No I/O in decide() — a backtest is literally re-running this function
over the historical log (spec section 4). I/O lives only in main().

reclassify() re-implements the collector's discriminant on purpose,
reading only the published payload: it is the auditor's side of the
cross-check. Do NOT merge it with the collector's classify() — a
shared implementation could hide a shared bug. Track A counts events
by the recomputed kind; a disagreement with the collector's recorded
verdict is reported, never silently resolved.
"""

from datetime import datetime, timezone

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_ts(s):
    """ISO-8601 UTC 'Z' string -> epoch seconds (int)."""
    return int(
        datetime.strptime(s, TS_FORMAT)
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )


def midpoint(interval):
    """Midpoint of an occurred_at interval, epoch seconds (float)."""
    return (parse_ts(interval[0]) + parse_ts(interval[1])) / 2


def reclassify(obs):
    """Recompute the discriminant from the published payload alone."""
    payload = obs["payload"]
    if not payload["curr_remaining"] > payload["prev_remaining"]:
        return None
    if parse_ts(obs["observed_at"]) < parse_ts(payload["prev_reset_at"]):
        return "bonus_reset"
    return "rollover"


def _check_quota_jumps(events):
    checked, mismatches = [], []
    for obs in events:
        if obs.get("evidence_kind") != "quota_jump":
            continue
        recorded = obs["payload"].get("classified_as")
        recomputed = reclassify(obs)
        row = {
            "occurred_at": list(obs["occurred_at"]),
            "observed_at": obs["observed_at"],
            "lag_seconds": parse_ts(obs["observed_at"])
            - midpoint(obs["occurred_at"]),
            "recorded_kind": recorded,
            "recomputed_kind": recomputed,
            "mismatch": recorded != recomputed,
        }
        checked.append(row)
        if row["mismatch"]:
            mismatches.append(row)
    return checked, mismatches


def decide(events, now_epoch):
    """events (list of observation dicts) + now -> verdict dict.

    Pure: no I/O, no mutation of the input, deterministic.
    """
    drifted = any(
        obs.get("evidence_kind") == "schema_drift" for obs in events
    )
    checked, mismatches = _check_quota_jumps(events)
    bonus = [row for row in checked if row["recomputed_kind"] == "bonus_reset"]

    verdict = {
        "events": bonus,
        "mismatches": mismatches,
        "hazard": None,
    }
    if drifted:
        verdict["status"] = "HALT_SCHEMA_DRIFT"
        return verdict
    verdict["status"] = "OK"
    return verdict
