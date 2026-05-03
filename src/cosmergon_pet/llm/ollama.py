"""Ollama provider — local-first LLM adapter.

Uses Ollama's HTTP API (default port 11434). Designed for the canonical
Pet setup: Pet on a Raspberry Pi at home, Ollama on a Mac Mini in the
same LAN, model ``llama3.2:3b`` (the S101-benchmark winner).

Configuration via env vars (CLI-overridable from face.py):
  PET_LLM_OLLAMA_URL   default ``http://localhost:11434``
  PET_LLM_OLLAMA_MODEL default ``llama3.2:3b``

For a Mac Mini in the LAN, point the URL at the host:
  ``http://mac-mini.local:11434`` (mDNS) or a static IP.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

from .base import LLMProviderError

logger = logging.getLogger(__name__)


class OllamaProvider:
    """Talks to a local-or-LAN Ollama instance via /api/generate.

    Uses ``format: "json"`` so Ollama emits structured output that
    parses cleanly into the Pet's action schema.
    """

    name = "ollama"

    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout_s: float = 60.0,
    ) -> None:
        self.url = (url or os.environ.get("PET_LLM_OLLAMA_URL", "http://localhost:11434")).rstrip(
            "/"
        )
        self.model = model or os.environ.get("PET_LLM_OLLAMA_MODEL", "llama3.2:3b")
        self.timeout_s = timeout_s

    @property
    def model_string(self) -> str:
        return f"ollama/{self.model}"

    async def decide(
        self,
        system_prompt: str,
        memory: str,
        world: str,
        schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prompt = self._compose_prompt(system_prompt, memory, world)
        # Ollama structured-output (since Q1/2025): when `format` is a
        # JSON-Schema object instead of the string "json", the decoder
        # constrains generation to schema-conforming tokens. This is the
        # difference between "valid JSON" (anything goes) and "exactly
        # one of the allowed shapes" (each option fully specified).
        # Without this, smaller models (qwen2.5:7b in S160 empirics)
        # output `{"action":"place_cells","params":{}}` — valid JSON,
        # invalid game move.
        format_value: Any = schema if schema else "json"
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": format_value,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.url}/api/generate", json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as e:
            raise LLMProviderError(f"ollama http error: {e}") from e

        raw_response = payload.get("response", "")
        if not raw_response:
            raise LLMProviderError("ollama returned empty response field")

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise LLMProviderError(
                f"ollama response is not JSON despite format constraint: {raw_response[:200]!r}"
            ) from e

        action = parsed.get("action")
        params = parsed.get("params", {})
        if not isinstance(action, str) or not action:
            raise LLMProviderError(f"missing or non-string 'action' in {parsed!r}")
        if not isinstance(params, dict):
            raise LLMProviderError(f"'params' must be a dict, got {type(params).__name__}")
        return {"action": action, "params": params}

    @staticmethod
    def _compose_prompt(system_prompt: str, memory: str, world: str) -> str:
        memory_block = memory or "(no prior memory yet)"
        return (
            f"{system_prompt}\n\n"
            f"# Your memory\n{memory_block}\n\n"
            f"# Current world\n{world}\n\n"
            f"# Your decision (JSON only)"
        )
