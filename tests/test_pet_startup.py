"""Pet startup integration test — SDK lifecycle on real process start.

Covers the gap the earlier installer-runtime tests left open: verifying
that `run_pet()` actually opens the SDK HTTP client before issuing
requests. The bug (cosmergon-pet#1 third layer) was that `run_pet()` was
using the `CosmergonAgent` without `async with agent:`, so every
`_request()` raised `RuntimeError("Agent not connected. Call run() or
use async with.")` from `agent.py`. That exception surfaced on the
display as `! state: Agent not co` on every info screen.

Two checks:

1. **Static lint** — the `run_pet()` function source must contain
   `async with agent`. Cheap, fast, catches regressions instantly.
2. **Async integration** — exercise the SDK lifecycle the exact way
   `run_pet()` does. Without `async with`, `_prime_state()` raises the
   pre-flight RuntimeError; with it, the SDK reaches network code and
   fails on the unreachable base URL instead. The former is the bug
   signature we're guarding against; the latter is the expected
   backend-unreachable path and confirms the lifecycle is open.

Run standalone:  `python3 tests/test_pet_startup.py`
Or via pytest:   `pytest tests/test_pet_startup.py -v`
"""

from __future__ import annotations

import asyncio
import inspect
import sys

# The pre-flight error signature. If this string appears in an exception
# raised from a pre-open SDK call, the HTTP client was never initialised.
BUG_SIGNATURE = "Call run() or use async with"


def test_run_pet_uses_async_with_agent() -> None:
    """run_pet() must open the SDK HTTP client via `async with agent:`."""
    from cosmergon_pet.face import run_pet

    src = inspect.getsource(run_pet)
    assert "async with agent" in src, (
        "run_pet() is not opening the SDK HTTP client. Without `async with "
        "agent:` every _request() call raises RuntimeError and the Pet shows "
        "`! state: Agent not co` on every screen — see cosmergon-pet#1."
    )


def test_poll_state_mirrors_state_into_sdk() -> None:
    """`_poll_state` must write the fetched GameState into `agent._state`.

    Diagnosed 2026-05-04: Pet's custom polling loop filled `ps.game_state`
    but left `agent._state` at None, so the LLM-Decider (which reads
    `agent.state` via SDK property) saw an empty state and built only the
    `wait` schema-choice. Comet-hand chose 100% wait for ~33h despite
    /state returning 200 OK — same llama3.2:3b chose 67% growth as an NPC.

    Static check: source contains `agent._state =` inside `_poll_state`.
    Cheap, fast, catches regressions instantly. Full integration would
    require mocking httpx + asyncio; the source check covers the same
    contract.
    """
    from cosmergon_pet.face import _poll_state

    src = inspect.getsource(_poll_state)
    assert "agent._state = state" in src, (
        "`_poll_state` is not mirroring the fetched state into the SDK's "
        "`_state` slot. Without this, `agent.state` (read by the "
        "LLM-Decider) remains None and the only schema-choice the LLM "
        "ever sees is `wait`."
    )


def test_sdk_client_is_none_before_open() -> None:
    """Canary: a freshly constructed CosmergonAgent has no HTTP client.

    Without this invariant the bug signature would never appear — so the
    fix wouldn't be guarding against anything. Run against the real SDK
    on every CI run.
    """
    try:
        from cosmergon_agent import CosmergonAgent
    except ImportError:
        import pytest  # type: ignore[import-not-found]

        pytest.skip("cosmergon_agent not importable")

    agent = CosmergonAgent(
        api_key="fake-key-for-testing",
        base_url="http://127.0.0.1:1",
    )
    assert agent._client is None, (
        "CosmergonAgent starts with _client != None — the bug no longer has "
        "a pre-flight guard. Re-verify the rest of this test suite."
    )


def test_request_on_unopened_agent_raises_bug_signature() -> None:
    """Canary: calling `_request` before open raises the pre-flight error.

    Reproduces the exact path `_prime_state()` hit on Lashee's Pi before
    the fix. If this ever stops reproducing, the bug has moved or the
    failure mode has changed — either way the fix-regression check below
    stops meaning what it says.
    """
    try:
        from cosmergon_agent import CosmergonAgent
    except ImportError:
        import pytest  # type: ignore[import-not-found]

        pytest.skip("cosmergon_agent not importable")

    async def _probe() -> str:
        agent = CosmergonAgent(
            api_key="fake-key-for-testing",
            base_url="http://127.0.0.1:1",
        )
        try:
            await agent._request("GET", "/api/v1/agents/")
        except RuntimeError as err:
            return str(err)
        return ""

    err = asyncio.run(_probe())
    assert BUG_SIGNATURE in err, (
        f"Pre-flight RuntimeError no longer raised by _request on an unopened agent. Got: {err!r}"
    )


def test_request_on_opened_client_skips_bug_signature() -> None:
    """Fix regression: once `_client` is set, no pre-flight RuntimeError.

    Opens the client the same way `async with agent:` does internally
    (via `_create_client`), then fires a request at an unreachable URL.
    The expected outcome is a network-level error from httpx — anything
    except the pre-flight RuntimeError is fine here; that's the whole
    point of the fix.
    """
    try:
        from cosmergon_agent import CosmergonAgent
    except ImportError:
        import pytest  # type: ignore[import-not-found]

        pytest.skip("cosmergon_agent not importable")

    async def _probe() -> str:
        agent = CosmergonAgent(
            api_key="fake-key-for-testing",
            base_url="http://127.0.0.1:1",
            max_retries=0,  # fail fast on unreachable URL
        )
        agent._client = agent._create_client()
        try:
            try:
                await agent._request("GET", "/api/v1/agents/")
            except Exception as err:
                return f"{type(err).__name__}: {err}"
            return ""
        finally:
            if agent._client is not None:
                await agent._client.aclose()

    err = asyncio.run(_probe())
    assert BUG_SIGNATURE not in err, (
        f"Pre-flight RuntimeError still raised with `_client` set — the "
        f"fix path is broken. Got: {err!r}"
    )


# --- Standalone runner ------------------------------------------------------


def _main() -> int:
    failures: list[str] = []

    try:
        test_run_pet_uses_async_with_agent()
        print("PASS  run_pet() uses `async with agent:`")
    except AssertionError as e:
        print("FAIL  async_with check:", e)
        failures.append("async_with_lint")

    try:
        import cosmergon_agent  # noqa: F401

        import cosmergon_pet  # noqa: F401

        checks = (
            ("SDK client is None before open (invariant)", test_sdk_client_is_none_before_open),
            (
                "pre-flight RuntimeError reproduces (canary)",
                test_request_on_unopened_agent_raises_bug_signature,
            ),
            (
                "fix keeps pre-flight RuntimeError away",
                test_request_on_opened_client_skips_bug_signature,
            ),
        )
        for name, fn in checks:
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                print(f"FAIL  {name}:", str(e)[:300])
                failures.append(name)
    except ImportError:
        print("SKIP  cosmergon_pet / cosmergon_agent not importable")

    if failures:
        print(f"\n{len(failures)} failure(s): {failures}")
        return 1
    print("\nAll startup tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
