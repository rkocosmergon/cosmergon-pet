"""Tests for the pluggable LLM provider layer.

Covers the provider protocol contract, factory, and OllamaProvider's
HTTP + JSON parsing. No real network is touched — httpx is mocked
via ``unittest.mock``.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


def _import_or_skip() -> Any:
    try:
        from cosmergon_pet.llm import (  # noqa: F401
            LLMProvider,
            LLMProviderError,
            OllamaProvider,
            available_providers,
            build_provider,
        )
    except Exception:
        try:
            import pytest  # type: ignore[import-not-found]
        except Exception:
            print("SKIP  cosmergon_pet.llm not importable", file=sys.stderr)
            sys.exit(0)
        pytest.skip("cosmergon_pet.llm not importable")
    import cosmergon_pet.llm as llm_module
    return llm_module


def test_factory_lists_known_providers() -> None:
    llm = _import_or_skip()
    names = llm.available_providers()
    assert "ollama" in names


def test_factory_unknown_provider_raises() -> None:
    llm = _import_or_skip()
    try:
        llm.build_provider("does-not-exist")
    except ValueError as e:
        assert "ollama" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown provider")


def test_ollama_provider_satisfies_protocol() -> None:
    """Runtime-checkable Protocol must accept the concrete provider."""
    llm = _import_or_skip()
    p = llm.OllamaProvider(url="http://x", model="m")
    assert isinstance(p, llm.LLMProvider)
    assert p.name == "ollama"
    assert p.model_string == "ollama/m"


def test_ollama_url_normalisation() -> None:
    """Trailing slash on URL is stripped (canonical form for f-string concat)."""
    llm = _import_or_skip()
    p = llm.OllamaProvider(url="http://mac-mini.local:11434/", model="llama3.2:3b")
    assert p.url == "http://mac-mini.local:11434"


def test_ollama_env_var_defaults(monkeypatch: Any) -> None:
    llm = _import_or_skip()
    monkeypatch.setenv("PET_LLM_OLLAMA_URL", "http://example:9999")
    monkeypatch.setenv("PET_LLM_OLLAMA_MODEL", "qwen2.5:7b")
    p = llm.OllamaProvider()
    assert p.url == "http://example:9999"
    assert p.model == "qwen2.5:7b"
    assert p.model_string == "ollama/qwen2.5:7b"


def _async(value: Any) -> AsyncMock:
    """Build an AsyncMock that returns ``value``."""
    m = AsyncMock()
    m.return_value = value
    return m


def _ollama_response(body: dict) -> MagicMock:
    """Mock httpx.Response with a JSON body."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value=body)
    return resp


async def _aexecute(coro: Any) -> Any:
    return await coro


def test_ollama_decide_happy_path() -> None:
    """Happy path: provider returns parsed action+params dict."""
    import asyncio
    llm = _import_or_skip()

    fake_resp = _ollama_response({
        "response": json.dumps({"action": "place_cells", "params": {"field_id": "abc", "preset": "block"}}),
    })

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def post(self, *_: Any, **__: Any) -> Any:
            return fake_resp

    with patch("cosmergon_pet.llm.ollama.httpx.AsyncClient", return_value=_Client()):
        p = llm.OllamaProvider(url="http://x", model="m")
        out = asyncio.run(p.decide("sys", "mem", "world"))

    assert out == {"action": "place_cells", "params": {"field_id": "abc", "preset": "block"}}


def test_ollama_decide_malformed_json_raises_provider_error() -> None:
    """Ollama returned non-JSON despite format=json — raise LLMProviderError."""
    import asyncio
    llm = _import_or_skip()

    fake_resp = _ollama_response({"response": "not really json {"})

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def post(self, *_: Any, **__: Any) -> Any:
            return fake_resp

    with patch("cosmergon_pet.llm.ollama.httpx.AsyncClient", return_value=_Client()):
        p = llm.OllamaProvider(url="http://x", model="m")
        try:
            asyncio.run(p.decide("sys", "mem", "world"))
        except llm.LLMProviderError as e:
            assert "JSON" in str(e) or "json" in str(e)
        else:
            raise AssertionError("expected LLMProviderError")


def test_ollama_decide_missing_action_raises() -> None:
    """Backend returned JSON without 'action' field — provider error."""
    import asyncio
    llm = _import_or_skip()

    fake_resp = _ollama_response({"response": json.dumps({"params": {}})})

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def post(self, *_: Any, **__: Any) -> Any:
            return fake_resp

    with patch("cosmergon_pet.llm.ollama.httpx.AsyncClient", return_value=_Client()):
        p = llm.OllamaProvider(url="http://x", model="m")
        try:
            asyncio.run(p.decide("sys", "mem", "world"))
        except llm.LLMProviderError:
            pass
        else:
            raise AssertionError("expected LLMProviderError")


if __name__ == "__main__":
    test_factory_lists_known_providers()
    test_factory_unknown_provider_raises()
    test_ollama_provider_satisfies_protocol()
    test_ollama_url_normalisation()
    test_ollama_decide_happy_path()
    test_ollama_decide_malformed_json_raises_provider_error()
    test_ollama_decide_missing_action_raises()
    print("OK")
