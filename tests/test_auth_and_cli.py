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
