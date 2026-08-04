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

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

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
