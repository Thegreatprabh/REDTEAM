"""Config + CLI tests. HOME is isolated via monkeypatch; no real keys."""

import json
import os

import pytest

from redteam import config as cfg


def _isolate_home(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Path.home() caches? No — it reads env each call. Ensure no stale dir.
    return home


def test_detect_provider():
    assert cfg.detect_provider("sk-ant-abc") == "anthropic"
    assert cfg.detect_provider("AIzaXYZ") == "gemini"
    assert cfg.detect_provider("sk-xyz") == "openai"
    with pytest.raises(ValueError):
        cfg.detect_provider("weird-key")


def test_get_key_priority(monkeypatch, tmp_path):
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    assert cfg.get_key("openai", explicit="sk-arg") == "sk-arg"
    assert cfg.get_key("openai") == "sk-env"
    monkeypatch.delenv("OPENAI_API_KEY")
    cfg.save_config({"keys": {"openai": "sk-file"}})
    assert cfg.get_key("openai") == "sk-file"
    assert cfg.get_key("anthropic") is None


def test_config_file_perms(monkeypatch, tmp_path):
    home = _isolate_home(monkeypatch, tmp_path)
    p = cfg.save_config({"keys": {"openai": "sk-x"}})
    import stat
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    assert p.parent == home / ".redteam"


def test_load_corrupt_config(monkeypatch, tmp_path):
    home = _isolate_home(monkeypatch, tmp_path)
    d = home / ".redteam"
    d.mkdir()
    (d / "config.json").write_text("{{{garbage")
    assert cfg.load_config() == {}


def test_save_key_interactive_never_echoes(monkeypatch, tmp_path, capsys):
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setattr("getpass.getpass", lambda prompt="": "sk-test-123")
    cfg.save_key_interactive("openai")
    out = capsys.readouterr().out
    assert "sk-test-123" not in out
    assert cfg.load_config()["keys"]["openai"] == "sk-test-123"


def test_cli_list(capsys):
    from redteam.cli import main
    assert main(["list", "--suite", "injection"]) == 0
    out = capsys.readouterr().out
    assert "inj-001" in out and "10 attacks" in out


def test_cli_list_all(capsys):
    from redteam.cli import main
    assert main(["list"]) == 0
    assert "50 attacks" in capsys.readouterr().out


def test_cli_run_no_key_exits_2(monkeypatch, tmp_path, capsys):
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from redteam.cli import main
    with pytest.raises(SystemExit) as ei:
        main(["run", "--provider", "openai"])
    assert ei.value.code == 2


def test_cli_version(capsys):
    from redteam.cli import main
    with pytest.raises(SystemExit) as ei:
        main(["--version"])
    assert ei.value.code == 0
    assert "0.1.0" in capsys.readouterr().out
