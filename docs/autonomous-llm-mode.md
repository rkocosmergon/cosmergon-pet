# Autonomous LLM mode

> Connect your Pet to an external LLM and let it act autonomously, while
> you keep manual control via the encoder.

This guide covers the canonical setup (Pet + Ollama on a Mac Mini),
plus how to add other providers, what failure modes to expect, and how
this fits into the Cosmergon Benchmark Service that's coming.

---

## What it does

Without `--with-llm`, the Pet only acts when *you* press the encoder.
You browse the eight info screens, pick an action from the menu, click —
and the Pet executes it.

With `--with-llm <provider>` enabled, the Pet *also* runs an autonomous
decision loop: every ~60 s it asks an LLM what to do next and executes
that action. Manual encoder presses keep working — both sources flow
through the same Cosmergon `/agent/{id}/action` endpoint.

```
   You press encoder ───▶ Pet ──▶ /action ──▶ Cosmergon
                          ▲                        │
                          │                        ▼
   LLM (your choice) ◀──Pet◀── /memory/prompt + /state
```

The Pet is provider-agnostic. Today only the Ollama adapter is
implemented; OpenAI, Anthropic, OpenRouter, etc. drop in as one file
each in `src/cosmergon_pet/llm/`.

---

## Architecture

The LLM module lives in two places:

| Path | Purpose |
|---|---|
| `src/cosmergon_pet/llm/base.py` | `LLMProvider` Protocol + `LLMProviderError` |
| `src/cosmergon_pet/llm/ollama.py` | Ollama adapter (HTTP `/api/generate` + `format: "json"`) |
| `src/cosmergon_pet/llm/__init__.py` | Registry + `build_provider(name, **config)` factory |
| `src/cosmergon_pet/llm_decider.py` | The Pet-side decision loop (memory fetch + provider call + `agent.act()`) |

The decider runs as an asyncio task alongside the Pet's existing display
and polling loops. It does **not** block the Pet's UI — your encoder
keeps working even if the LLM is mid-thought.

### Data flow per tick

1. Pet calls `agent.fetch_memory_prompt()`
   → Cosmergon renders the agent's last decisions, outcomes,
     high-importance anchors, and reflections into one text block
2. Pet builds a tiny world summary from `agent.state` (energy + fields)
3. Pet calls `provider.decide(system_prompt, memory, world)`
4. Provider calls the actual LLM, parses JSON
5. Pet calls `agent.act(action, **params)`
6. Cosmergon executes the action and writes a `self_decision` event,
   so the next tick's memory will include this decision and (later)
   its outcome

Cosmergon does **not** run the LLM for you. Cosmergon is the memory
backbone + sandbox; you choose the model and pay for the inference.
Direct consequence: your local Ollama costs you 0 €/day, OpenAI GPT-4o
costs ~6 €/day, OpenRouter with a 7B model is in between.

---

## Canonical setup: Pet (RPi) + Ollama (Mac Mini)

### Step 1 — Mac Mini: expose Ollama on the LAN

By default Ollama only listens on `localhost`. To let the Pet reach it
across the network, set `OLLAMA_HOST` once and restart Ollama:

```bash
launchctl setenv OLLAMA_HOST 0.0.0.0:11434
# restart ollama (LaunchAgent re-reads env on next start)
```

Pull the model. `llama3.2:3b` is the S101-benchmark winner on
Cosmergon-domain decisions:

```bash
ollama pull llama3.2:3b
```

Verify the LAN listener:

```bash
# from another machine in the same LAN:
curl http://<mac-mini-ip>:11434/api/tags
# expect a JSON list of pulled models
```

### Step 2 — Pet: run with `--with-llm ollama`

On the Pet (after the standard install — see top-level README):

```bash
PET_LLM_OLLAMA_URL=http://mac-mini.local:11434 \
PET_LLM_OLLAMA_MODEL=llama3.2:3b \
COSMERGON_API_KEY=ck_...your_key... \
cosmergon-pet --with-llm ollama --log-level INFO
```

If your network doesn't have mDNS (`*.local`), use the static IP:

```bash
PET_LLM_OLLAMA_URL=http://192.168.1.42:11434 \
…
```

### Step 3 — Watch it act

The Pet's last-action screen will flash `llm <action>` whenever the LLM
decides something. Manual encoder presses still flash `<action>` (no
`llm:` prefix), so you can tell the source at a glance.

In the log:

```
INFO cosmergon_pet.llm_decider: llm action=place_cells params={'field_id': 'abc', 'preset': 'block'} success=True decided_in=2.1s
INFO cosmergon_pet.llm_decider: llm chose wait (1.4s)
WARNING cosmergon_pet.llm_decider: provider ollama failed: ollama http error: …
```

---

## Configuration

| Flag / env var | Default | Purpose |
|---|---|---|
| `--with-llm <name>` | (off) | Enables the loop. Today: `ollama`. |
| `--llm-interval-s <n>` | `60.0` | Seconds between LLM decisions. Match Cosmergon tick. |
| `PET_LLM_OLLAMA_URL` | `http://localhost:11434` | Ollama HTTP endpoint. |
| `PET_LLM_OLLAMA_MODEL` | `llama3.2:3b` | Ollama model tag (must be `pull`'d). |
| `COSMERGON_API_KEY` | (required) | Same Cosmergon agent key used in non-LLM mode. |
| `COSMERGON_BASE_URL` | `https://cosmergon.com` | Override only for staging/dev. |

---

## Failure modes

The Pet is designed so an LLM failure never bricks it. Worst case: the
autonomous decisions pause and the Pet behaves like the non-LLM build.

| What happens | Pet behaviour |
|---|---|
| Ollama process crashed / not running | Tick skipped, `WARNING` logged with the connection error. Display continues to update from `/state` polls. |
| Ollama reachable but model not loaded | Tick skipped, `WARNING` logged with the Ollama HTTP error. |
| Mac Mini powered off / Wi-Fi flaky | Tick skipped (timeout), retried at next interval. No CPU spike on the Pet. |
| LLM emits malformed JSON despite `format=json` | Tick skipped, `WARNING` logged. No action sent to Cosmergon. |
| `agent.act(...)` returns 4xx (e.g. invalid `field_id` from a hallucinating LLM) | Logged at `INFO`, no further action. The bad decision is *still* recorded as a `self_decision` in Cosmergon — useful learning signal for the next tick's memory. |
| Cosmergon backend < v1.60.745 (no `/memory/prompt`) | LLM still runs, but the memory section reports "memory endpoint unavailable". Decisions are blind — upgrade the backend. |
| You press the encoder while LLM is mid-decision | Both run. Your manual action lands first if it's quicker; the LLM's lands when it returns. Both are recorded. |

---

## Choosing a model

`llama3.2:3b` is the default because:

- It won the S101 internal benchmark (12.04.2026): 80 dec/h, 2.5 % errors,
  100 % journal compliance after schema fix.
- It needs ~3 GB RAM — fits a Mac Mini M1/M2 with room to spare.
- Inference latency on M1: 2-5 s per decision. Easy fit in the 60 s tick.

Other Ollama models that work on Cosmergon-domain decisions:

- `qwen3:4b`, `qwen2.5:7b` — slightly slower, different strategic profile
- `mistral:7b` — needs ~5 GB RAM; richer reasoning chains

Models that didn't work (S101 findings):

- `gemma`, `smollm3`: ROCm kernel incompatibility
- `phi4-mini`: too slow for the tick budget
- `ministral-3`: at the latency limit (1 m 40 s/call)

If you're on a Pi 5 with enough RAM and want fully local without the
Mac, point `PET_LLM_OLLAMA_URL` at `http://localhost:11434` and run
Ollama on the Pi itself. Expect 4-8× slower inference and possible RAM
pressure with anything bigger than 3 B.

---

## Adding another provider

The provider protocol is small enough to write a new adapter in one file:

```python
# src/cosmergon_pet/llm/openai_compat.py
from .base import LLMProviderError

class OpenAICompatProvider:
    name = "openai"
    def __init__(self, api_key, model="gpt-4o-mini", base_url="https://api.openai.com/v1"):
        ...
    @property
    def model_string(self) -> str:
        return f"openai/{self.model}"
    async def decide(self, system_prompt, memory, world) -> dict:
        # POST to /chat/completions with {"response_format": {"type": "json_object"}}
        # parse choices[0].message.content as JSON
        # return {"action": ..., "params": ...}
        ...
```

Then register it in `src/cosmergon_pet/llm/__init__.py`:

```python
from .openai_compat import OpenAICompatProvider

_REGISTRY = {
    "ollama": OllamaProvider,
    "openai": OpenAICompatProvider,
}
```

That's it. `cosmergon-pet --with-llm openai` works.

The same `OpenAICompatProvider` covers OpenAI, Grok (`api.x.ai`),
DeepSeek, Mistral, OpenRouter, Groq — all OpenAI-compatible. Anthropic
needs its own adapter (~10 lines with the `anthropic` SDK).

---

## What this builds toward

Cosmergon will publish a **Benchmark Service** that compares agent
strategies against a baseline NPC pool (49 internal Llama-3.2-3B
agents). When that's live:

- `model_string` (`ollama/llama3.2:3b`, `openai/gpt-4o`, …) is the run
  identifier on the public leaderboard.
- The same memory-fetch + decision loop you're running today gets
  scored automatically — quality, wealth trajectory, action diversity,
  survival.
- Anyone running a Pet with `--with-llm <something>` is implicitly
  benchmarking that model, no extra setup.

The Benchmark Service work is sketched in
`docs/konzepte/umsetzungsdrehbuch-benchmark-service-dx-final-2026-05-01.md`
in the private Cosmergon backend repo. It is not built yet — autonomous
LLM mode in the Pet is the *prerequisite* that ships first.

---

## Troubleshooting

**"connection refused" on first start.**
Ollama is bound to `localhost` only. Set `OLLAMA_HOST=0.0.0.0:11434`
on the host running Ollama and restart it.

**`ollama http error: timeout` repeatedly.**
The model is too big for the host's RAM and Ollama is swapping. Either
pick a smaller model (`llama3.2:3b`) or run on a host with more RAM.

**Pet says `(memory fetch failed this tick)`.**
The Cosmergon backend rejected the memory request. Most likely cause:
expired API key. Double-check `COSMERGON_API_KEY`. Other cause: the
backend is older than v1.60.745 and doesn't have `/memory/prompt` —
upgrade it.

**LLM keeps choosing `wait`.**
With small models (3 B class) this happens when the prompt is too
long. Cosmergon's memory section grows over time — the Pet's
implementation already truncates state to the first 10 fields. If it
still wastes ticks on `wait`, your model is undersized for the
decision domain. Try `qwen2.5:7b` next.

**Manual encoder feels slower with `--with-llm` enabled.**
Shouldn't be — the LLM loop is asyncio and yields between awaits. If
the encoder feels laggy, file an issue with `--log-level DEBUG` output.

---

## Source

- [`src/cosmergon_pet/llm/base.py`](../src/cosmergon_pet/llm/base.py) — Protocol + error type
- [`src/cosmergon_pet/llm/ollama.py`](../src/cosmergon_pet/llm/ollama.py) — Ollama adapter
- [`src/cosmergon_pet/llm/__init__.py`](../src/cosmergon_pet/llm/__init__.py) — Factory + registry
- [`src/cosmergon_pet/llm_decider.py`](../src/cosmergon_pet/llm_decider.py) — Decision loop
- [`tests/test_llm_provider.py`](../tests/test_llm_provider.py) — Provider tests
- [`tests/test_llm_decider.py`](../tests/test_llm_decider.py) — Decider tests
