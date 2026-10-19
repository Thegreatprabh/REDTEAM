"""OpenAI provider (chat completions), stdlib urllib."""

from __future__ import annotations

from typing import Any, Dict, List

from .base import Message, Provider

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(Provider):
    name = "openai"

    def _url(self) -> str:
        return "https://api.openai.com/v1/chat/completions"

    def _headers(self) -> Dict[str, str]:
        h = super()._headers()
        h["Authorization"] = f"Bearer {self._key}"
        return h

    def _payload(self, messages: List[Message]) -> Dict[str, Any]:
        return {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": 0.7,
            "max_tokens": 512,
        }

    def _parse(self, data: Dict[str, Any]) -> str:
        return data["choices"][0]["message"]["content"] or ""
