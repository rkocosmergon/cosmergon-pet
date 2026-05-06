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
        # Diagnostic-only: last raw model output before parse.
        # Read by llm_decider._maybe_dump_decision_outcome when
        # COSMERGON_PET_DECISION_DUMP_PATH is set. Never read by the
        # decision loop itself — it would couple the diagnosis path
        # to gameplay. S163 A.2 setup.
        self.last_raw_response: str | None = None

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
        # Stash before any parse / validation work so the diagnostic dump
        # can read the model's verbatim output even when JSON parsing
        # fails downstream.
        self.last_raw_response = raw_response
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

    async def reflect(
        self,
        signals: dict[str, Any],
        persona: str,
        agent_name: str,
    ) -> dict[str, str] | None:
        """Synthesize a self-reflection from collected decision signals.

        Implements the LLMProvider.reflect contract: given top-5 best,
        bottom-5 worst, and dominant action patterns, ask the model for
        three structured strings (lessons / avoid / double_down). Schema-
        constrained via Ollama's structured-output mode so the response
        always matches the exact shape Cosmergon's POST /reflection
        accepts.

        Returns None on any LLM error, schema violation, or empty signals
        — never raises from this path. The Pet is expected to retry on
        the next decision tick when ``state.reflection_due`` is still set.
        """
        top = signals.get("top_5") or []
        bottom = signals.get("bottom_5") or []
        if not top and not bottom:
            return None  # nothing to reflect on yet
        prompt = self._compose_reflection_prompt(signals, persona, agent_name)
        # Ollama structured-output schema for the reflection result. Length
        # bounds match Cosmergon's ReflectionResult pydantic model so the
        # POST /reflection round-trip never trips a 422.
        reflection_schema = {
            "type": "object",
            "required": ["lessons", "avoid", "double_down"],
            "properties": {
                "lessons": {"type": "string", "minLength": 100, "maxLength": 500},
                "avoid": {"type": "string", "minLength": 50, "maxLength": 200},
                "double_down": {"type": "string", "minLength": 50, "maxLength": 200},
            },
            "additionalProperties": False,
        }
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": reflection_schema,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                resp = await client.post(f"{self.url}/api/generate", json=body)
                resp.raise_for_status()
                payload = resp.json()
        except httpx.HTTPError as e:
            logger.warning("reflection: ollama http error: %s", e)
            return None
        raw = payload.get("response", "")
        if not raw:
            logger.warning("reflection: empty ollama response")
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning("reflection: non-JSON response: %s", e)
            return None
        # Defensive validation against the shape Cosmergon expects.
        for key in ("lessons", "avoid", "double_down"):
            if not isinstance(parsed.get(key), str) or not parsed[key].strip():
                logger.warning("reflection: missing/blank field %r in %r", key, parsed)
                return None
        return {
            "lessons": parsed["lessons"],
            "avoid": parsed["avoid"],
            "double_down": parsed["double_down"],
        }

    @staticmethod
    def _compose_reflection_prompt(
        signals: dict[str, Any],
        persona: str,
        agent_name: str,
    ) -> str:
        """Build a compact reflection prompt from raw signal data.

        Trim each top/bottom entry to its action + score so the prompt
        stays in budget on a small model. The model never sees full
        decision metadata — just enough signal to write three sentences.
        """
        name = agent_name or "the agent"
        persona_str = persona or "scientist"

        def _summarize(rows: list[dict[str, Any]]) -> str:
            if not rows:
                return "  (none)"
            lines = []
            for r in rows[:5]:
                action = (r.get("decision_data") or {}).get("action", "?")
                score = r.get("quality_score")
                tick = r.get("tick_number", "?")
                score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "?"
                lines.append(f"  - tick {tick}: {action} (quality {score_str})")
            return "\n".join(lines)

        top_block = _summarize(signals.get("top_5") or [])
        bottom_block = _summarize(signals.get("bottom_5") or [])
        dominant = signals.get("dominant_actions") or []
        dominant_block = (
            ", ".join(f"{d.get('action', '?')}×{d.get('n', 0)}" for d in dominant[:5]) or "(none)"
        )
        decisions = signals.get("decisions_in_window", 0)

        return (
            f"You are {name}, a {persona_str}-persona agent in Cosmergon.\n"
            f"Reflect on your last {decisions} decisions and produce three short "
            f"strings: lessons (100-500 chars), avoid (50-200 chars), double_down "
            f"(50-200 chars).\n\n"
            f"## Your best 5 decisions (highest quality)\n{top_block}\n\n"
            f"## Your worst 5 decisions (lowest quality)\n{bottom_block}\n\n"
            f"## Your most-used actions\n{dominant_block}\n\n"
            f'Respond with JSON only: {{"lessons": ..., "avoid": ..., '
            f'"double_down": ...}}\n'
            f"Speak in first person ('I learned...'). Specific, actionable, "
            f"persona-tone. No markdown, no preamble."
        )
