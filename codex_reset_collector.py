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
