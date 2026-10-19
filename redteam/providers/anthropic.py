"""Anthropic provider (messages API), stdlib urllib."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import Message, Provider

DEFAULT_MODEL = "claude-3-5-haiku-latest"
ANTHROPIC_VERSION = "2023-06-01"


class AnthropicProvider(Provider):
    name = "anthropic"

    def _url(self) -> str:
        return "https://api.anthropic.com/v1/messages"

    def _headers(self) -> Dict[str, str]:
        h = super()._headers()
        h["x-api-key"] = self._key
        h["anthropic-version"] = ANTHROPIC_VERSION
        return h

    def _payload(self, messages: List[Message]) -> Dict[str, Any]:
        system_parts = [m.content for m in messages if m.role == "system"]
        rest = [m.to_dict() for m in messages if m.role != "system"]
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": rest,
            "temperature": 0.7,
            "max_tokens": 512,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        return payload

    def _parse(self, data: Dict[str, Any]) -> str:
        blocks = data.get("content", [])
        texts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        return "".join(texts)
