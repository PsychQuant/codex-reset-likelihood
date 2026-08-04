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
