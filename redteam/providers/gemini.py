"""Gemini provider (generateContent), stdlib urllib. Key goes in query param (Google's API shape)."""

from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import quote

from .base import Message, Provider

DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiProvider(Provider):
    name = "gemini"

    def _url(self) -> str:
        # NOTE: Gemini's REST shape requires the key in the query string.
        # The key is never logged; ProviderError redacts it.
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(self.model, safe='')}:generateContent?key={quote(self._key, safe='')}"
        )

    def _payload(self, messages: List[Message]) -> Dict[str, Any]:
        system_parts = [m.content for m in messages if m.role == "system"]
        rest = messages and [m for m in messages if m.role != "system"]
        contents = [
            {"role": "user" if m.role == "user" else "model",
             "parts": [{"text": m.content}]}
            for m in rest
        ]
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 512},
        }
        if system_parts:
            payload["system_instruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }
        return payload

    def _parse(self, data: Dict[str, Any]) -> str:
        cands = data.get("candidates", [])
        if not cands:
            return ""
        parts = cands[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
