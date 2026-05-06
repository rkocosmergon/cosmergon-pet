# Diagnostic Tools — Pet LLM Decision Path

Tools for diagnosing Pet-LLM behavior **without** cobot-live A/B-hopping.
S163 A.2 Methoden-Pflicht (cos20 TODO.md): never iterate live with three
hypotheses in parallel. Single-hypothesis lab work first, cobot-live only
as final validation.

## 1. Per-Decision JSONL Dump (live cobot)

Activate by setting an env var on the Pet service. Each decision writes
two JSONL entries to the same file:

* `phase: "input"` — system_prompt, memory, world, JSON-Schema
* `phase: "outcome"` — action, params (redacted), raw_response, validation
  outcome (`parsed`/`disallowed`/`off_list`/`wait`/`agent_act_ok`/
  `agent_act_fail`/`provider_error`), decided_in_seconds

```
# /etc/systemd/system/cosmergon-pet.service.d/dump.conf
[Service]
Environment=COSMERGON_PET_DECISION_DUMP_PATH=/tmp/pet-dump.jsonl
```

```
sudo systemctl daemon-reload && sudo systemctl restart cosmergon-pet
tail -f /tmp/pet-dump.jsonl
```

Off by default — no file I/O when the env var is unset. Token-free by
construction (sensitive params are redacted with `_redact_params`).
Failures are logged at WARNING and swallowed; the decision loop is
never affected.

The legacy env var `COSMERGON_PET_PROMPT_DUMP_PATH` keeps working —
it's the same code path under the older name. New deployments should
use `COSMERGON_PET_DECISION_DUMP_PATH` for clarity.

## 2. Local Experiment Harness (no cobot needed)

Reproduces Pet's prompt-builder + JSON-Schema constraints against an
Ollama instance N times for a fixed mock state. Output is the same
JSONL format as the live dump — same downstream tooling works on
either source.

Setup:

```
# Clone the agent SDK alongside cosmergon-pet
git clone git@github.com:rkocosmergon/cosmergon-agent.git ~/projekte/cosmergon-agent

# Run via PYTHONPATH (works on PEP 668 systems without venv)
PYTHONPATH="$HOME/projekte/cosmergon-pet/src:$HOME/projekte/cosmergon-agent/src" \
    python ~/projekte/cosmergon-pet/scripts/local-experiment.py --runs 10
```

Defaults match Comet-hand at session-162-imac.md L1-Empirie 18:50 UTC:
`persona=scientist`, `balance=1.67M E`, single Tier-2 oscillator field
with 3 cells, no buyable market listings.

Override:

```
python scripts/local-experiment.py \
    --runs 20 \
    --persona warrior \
    --balance 50000 \
    --model qwen2.5:7b \
    --ollama-url http://mac-mini.local:11434 \
    --output /tmp/exp-warrior.jsonl
```

Output: stderr summary (action distribution, validation outcome,
latency stats) plus `/tmp/local-experiment-<unix-ts>.jsonl` with one
entry per run.

## 3. Workflow per Hypothesis

S163-A.2 method:

1. **Decision-path transparency.** Run §2 with current Pet-code and
   record the baseline distribution.
2. **One change at a time.** Pick exactly one hypothesis (choice
   ordering, balance threshold, model swap, prompt wording, removal of
   one example, etc.). Edit the relevant Pet source.
3. **Local re-run.** Same `--runs` and `--persona` as the baseline.
   Compare distributions head-to-head.
4. **Cobot-deploy only if local change shows directional improvement.**
   Live-cobot is the final validation step — never the search step.
5. **Pre-registered prediction before the run.** Write the expected
   distribution into the relevant session note so the result is
   falsifiable. Cf. memory `feedback_pre_registered_predictions`.

Anti-pattern (rejected in S160 + S162): three hypotheses live on cobot
in parallel, each iteration ~30 minutes between deploys, after 5 hours
no causal claim is possible because the samples are interleaved.

## 4. Provenance

* `_maybe_dump_prompt` — S161 PR #10/#11 (prompt-dump tool, removed
  briefly post-diagnosis, restored as part of the decision-loop in
  S163 A.2).
* `_maybe_dump_decision_outcome` — S163 A.2, this commit.
* `OllamaProvider.last_raw_response` — S163 A.2, this commit. Snapshot
  of the verbatim model output before parse, populated even on
  parse failure for debugging.
* `scripts/local-experiment.py` — S163 A.2, this commit.

Re-evaluate when: a new provider (e.g. local SLM, OpenAI) is added.
The diagnostic protocol is provider-agnostic but the
`last_raw_response` attribute must be implemented on each provider
class for the dump's `raw_response` field to populate.
