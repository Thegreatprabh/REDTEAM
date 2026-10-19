"""Provider base: stdlib HTTP client + key handling discipline."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def redact_key(key: str) -> str:
    """Redact an API key to its last 4 chars for error messages. Never log full keys."""
    if not key:
        return "<none>"
    tail = key[-4:] if len(key) >= 4 else "****"
    return f"…{tail}"


class ProviderError(Exception):
    """Raised when a provider call fails. Never carries the raw key."""

    def __init__(self, provider: str, message: str, key: str = ""):
        self.provider = provider
        super().__init__(f"[{provider}] {message} (key {redact_key(key)})")


@dataclass
class Completion:
    text: str
    model: str
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class Provider:
    """Base class. Subclasses implement _payload() and _parse()."""

    name: str = "base"

    def __init__(self, api_key: str, model: str, timeout: int = 60):
        if not api_key or not api_key.strip():
            raise ProviderError(self.name, "empty API key")
        self._key = api_key
        self.model = model
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {"Content-Type": "application/json"}

    def _payload(self, messages: List[Message]) -> Dict[str, Any]:
        raise NotImplementedError

    def _parse(self, data: Dict[str, Any]) -> str:
        raise NotImplementedError

    def _url(self) -> str:
        raise NotImplementedError

    def complete(self, messages: List[Message]) -> Completion:
        body = json.dumps(self._payload(messages)).encode("utf-8")
        req = urllib.request.Request(self._url(), data=body, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ProviderError(self.name, f"HTTP {e.code}") from None
        except urllib.error.URLError as e:
            raise ProviderError(self.name, f"network error: {e.reason}") from None
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            raise ProviderError(self.name, f"bad response: {type(e).__name__}") from None
        return Completion(text=self._parse(data), model=self.model, raw=data)

    def __repr__(self) -> str:  # never leak the key
        return f"{type(self).__name__}(model={self.model!r}, key={redact_key(self._key)})"
