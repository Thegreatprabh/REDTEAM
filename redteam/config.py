"""Local config: API keys live in ~/.redteam/config.json (0600). Keys are
never printed, logged, or echoed — see providers/base.py for the discipline."""

from __future__ import annotations

import getpass
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, Optional

CONFIG_DIR_NAME = ".redteam"
CONFIG_FILE_NAME = "config.json"


def get_config_dir() -> Path:
    d = Path.home() / CONFIG_DIR_NAME
    d.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _config_path() -> Path:
    return get_config_dir() / CONFIG_FILE_NAME


def load_config() -> Dict[str, Any]:
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(data: Dict[str, Any]) -> Path:
    path = _config_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    if stat.S_IMODE(os.stat(path).st_mode) != 0o600:
        os.chmod(path, 0o600)
    return path


def get_key(provider: str, explicit: Optional[str] = None) -> Optional[str]:
    """Key resolution: --key arg > env var > config file. Returns None if unset."""
    if explicit and explicit.strip():
        return explicit.strip()
    env_map = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
               "gemini": "GEMINI_API_KEY"}
    env_val = os.environ.get(env_map.get(provider, ""), "")
    if env_val and env_val.strip():
        return env_val.strip()
    keys = load_config().get("keys", {})
    if isinstance(keys, dict):
        val = keys.get(provider)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return None


def save_key_interactive(provider: str) -> Path:
    key = getpass.getpass(f"API key for {provider} (hidden): ").strip()
    if not key:
        raise ValueError("empty key — not saved")
    data = load_config()
    keys = data.get("keys")
    if not isinstance(keys, dict):
        keys = {}
        data["keys"] = keys
    keys[provider] = key
    return save_config(data)


def detect_provider(key: str) -> str:
    """Auto-detect provider from key prefix. Unknown prefix => clear error."""
    k = (key or "").strip()
    if k.startswith("sk-ant-"):
        return "anthropic"
    if k.startswith("AIza"):
        return "gemini"
    if k.startswith("sk-"):
        return "openai"
    raise ValueError(
        "could not detect provider from key prefix "
        "(expected sk-ant-*, AIza*, or sk-*); pass --provider explicitly")
