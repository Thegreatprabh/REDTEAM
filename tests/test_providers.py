"""Provider tests: payload shapes, key discipline. Network fully mocked."""

import io
import json
import urllib.error

import pytest

from redteam.providers.anthropic import AnthropicProvider
from redteam.providers.base import Message, ProviderError, redact_key
from redteam.providers.gemini import GeminiProvider
from redteam.providers.openai import OpenAIProvider


class FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch(monkeypatch, payload=None, exc=None):
    def fake_urlopen(req, timeout=None):
        if exc:
            raise exc
        return FakeResp(payload)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)


def test_redact_key():
    assert redact_key("sk-ant-abc123") == "…c123"
    assert redact_key("") == "<none>"
    assert "sk-ant-abc123" not in redact_key("sk-ant-abc123")


def test_empty_key_rejected():
    with pytest.raises(ProviderError):
        OpenAIProvider(api_key="", model="x")


def test_openai_payload_and_parse(monkeypatch):
    _patch(monkeypatch, {"choices": [{"message": {"content": "hi"}}]})
    p = OpenAIProvider(api_key="sk-test", model="gpt-x")
    c = p.complete([Message("system", "sys"), Message("user", "u")])
    assert c.text == "hi" and c.model == "gpt-x"


def test_openai_auth_header(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["auth"] = req.get_header("Authorization")
        return FakeResp({"choices": [{"message": {"content": "x"}}]})
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    OpenAIProvider(api_key="sk-secret", model="m").complete([Message("user", "u")])
    assert captured["auth"] == "Bearer sk-secret"


def test_anthropic_system_extraction(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data.decode())
        return FakeResp({"content": [{"type": "text", "text": "ok"}]})
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    p = AnthropicProvider(api_key="sk-ant-x", model="claude-x")
    c = p.complete([Message("system", "SYS"), Message("user", "hi")])
    assert c.text == "ok"
    assert captured["body"]["system"] == "SYS"
    assert all(m["role"] != "system" for m in captured["body"]["messages"])


def test_gemini_parse(monkeypatch):
    _patch(monkeypatch, {"candidates": [{"content": {"parts": [{"text": "yo"}]}}]})
    p = GeminiProvider(api_key="AIza-x", model="gemini-x")
    assert p.complete([Message("user", "u")]).text == "yo"


def test_http_error_redacts_key(monkeypatch):
    _patch(monkeypatch, exc=urllib.error.HTTPError(
        url="u", code=401, msg="x", hdrs={}, fp=io.BytesIO(b"")))
    with pytest.raises(ProviderError) as ei:
        OpenAIProvider(api_key="sk-live-secret-key", model="m").complete([Message("user", "u")])
    assert "sk-live-secret-key" not in str(ei.value)
    assert "401" in str(ei.value)


def test_network_error_clean(monkeypatch):
    _patch(monkeypatch, exc=urllib.error.URLError("boom"))
    with pytest.raises(ProviderError) as ei:
        OpenAIProvider(api_key="sk-x", model="m").complete([Message("user", "u")])
    assert "boom" in str(ei.value)


def test_repr_never_leaks_key():
    p = OpenAIProvider(api_key="sk-super-secret", model="m")
    assert "sk-super-secret" not in repr(p)
