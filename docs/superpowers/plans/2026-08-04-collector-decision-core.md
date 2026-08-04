# Collector + Decision Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the local collector (single-file, stdlib-only Python state machine polling `/wham/usage`) and the pure-function decision core (event log → detector cross-check + Weibull hazard), with TDD over the spec's boundary cases.

**Architecture:** The collector is a state machine, not a stateless poller — it keeps the previous snapshot in `.collector-state/` and applies the deterministic discriminant on each poll, appending Observations to a git-tracked JSONL log. The decision core is a pure function over that log: it *independently re-runs* the discriminant from each observation's published payload (the duplication with the collector is deliberate — it is the auditor's side of the cross-check, never merge them), then estimates a Weibull hazard by method of moments, refusing to publish below 3 events and halting all inference on schema drift.

**Tech Stack:** Python ≥ 3.9 stdlib only (collector and core; `math.lgamma` replaces the JS Lanczos port). pytest (dev-only, system 9.0.2) with seeded `random.Random` property loops — no hypothesis dependency.

## Global Constraints

- Collector is **one file at repo root** (`codex_reset_collector.py`), **stdlib only** — spec §9: "Python 單檔、零依賴（一個檔 + `python3`）". Crowdsourcing = `curl -O` one file.
- Decision core is a **pure function, no I/O** — spec §4: "輸入 event log、輸出判斷、不做任何 I/O". I/O lives only in `main()`.
- Cold-start hard rule — spec §6: "事件數 < 3 時不出任何風險數字" → `INSUFFICIENT_DATA`.
- Schema drift — spec §7: fail loud, record `schema_drift`, "停止一切推論" → decision core returns `HALT_SCHEMA_DRIFT`, hazard `None`.
- Privacy — spec §8: credentials never leave the machine; never record token / account id / prompt; drift observations record key *names* only, never values. `signature` is `null` in v1 (no upload path exists at N=1; git history is the integrity anchor; field reserved for v2 crowd).
- `occurred_at` is an **interval** `[prev_observed_at, curr_observed_at]`; `observed_at` is separate — spec §5.
- `payload` of every `quota_jump` contains the spec's five fields verbatim: `prev_observed_at`, `prev_reset_at`, `prev_remaining`, `curr_remaining`, `curr_reset_at` — spec §5. Extra keys are allowed on top; those five may never be dropped or renamed.
- Event log: `data/observations.jsonl`, append-only, git-tracked — spec §9.
- Hazard is **Weibull by method of moments**, identical to the deployed page's JS (`k = cv^-1.086`, `λ = mean/Γ(1+1/k)`, `p24 = 1 − exp(−(H(t+1)−H(t)))`). Spec §6 said "Exponential 起步" but the shipped `index.html` already had to abandon exponential (memoryless ⇒ "days elapsed" cannot move the number — caught by the finish review); the Python core must agree with the deployed JS, and Task 8 pins that agreement with a cross-implementation anchor test.
- Timestamps: epoch seconds (int) internally, ISO-8601 UTC `YYYY-MM-DDTHH:MM:SSZ` strings in the log.
- All figures on the deployed site stay synthetic until ≥ 3 *real* events exist; wiring the site to real data is explicitly **out of this plan's scope**.

## Probed upstream facts (2026-08-04, live account — the parser is built on these, not on the spec's guesses)

`GET https://chatgpt.com/backend-api/wham/usage` with headers `Authorization: Bearer <tokens.access_token>` + `ChatGPT-Account-ID: <tokens.account_id>` (both nested under `tokens` in `~/.codex/auth.json` — **not** top-level as spec §8 implied) returned HTTP 200 with shape:

```
rate_limit:
  primary_window:   { used_percent: int 0..100, limit_window_seconds: ~604800, reset_after_seconds: int, reset_at: epoch-seconds int }
  secondary_window: null              ← the weekly window is PRIMARY on this account
additional_rate_limits: [...]
rate_limit_reset_credits: { available_count: int, applicable_available_count: int }
credits / spend_control / promo / ...
```

Consequences baked into the design: the parser **selects the window whose `limit_window_seconds` is closest to 604800** (checking both `primary_window` and `secondary_window`, tolerating ±25%) instead of hardcoding a name; quota is `used_percent` so "額度上升" = used_percent **drops**; `reset_credits.available_count` is captured as an auxiliary field of every snapshot.

## File Structure

```
codex_reset_collector.py        # single-file collector: parse, discriminant, state, JSONL, main
core/__init__.py                # empty package marker
core/decision_core.py           # pure: events → verdict; CLI main for backtest
data/observations.jsonl         # append-only log, committed empty in Task 10
tests/conftest.py               # sys.path bootstrap
tests/fixtures/usage_ok.json    # synthetic fixture mirroring the probed shape
tests/test_parse_usage.py       # Task 1
tests/test_discriminant.py      # Task 2
tests/test_observation.py       # Task 3
tests/test_state_io.py          # Task 4
tests/test_run_once.py          # Task 5
tests/test_auth_and_cli.py      # Task 6
tests/test_reclassify.py        # Task 7
tests/test_hazard.py            # Task 8
tests/test_properties.py        # Task 9
tests/test_core_cli.py          # Task 10
```

Run all tests from repo root: `python3 -m pytest tests/ -v`.

---

### Task 1: Fixture + `parse_usage`

**Files:**
- Create: `codex_reset_collector.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/usage_ok.json`
- Test: `tests/test_parse_usage.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `SchemaDrift(ValueError)`; `parse_usage(body: dict, observed_at: int) -> dict` returning snapshot `{"observed_at": int, "used_percent": int, "reset_at": int, "window_seconds": int, "window_source": str, "reset_credits": int|None}`; `iso(ts: int) -> str`; module constants `WEEKLY_SECONDS = 604800`, `WEEKLY_TOLERANCE = 0.25`, `SCHEMA_VERSION = 1`. Later tasks import all of these from `codex_reset_collector`.

- [ ] **Step 1: Create the bootstrap conftest and the fixture**

`tests/conftest.py`:

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
```

`tests/fixtures/usage_ok.json` — synthetic values, probed structure (weekly window in `primary_window`, `secondary_window` null, exactly as the live account returned):

```json
{
  "user_id": "user-synthetic",
  "account_id": "acct-synthetic",
  "email": "synthetic@example.invalid",
  "plan_type": "plus",
  "rate_limit": {
    "allowed": true,
    "limit_reached": false,
    "primary_window": {
      "used_percent": 37,
      "limit_window_seconds": 604800,
      "reset_after_seconds": 432000,
      "reset_at": 1754800000
    },
    "secondary_window": null
  },
  "code_review_rate_limit": null,
  "additional_rate_limits": [],
  "credits": {
    "has_credits": false,
    "unlimited": false,
    "overage_limit_reached": false,
    "balance": "0",
    "approx_local_messages": [],
    "approx_cloud_messages": []
  },
  "spend_control": { "reached": false, "individual_limit": null },
  "rate_limit_reset_credits": {
    "available_count": 0,
    "applicable_available_count": 0
  },
  "rate_limit_reached_type": null,
  "promo": null
}
```

- [ ] **Step 2: Write the failing tests**

`tests/test_parse_usage.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_parse_usage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'codex_reset_collector'`

- [ ] **Step 4: Write the implementation**

`codex_reset_collector.py`:

```python
#!/usr/bin/env python3
"""codex-reset-likelihood — local collector.

Single file, stdlib only, on purpose: crowdsourcing this instrument must
cost one `curl -O` and a python3. It is a state machine, not a stateless
poller — the discriminant needs the previous observation.

    quota rises  AND  now <  previous reset_at   ->  bonus reset
    quota rises  AND  now >= previous reset_at   ->  ordinary rollover

Credentials are read from ~/.codex/auth.json and never leave this
machine. Nothing token-shaped is ever written to the observation log.
"""

import json
from datetime import datetime, timezone

SCHEMA_VERSION = 1
WEEKLY_SECONDS = 604800
WEEKLY_TOLERANCE = 0.25  # accept a "weekly" window within +-25% of a week


class SchemaDrift(ValueError):
    """The upstream response no longer matches the shape we measured.

    Fail loud: this is recorded as a schema_drift observation and halts
    all inference downstream (spec section 7).
    """


def iso(ts):
    """Epoch seconds -> ISO-8601 UTC string, second resolution."""
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def parse_usage(body, observed_at):
    """Extract one snapshot from a /wham/usage response body.

    The weekly window is *found*, not assumed: the live API keeps it in
    primary_window (secondary_window is null there), so we pick whichever
    window's limit_window_seconds is closest to one week. Anything that
    does not match the probed shape raises SchemaDrift.
    """
    if not isinstance(body, dict):
        raise SchemaDrift("response body is not a JSON object")
    rate_limit = body.get("rate_limit")
    if not isinstance(rate_limit, dict):
        raise SchemaDrift("rate_limit missing or not an object")

    candidates = []
    for name in ("primary_window", "secondary_window"):
        window = rate_limit.get(name)
        if window is None:
            continue
        if not isinstance(window, dict):
            raise SchemaDrift("%s is not an object" % name)
        try:
            window_seconds = int(window["limit_window_seconds"])
            used_percent = int(window["used_percent"])
            reset_at = int(window["reset_at"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaDrift("%s malformed: %r" % (name, exc)) from exc
        if not 0 <= used_percent <= 100:
            raise SchemaDrift(
                "%s.used_percent out of range: %d" % (name, used_percent)
            )
        if window_seconds <= 0 or reset_at <= 0:
            raise SchemaDrift("%s has non-positive fields" % name)
        candidates.append(
            (abs(window_seconds - WEEKLY_SECONDS), name, window_seconds,
             used_percent, reset_at)
        )

    if not candidates:
        raise SchemaDrift("no rate-limit window present")
    distance, name, window_seconds, used_percent, reset_at = min(candidates)
    if distance > WEEKLY_SECONDS * WEEKLY_TOLERANCE:
        raise SchemaDrift(
            "nearest window (%ds) is not week-like" % window_seconds
        )

    reset_credits = None
    credits_obj = body.get("rate_limit_reset_credits")
    if credits_obj is not None:
        if not isinstance(credits_obj, dict):
            raise SchemaDrift("rate_limit_reset_credits is not an object")
        try:
            reset_credits = int(credits_obj["available_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaDrift(
                "rate_limit_reset_credits malformed: %r" % exc
            ) from exc

    return {
        "observed_at": int(observed_at),
        "used_percent": used_percent,
        "reset_at": reset_at,
        "window_seconds": window_seconds,
        "window_source": name,
        "reset_credits": reset_credits,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_parse_usage.py -v`
Expected: 11 PASS

- [ ] **Step 6: Commit**

```bash
git add codex_reset_collector.py tests/conftest.py tests/fixtures/usage_ok.json tests/test_parse_usage.py
git commit -m "feat: collector parse_usage 依實測 schema 選出 weekly window"
```

---

### Task 2: The discriminant — `classify`

**Files:**
- Modify: `codex_reset_collector.py` (append after `parse_usage`)
- Test: `tests/test_discriminant.py`

**Interfaces:**
- Consumes: snapshot dicts as produced by `parse_usage` (Task 1).
- Produces: `classify(prev: dict, curr: dict) -> str | None` returning `"bonus_reset"`, `"rollover"`, or `None`. Task 5 calls it; Task 3's `build_observation` receives its result as `kind`.

- [ ] **Step 1: Write the failing tests**

`tests/test_discriminant.py`:

```python
from codex_reset_collector import classify

RESET_AT = 1754800000


def snap(observed_at, used_percent, reset_at=RESET_AT):
    return {
        "observed_at": observed_at,
        "used_percent": used_percent,
        "reset_at": reset_at,
        "window_seconds": 604800,
        "window_source": "primary_window",
        "reset_credits": 0,
    }


def test_no_quota_rise_is_no_event():
    assert classify(snap(1754368000, 37), snap(1754371600, 41)) is None


def test_equal_quota_is_no_event():
    assert classify(snap(1754368000, 37), snap(1754371600, 37)) is None


def test_rise_one_second_before_reset_at_is_bonus():
    prev = snap(1754368000, 62)
    curr = snap(RESET_AT - 1, 3)
    assert classify(prev, curr) == "bonus_reset"


def test_rise_exactly_at_reset_at_is_rollover():
    # spec: now >= previous reset_at -> ordinary rollover
    prev = snap(1754368000, 62)
    curr = snap(RESET_AT, 3)
    assert classify(prev, curr) == "rollover"


def test_rise_one_second_after_reset_at_is_rollover():
    prev = snap(1754368000, 62)
    curr = snap(RESET_AT + 1, 3)
    assert classify(prev, curr) == "rollover"


def test_poll_crossing_window_boundary_is_rollover():
    # prev seen deep inside window 1, curr seen after that window ended
    prev = snap(RESET_AT - 50000, 91)
    curr = snap(RESET_AT + 3600, 2, reset_at=RESET_AT + 604800)
    assert classify(prev, curr) == "rollover"


def test_reset_at_moved_and_quota_rose_early_is_bonus():
    # OpenAI grants a fresh window before the old one expired: quota
    # rises AND the announced reset_at jumps forward. Still bonus —
    # the discriminant reads the PREVIOUS observation's reset_at.
    prev = snap(1754368000, 62)
    curr = snap(1754400000, 1, reset_at=1755004800)
    assert curr["observed_at"] < prev["reset_at"]
    assert classify(prev, curr) == "bonus_reset"


def test_reset_at_moved_without_quota_rise_is_no_event():
    prev = snap(1754368000, 62)
    curr = snap(1754400000, 62, reset_at=1755004800)
    assert classify(prev, curr) is None


def test_classify_does_not_mutate_inputs():
    prev, curr = snap(1754368000, 62), snap(1754400000, 1)
    prev_copy, curr_copy = dict(prev), dict(curr)
    classify(prev, curr)
    assert prev == prev_copy and curr == curr_copy
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_discriminant.py -v`
Expected: FAIL — `ImportError: cannot import name 'classify'`

- [ ] **Step 3: Write the implementation**

Append to `codex_reset_collector.py`:

```python
def classify(prev, curr):
    """Apply the discriminant to two consecutive snapshots.

    Quota "rises" when used_percent drops. Reads only fields that
    build_observation publishes in the payload, so anyone holding the
    log can recompute this classification (spec section 5).
    """
    quota_rose = curr["used_percent"] < prev["used_percent"]
    if not quota_rose:
        return None
    if curr["observed_at"] < prev["reset_at"]:
        return "bonus_reset"
    return "rollover"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_discriminant.py -v`
Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add codex_reset_collector.py tests/test_discriminant.py
git commit -m "feat: 判別式 classify 與邊界案例（±1s、reset_at 變動、跨視窗）"
```

---

### Task 3: Observation records — `build_observation` / `build_drift_observation`

**Files:**
- Modify: `codex_reset_collector.py` (append after `classify`)
- Test: `tests/test_observation.py`

**Interfaces:**
- Consumes: snapshots (Task 1), `kind` from `classify` (Task 2), `iso` (Task 1).
- Produces: `build_observation(prev: dict, curr: dict, kind: str) -> dict` and `build_drift_observation(observed_at: int, reason: str, top_level_keys: list) -> dict`. Task 5 appends their results to the log; Task 7's `reclassify` reads exactly these shapes.

Both rollovers and bonus resets are recorded as `quota_jump` observations with `payload.classified_as` carrying the collector's verdict. The spec says rollovers are "ignored" — they are ignored *as Track A events* (the decision core counts only bonus resets), but recording them gives auditors the negative cases: proof we did not misfile rollovers as bonuses.

- [ ] **Step 1: Write the failing tests**

`tests/test_observation.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_observation.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_observation'`

- [ ] **Step 3: Write the implementation**

Append to `codex_reset_collector.py`:

```python
def build_observation(prev, curr, kind):
    """One quota_jump Observation (spec section 5).

    The payload carries the discriminant's complete input — the five
    spec fields — so the classification can be recomputed by anyone
    holding the log. classified_as is this collector's verdict; the
    decision core recomputes its own and reports mismatches.
    """
    return {
        "v": SCHEMA_VERSION,
        "source": "self-account",
        "observed_at": iso(curr["observed_at"]),
        "occurred_at": [iso(prev["observed_at"]), iso(curr["observed_at"])],
        "evidence_kind": "quota_jump",
        "payload": {
            "prev_observed_at": iso(prev["observed_at"]),
            "prev_reset_at": iso(prev["reset_at"]),
            "prev_remaining": 100 - prev["used_percent"],
            "curr_remaining": 100 - curr["used_percent"],
            "curr_reset_at": iso(curr["reset_at"]),
            "window_source": curr["window_source"],
            "classified_as": kind,
        },
        "signature": None,
    }


def build_drift_observation(observed_at, reason, top_level_keys):
    """Record that upstream no longer matches the measured shape.

    Key names only — never response values: a drifted payload could
    contain anything, and this log is public.
    """
    return {
        "v": SCHEMA_VERSION,
        "source": "self-account",
        "observed_at": iso(observed_at),
        "occurred_at": [iso(observed_at), iso(observed_at)],
        "evidence_kind": "schema_drift",
        "payload": {"reason": reason, "top_level_keys": top_level_keys},
        "signature": None,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_observation.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add codex_reset_collector.py tests/test_observation.py
git commit -m "feat: Observation 建構（spec 五欄位 payload、區間 occurred_at、drift 只記 key 名）"
```

---

### Task 4: State + JSONL I/O

**Files:**
- Modify: `codex_reset_collector.py` (append; add `import os` and `from pathlib import Path` to the imports)
- Test: `tests/test_state_io.py`

**Interfaces:**
- Consumes: snapshot dicts (Task 1), observation dicts (Task 3).
- Produces: `load_state(state_path) -> dict | None` (raises `StateCorrupt(RuntimeError)` on unparseable state), `save_state(state_path, snapshot) -> None` (atomic, creates parent dirs), `append_observation(log_path, obs) -> None` (one compact JSON line, creates parent dirs). Task 5 wires these.

- [ ] **Step 1: Write the failing tests**

`tests/test_state_io.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_state_io.py -v`
Expected: FAIL — `ImportError: cannot import name 'StateCorrupt'`

- [ ] **Step 3: Write the implementation**

Add `import os` and `from pathlib import Path` to the top of `codex_reset_collector.py`, then append:

```python
class StateCorrupt(RuntimeError):
    """The saved baseline could not be parsed.

    Treating this as "no baseline" would silently discard the previous
    observation and could swallow a real event — fail loud instead and
    let the operator inspect or delete the file.
    """


def load_state(state_path):
    path = Path(state_path)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError) as exc:
        raise StateCorrupt(
            "cannot parse %s: %r — inspect or remove it" % (path, exc)
        ) from exc


def save_state(state_path, snapshot):
    """Atomic write: a poll interrupted mid-save must not corrupt the
    baseline the next discriminant run depends on."""
    path = Path(state_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(snapshot, fh)
    os.replace(tmp, path)


def append_observation(log_path, obs):
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obs, separators=(",", ":")) + "\n")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_state_io.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
git add codex_reset_collector.py tests/test_state_io.py
git commit -m "feat: 狀態機持久層（atomic state、append-only JSONL、壞檔 fail loud）"
```

---

### Task 5: One poll cycle — `run_once`

**Files:**
- Modify: `codex_reset_collector.py` (append after the I/O helpers)
- Test: `tests/test_run_once.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `run_once(fetch, now, state_path, log_path) -> int` where `fetch` is a zero-argument callable returning the parsed JSON body (dependency injection — tests never touch the network) and the return value is the process exit code: `0` ok, `2` schema drift recorded. Task 6's `main()` wraps this.

- [ ] **Step 1: Write the failing tests**

`tests/test_run_once.py`:

```python
import copy
import json
from pathlib import Path

from codex_reset_collector import load_state, run_once

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "tests" / "fixtures" / "usage_ok.json")
    .read_text()
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_run_once.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_once'`

- [ ] **Step 3: Write the implementation**

Append to `codex_reset_collector.py`:

```python
def run_once(fetch, now, state_path, log_path):
    """One poll cycle: fetch -> parse -> discriminant -> append -> save.

    `fetch` is injected so every path below is testable without a
    network. Returns the process exit code (0 ok, 2 schema drift).
    """
    prev = load_state(state_path)
    body = fetch()
    try:
        curr = parse_usage(body, now)
    except SchemaDrift as exc:
        keys = sorted(body.keys()) if isinstance(body, dict) else []
        append_observation(
            log_path, build_drift_observation(now, str(exc), keys)
        )
        # Deliberately NOT saving state: the last good baseline is kept
        # so the discriminant can resume from it after recovery.
        return 2
    if prev is not None:
        kind = classify(prev, curr)
        if kind is not None:
            append_observation(log_path, build_observation(prev, curr, kind))
    save_state(state_path, curr)
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_run_once.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add codex_reset_collector.py tests/test_run_once.py
git commit -m "feat: run_once 輪詢週期（注入 fetch、drift 保留 baseline、exit code）"
```

---

### Task 6: Real fetch, auth, CLI `main()`

**Files:**
- Modify: `codex_reset_collector.py` (append; add `import argparse`, `import sys`, `import time`, `import urllib.error`, `import urllib.request` to the imports)
- Test: `tests/test_auth_and_cli.py`

**Interfaces:**
- Consumes: `run_once` (Task 5).
- Produces: `AuthError(RuntimeError)`; `read_auth(auth_path) -> tuple[str, str]` (access_token, account_id — **nested under `tokens`**, as probed); `fetch_usage(token, account_id) -> dict`; `main(argv=None) -> int` with flags `--auth`, `--state`, `--log` and exit codes `0` ok / `2` drift / `3` auth problem / `4` network error / `5` corrupt state. Task 10's README documents this CLI.

- [ ] **Step 1: Write the failing tests**

`tests/test_auth_and_cli.py`:

```python
import json

import pytest

from codex_reset_collector import AuthError, main, read_auth

AUTH = {
    "auth_mode": "chatgpt",
    "OPENAI_API_KEY": None,
    "tokens": {
        "id_token": "id-synthetic",
        "access_token": "at-synthetic",
        "refresh_token": "rt-synthetic",
        "account_id": "acct-synthetic",
    },
    "last_refresh": "2026-08-04T00:00:00Z",
}


def test_read_auth_uses_nested_tokens(tmp_path):
    path = tmp_path / "auth.json"
    path.write_text(json.dumps(AUTH))
    assert read_auth(path) == ("at-synthetic", "acct-synthetic")


def test_read_auth_missing_file_is_auth_error(tmp_path):
    with pytest.raises(AuthError):
        read_auth(tmp_path / "absent.json")


def test_read_auth_top_level_token_is_auth_error(tmp_path):
    # the spec guessed access_token was top-level; the real file nests
    # it under "tokens" — a top-level-only file is NOT valid
    path = tmp_path / "auth.json"
    path.write_text(json.dumps({"access_token": "x", "account_id": "y"}))
    with pytest.raises(AuthError):
        read_auth(path)


def test_main_exit_3_when_auth_missing(tmp_path, capsys):
    code = main([
        "--auth", str(tmp_path / "absent.json"),
        "--state", str(tmp_path / "state.json"),
        "--log", str(tmp_path / "log.jsonl"),
    ])
    assert code == 3
    assert "auth" in capsys.readouterr().err.lower()


def test_main_exit_5_when_state_corrupt(tmp_path, capsys, monkeypatch):
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps(AUTH))
    state = tmp_path / "state.json"
    state.write_text("{not json")
    import codex_reset_collector as crc
    monkeypatch.setattr(crc, "fetch_usage", lambda token, account_id: {})
    code = main([
        "--auth", str(auth),
        "--state", str(state),
        "--log", str(tmp_path / "log.jsonl"),
    ])
    assert code == 5


def test_main_exit_4_on_network_error(tmp_path, capsys, monkeypatch):
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps(AUTH))

    import codex_reset_collector as crc

    def boom(token, account_id):
        raise crc.NetworkError("connection refused")

    monkeypatch.setattr(crc, "fetch_usage", boom)
    code = main([
        "--auth", str(auth),
        "--state", str(tmp_path / "state.json"),
        "--log", str(tmp_path / "log.jsonl"),
    ])
    assert code == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_auth_and_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'AuthError'`

- [ ] **Step 3: Write the implementation**

Add `import argparse`, `import sys`, `import time`, `import urllib.error`, `import urllib.request` to the imports of `codex_reset_collector.py`, then append:

```python
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
USER_AGENT = "codex-reset-likelihood-collector/0.1"


class AuthError(RuntimeError):
    """~/.codex/auth.json is missing or not in the shape Codex writes."""


class NetworkError(RuntimeError):
    """The usage endpoint could not be reached or answered non-2xx."""


def read_auth(auth_path):
    """Return (access_token, account_id) from Codex's auth.json.

    Both live NESTED under "tokens" — verified against the real file;
    they are not top-level. The values are used for one request header
    each and are never written anywhere.
    """
    path = Path(auth_path)
    try:
        with path.open(encoding="utf-8") as fh:
            auth = json.load(fh)
        tokens = auth["tokens"]
        return tokens["access_token"], tokens["account_id"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise AuthError(
            "cannot read credentials from %s: %r "
            "(expected Codex auth.json with tokens.access_token / "
            "tokens.account_id)" % (path, exc)
        ) from exc


def fetch_usage(token, account_id):
    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": "Bearer " + token,
            "ChatGPT-Account-ID": account_id,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise NetworkError("usage endpoint unreachable: %r" % exc) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="codex-reset-likelihood local collector (one poll "
        "per invocation; drive it with cron/launchd)"
    )
    parser.add_argument(
        "--auth", default=str(Path.home() / ".codex" / "auth.json")
    )
    parser.add_argument(
        "--state",
        default=".collector-state/last_observation.json",
    )
    parser.add_argument("--log", default="data/observations.jsonl")
    args = parser.parse_args(argv)

    try:
        token, account_id = read_auth(args.auth)
    except AuthError as exc:
        print("auth error: %s" % exc, file=sys.stderr)
        return 3

    now = int(time.time())
    try:
        code = run_once(
            lambda: fetch_usage(token, account_id), now, args.state, args.log
        )
    except NetworkError as exc:
        print("network error: %s" % exc, file=sys.stderr)
        return 4
    except StateCorrupt as exc:
        print("state error: %s" % exc, file=sys.stderr)
        return 5

    if code == 2:
        print("schema drift recorded; inference must halt", file=sys.stderr)
    else:
        print("ok: observed at %s" % iso(now))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_auth_and_cli.py -v`
Expected: 6 PASS

- [ ] **Step 5: Run the full collector suite**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS (Tasks 1–6 combined; no regressions)

- [ ] **Step 6: Commit**

```bash
git add codex_reset_collector.py tests/test_auth_and_cli.py
git commit -m "feat: 真實 fetch 與 CLI（tokens 巢狀 auth、exit code 0/2/3/4/5）"
```

---

### Task 7: Decision core — independent re-classification + cross-check

**Files:**
- Create: `core/__init__.py` (empty)
- Create: `core/decision_core.py`
- Test: `tests/test_reclassify.py`

**Interfaces:**
- Consumes: observation dict shapes from Task 3 (via the log; the core never imports the collector).
- Produces: `parse_ts(s: str) -> int`; `midpoint(interval: list) -> float`; `reclassify(obs: dict) -> str | None`; `decide(events: list, now_epoch: int) -> dict` returning at this stage `{"status": ..., "events": [...], "mismatches": [...], "hazard": None}` where each event row is `{"occurred_at": [str, str], "observed_at": str, "lag_seconds": float, "recorded_kind": str|None, "recomputed_kind": str|None, "mismatch": bool}`. Task 8 extends `decide` with the hazard; Task 10 wraps it in a CLI.

The decision core **must not import** `codex_reset_collector`. `reclassify` re-implements the discriminant reading only the published payload — this duplication is the point (the auditor's independent recomputation; a shared implementation could hide a shared bug). Track A counts events by the *recomputed* kind, not the collector's word.

- [ ] **Step 1: Write the failing tests**

`tests/test_reclassify.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_reclassify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.decision_core'`

- [ ] **Step 3: Write the implementation**

`core/__init__.py`: empty file.

`core/decision_core.py`:

```python
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
```

(`now_epoch` is unused until Task 8 adds the hazard — keep the parameter now so the signature never changes.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_reclassify.py -v`
Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add core/__init__.py core/decision_core.py tests/test_reclassify.py
git commit -m "feat: decision core 獨立重跑判別式並回報 mismatch（審計面）"
```

---

### Task 8: Hazard — Weibull by method of moments

**Files:**
- Modify: `core/decision_core.py` (add `import math`; extend `decide`)
- Test: `tests/test_hazard.py`

**Interfaces:**
- Consumes: `decide` scaffold from Task 7.
- Produces: `weibull_mom(gaps_days: list[float]) -> tuple[float, float, float]` (k, lam_days, mean_days); `p24(k: float, lam: float, elapsed_days: float) -> float`; constants `MIN_EVENTS = 3`, `MIN_CV = 0.02`; `decide` now returns `status` ∈ {`OK`, `INSUFFICIENT_DATA`, `HALT_SCHEMA_DRIFT`} and, when `OK`, `hazard = {"model": "weibull", "k", "lam_days", "mean_gap_days", "elapsed_days", "p24"}`.

- [ ] **Step 1: Write the failing tests**

`tests/test_hazard.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_hazard.py -v`
Expected: FAIL — `ImportError: cannot import name 'MIN_EVENTS'`

- [ ] **Step 3: Write the implementation**

In `core/decision_core.py`, add `import math` at the top, add the constants and two functions, and extend `decide`:

```python
MIN_EVENTS = 3   # spec section 6 hard rule: below 3 events, no number
MIN_CV = 0.02    # zero-variance gaps would send k -> infinity


def weibull_mom(gaps_days):
    """Method-of-moments Weibull fit, identical to the deployed JS:
    k = cv^-1.086, lam = mean / Gamma(1 + 1/k)."""
    n = len(gaps_days)
    mean = sum(gaps_days) / n
    variance = sum((g - mean) ** 2 for g in gaps_days) / (n - 1)
    cv = max(math.sqrt(variance) / mean, MIN_CV)
    k = cv ** -1.086
    lam = mean / math.exp(math.lgamma(1 + 1 / k))
    return k, lam, mean


def p24(k, lam, elapsed_days):
    """P(event within 24h | already waited elapsed_days)."""
    def cum_hazard(t):
        return (max(t, 0.0) / lam) ** k

    return 1 - math.exp(-(cum_hazard(elapsed_days + 1) - cum_hazard(elapsed_days)))
```

Replace the tail of `decide` (everything after the `verdict = {...}` literal) with:

```python
    if drifted:
        verdict["status"] = "HALT_SCHEMA_DRIFT"
        return verdict
    if len(bonus) < MIN_EVENTS:
        verdict["status"] = "INSUFFICIENT_DATA"
        return verdict

    mids = sorted(midpoint(row["occurred_at"]) for row in bonus)
    gaps_days = [(b - a) / 86400 for a, b in zip(mids, mids[1:])]
    k, lam, mean = weibull_mom(gaps_days)
    elapsed_days = (now_epoch - mids[-1]) / 86400
    verdict["status"] = "OK"
    verdict["hazard"] = {
        "model": "weibull",
        "k": k,
        "lam_days": lam,
        "mean_gap_days": mean,
        "elapsed_days": elapsed_days,
        "p24": p24(k, lam, elapsed_days),
    }
    return verdict
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_hazard.py tests/test_reclassify.py -v`
Expected: all PASS (Task 7's tests must survive the `decide` extension)

- [ ] **Step 5: Commit**

```bash
git add core/decision_core.py tests/test_hazard.py
git commit -m "feat: Weibull hazard 與部署頁 JS 錨定一致（k=3.16, λ=19.4, p24=1.7%）"
```

---

### Task 9: Property-style seeded fuzz tests

**Files:**
- Test: `tests/test_properties.py` (no production code — this task hardens what exists)

**Interfaces:**
- Consumes: `classify`, `build_observation`, `build_drift_observation` (collector); `decide` (core).
- Produces: nothing new — invariant coverage only.

- [ ] **Step 1: Write the tests (they should pass immediately if Tasks 1–8 are correct; any failure is a real bug found)**

`tests/test_properties.py`:

```python
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
```

- [ ] **Step 2: Run the tests**

Run: `python3 -m pytest tests/test_properties.py -v`
Expected: PASS. If any seed fails, that is a real defect in Tasks 1–8 — fix the production code (never weaken the invariant), then re-run the entire suite.

- [ ] **Step 3: Run the full suite**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_properties.py
git commit -m "test: 200 顆種子的不變量測試（純度、冷啟動、drift 停機、機率界）"
```

---

### Task 10: Core CLI, committed empty log, README

**Files:**
- Modify: `core/decision_core.py` (append `main`; add `import argparse`, `import json`, `import sys`, `import time` — keep them stdlib-top with the existing imports)
- Create: `data/observations.jsonl` (empty)
- Modify: `README.md` (add a "Running the instrument" section after "Deploy")
- Test: `tests/test_core_cli.py`

**Interfaces:**
- Consumes: `decide` (Task 8).
- Produces: `python3 -m core.decision_core <log.jsonl> [--now ISO]` printing the verdict as JSON — the "anyone can clone and re-run" entry point the README promises.

- [ ] **Step 1: Write the failing tests**

`tests/test_core_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_core_cli.py -v`
Expected: FAIL — CLI exits with an argparse/`No module` error (no `main` yet) and `data/observations.jsonl` does not exist.

- [ ] **Step 3: Write the implementation**

Create the empty log: `touch data/observations.jsonl` (the `data/` directory is new; the file itself is the tracked placeholder — no `.gitkeep` needed).

Append to `core/decision_core.py` (adding `import argparse`, `import json`, `import sys`, `import time` to the imports):

```python
def _load_log(path):
    events = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except ValueError as exc:
                raise SystemExit(
                    "%s line %d is not valid JSON: %r" % (path, lineno, exc)
                )
    return events


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Re-run the decision core over an observation log. "
        "This is the reproducibility entry point: the same function the "
        "site's scorecards come from, on the same public log."
    )
    parser.add_argument("log", help="path to observations.jsonl")
    parser.add_argument(
        "--now",
        help="ISO-8601 UTC (e.g. 2026-08-04T00:00:00Z); default: real now",
    )
    args = parser.parse_args(argv)

    now_epoch = parse_ts(args.now) if args.now else int(time.time())
    verdict = decide(_load_log(args.log), now_epoch)
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_core_cli.py -v`
Expected: 3 PASS

- [ ] **Step 5: Add the README section**

Insert into `README.md`, between the "Deploy" section and "## Documents":

````markdown
## Running the instrument

The collector is one stdlib-only file. One invocation = one poll; drive it with cron or launchd:

```shell
python3 codex_reset_collector.py            # reads ~/.codex/auth.json locally
python3 -m pytest tests/ -v                 # the full boundary-case suite

# every 30 minutes via cron (interval width = detection-lag floor):
*/30 * * * * cd /path/to/codex-reset-likelihood && python3 codex_reset_collector.py >> .collector-state/collector.log 2>&1
```

Exit codes: `0` ok · `2` schema drift recorded (inference halts) · `3` auth · `4` network · `5` corrupt state.

Re-run the decision core over the public log — this is the reproducibility claim made executable:

```shell
python3 -m core.decision_core data/observations.jsonl
```

`data/observations.jsonl` is committed **empty**: no real observation has been collected yet, and the deployed page stays synthetic until the log holds ≥ 3 real events.
````

- [ ] **Step 6: Run the full suite one last time**

Run: `python3 -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add core/decision_core.py data/observations.jsonl README.md tests/test_core_cli.py
git commit -m "feat: decision core CLI 與可重跑入口，README 補使用說明"
```

---

## Out of scope (explicitly)

- **Ingest server / POST /observations / signatures** — v2 crowd. v1 has N=1 and the git-tracked log *is* the ingest; `signature: null` reserves the field.
- **Social watcher** — advisory-only by design; nothing depends on it.
- **Wiring `index.html` to real data** — forbidden until ≥ 3 real events exist (cold-start rule); the page's synthetic labelling stays.
- **hypothesis** — seeded loops suffice; no new dependency.

## Spec-coverage map (self-review record)

| Spec section | Where |
|---|---|
| §3 discriminant + state machine | Tasks 2, 5 |
| §5 Observation schema, 5-field payload, interval `occurred_at` | Task 3 |
| §5 "anyone can re-run the classification" | Task 7 (`reclassify` + mismatch report) |
| §6 hazard, cold-start < 3 | Task 8 (Weibull per deployed page, not spec's exponential — deviation documented in Global Constraints) |
| §7 schema drift fail-loud | Tasks 1, 5, 8 |
| §8 credentials never leave; no secrets in log | Tasks 3 (test), 6 |
| §9 single file, zero deps, JSONL in git | structure + Task 10 |
| §10 boundary cases (±1s, reset_at moved, window crossing, midnight, drift halts) | Tasks 2, 3, 8 |
| §10 property tests (events ≤ jumps, < 3 → insufficient) | Task 9 |
