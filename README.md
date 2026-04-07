---
title: IncidentBench
emoji: "🔥"
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# IncidentBench

**IncidentBench** is a fully deterministic, offline evaluation environment that measures how well an autonomous agent can triage and resolve simulated production incidents at a fictional SaaS company. Every episode drops the agent into a live incident with partial visibility — it must gather forensic evidence, classify the severity, route to the right on-call team, pinpoint the root cause, prescribe a mitigation, and close the incident without taking unsafe shortcuts.

For a fast review:

1. Start with `PROJECT_SUMMARY.md` (high-level overview for evaluators).
2. Continue with this README (setup, interfaces, scoring mechanics).
3. Refer to `TECHNICAL_NOTES.md` (deep dive into determinism, grading, and reward logic).

## Why This Environment Matters

Most agent evaluation suites focus on general reasoning or toy games. IncidentBench is narrowly focused on **operational reliability** — can an agent follow a structured, evidence-driven workflow under uncertainty and ambiguity without introducing risk?

- **Grounded in a real domain:** production on-call incident response.
- **Fully offline:** zero network dependencies during environment execution.
- **Deterministic grading:** no LLM-as-judge, no stochastic evaluation.
- **Safety-aware:** premature or reckless resolutions are heavily penalized.

## Hackathon Alignment

- **Real-world utility:** incident triage and runbook-driven remediation.
- **OpenEnv-compatible API:** typed `Action`, `Observation`, `StepResult` models via Pydantic, plus `reset()`, `step()`, `state()`.
- **Three difficulty tiers** with 15 scenarios total and deterministic graders.
- **Dense trajectory reward** + independent final rubric-based score.
- **Containerized deployment:** FastAPI server, Dockerfile, and baseline inference script.

## How It Works

### Execution Flow

1. A scenario JSON file defines hidden ground-truth values and an evidence dependency graph.
2. `IncidentBenchEnvironment` loads scenarios and initializes episode state.
3. `reset()` returns a partial initial observation (ground truth is hidden).
4. `step(action)` applies a deterministic state transition and computes per-step reward.
5. `grade()` runs a final rubric scorer and returns a validator-safe score strictly inside `(0, 1)`.
6. FastAPI wraps the environment through `/reset`, `/step`, `/state`, `/grade`.

### Key Source Files

| File | Purpose |
|---|---|
| `models.py` | Pydantic models, enums, and API payload types |
| `server/environment.py` | Core environment dynamics and reward shaping |
| `grader.py` | Deterministic rubric-based final scorer |
| `server/app.py` | FastAPI endpoint layer |
| `inference.py` | OpenAI-client baseline agent runner |

## Scenario Catalog

15 fully synthetic scenarios spanning three difficulty tiers.

| Tier | Count | Typical Steps | What Makes It Hard |
|---|---:|---:|---|
| Easy | 5 | 4–8 | One dominant root cause, minimal distractions |
| Medium | 5 | 6–10 | At least one plausible red herring; cross-source evidence synthesis required |
| Hard | 5 | 8–12 | Conflicting signals, multiple false leads, shallow closures punished aggressively |

Services covered: `auth`, `checkout`, `payments`, `email`, `search`, `notifications`, `platform`.

## Action Space

| Field | Type | Required | Notes |
|---|---|---|---|
| `action_type` | enum | yes | See list below |
| `target` | string | inspect actions only | Evidence ID to inspect |
| `content` | string | setter/submit/note actions | Free text or enum-like value |

Available action types:

- `inspect_alert`, `inspect_log`, `inspect_runbook`, `inspect_timeline_note`
- `set_severity` (`SEV-1`, `SEV-2`, `SEV-3`)
- `assign_team`
- `submit_root_cause`, `submit_mitigation`
- `add_note`
- `resolve_incident`

## Observation Space

| Category | What the Agent Sees |
|---|---|
| Incident context | Scenario ID, title, difficulty, service, incident summary |
| Visible evidence | Unlocked alerts, logs, runbooks, and timeline notes |
| Agent working memory | Accumulated known facts + action history summary |
| Decision state | Currently selected severity, team, root cause, mitigation |
| Episode progress | Steps taken/remaining, done flag, result of most recent action |

Ground truth values are **never** exposed in observations.

## Reward Design (Per-Step Signal)

Reward is a dense per-step signal, separate from the final grader score.

**Positive signals:**
- `+0.03` for first-time inspection of relevant evidence
- `+0.01` for first-time inspection of neutral evidence
- `+0.015 / +0.02` for evidence coverage milestones (50%, 100%)
- `+0.10` for correct severity or correct team
- `+0.20` for correct root cause, correct mitigation, or safe resolution

**Negative signals:**
- `-0.005` living penalty each step
- `-0.02` for re-inspecting relevant evidence already seen
- `-0.03` for repeated irrelevant or invalid inspections
- `-0.20` baseline penalty for unsafe resolution (with additional deductions for wrong root cause, low evidence coverage, or repetitive looping)

## Grading (Final Rubric Score)

The grader in `grader.py` is completely deterministic:

| Component | Weight |
|---|---:|
| Severity correctness | 0.15 |
| Owner team correctness | 0.15 |
| Root cause correctness | 0.30 |
| Mitigation correctness | 0.25 |
| Evidence coverage | 0.10 |
| Safe resolution behavior | 0.05 |

Text matching uses deterministic normalization (lowercasing, punctuation removal, light stemming, controlled synonyms, token overlap, and bounded fuzzy thresholds). Negated statements that conflict with the expected answer are explicitly rejected.

The published score is epsilon-clamped into `(0, 1)` so that strict validators never see exact boundary values.

## Example Episode

Scenario: `easy_auth_token_expiry`

```
1. inspect_alert  → ea1_alert_401_spike
2. inspect_log    → ea1_log_jwt_expired
3. inspect_runbook → ea1_runbook_key_rotation
4. set_severity   → SEV-2
5. assign_team    → auth-oncall
6. submit_root_cause → expired auth signing key
7. submit_mitigation → rotate signing key and restart issuer
8. resolve_incident
```

Expected outcome: `resolved_safely`, score ≈ `1.0`.

## API Reference

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/reset` | Start or restart an episode |
| `POST` | `/step` | Submit an action |
| `GET` | `/state` | Inspect internal episode state |
| `GET` | `/tasks` | List task tiers |
| `GET` | `/scenarios` | List all scenario IDs |
| `POST` | `/grade` | Score current episode |
| `POST` | `/score` | Alias for `/grade` |

Interactive docs: `http://127.0.0.1:8000/docs`

> **Tip for Swagger UI:** Replace the default `"scenario_id": "string"` placeholder in `/reset` with a real ID. Use `GET /scenarios` to find valid ones.

## Local Setup

Requires Python `3.11+`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e '.[dev]'
python3 -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

If editable installs are blocked by your Python configuration:

```bash
python3 -m pip install '.[dev]'
```

Verify:

```bash
curl http://127.0.0.1:8000/health
```

## Tests & Smoke Checks

```bash
python3 -m pytest
python3 scripts/smoke_test.py
python3 scripts/export_task_summary.py
```

## Running Baseline Inference

`inference.py` uses the OpenAI Python client and iterates over all 15 scenarios.

**Required environment variables:**

- `API_BASE_URL`
- `MODEL_NAME`
- `HF_TOKEN`

**Optional:**

- `API_KEY` / `OPENAI_API_KEY`
- `INCIDENTBENCH_BASE_URL`
- `MAX_STEPS`, `TEMPERATURE`, `MAX_TOKENS`, `RESULT_PATH`

```bash
python3 inference.py
```

**Fallback behavior:**

- If `INCIDENTBENCH_BASE_URL` is missing or unreachable, the script uses a local in-process environment.
- If no API credentials are found, it falls back to a deterministic planner-only baseline (no LLM calls) and still exits cleanly.
- When credentials are present, the script initializes the OpenAI client and logs `inference_mode: "openai_client"`.
- Stdout emits strict `[START]`, `[STEP]`, and `[END]` records for validator parsing.

**Recommended invocation:**

```bash
mkdir -p artifacts
export INCIDENTBENCH_BASE_URL="https://<your-space>.hf.space"
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="meta-llama/Llama-3.1-8B-Instruct"
export HF_TOKEN="<your_token>"
export RESULT_PATH="artifacts/inference_live_$(date +%Y%m%d_%H%M%S).json"
python3 inference.py | tee artifacts/inference_live_stdout.txt
```

**Output format:**

- `[START] task=...` — one line per scenario
- `[STEP] step=... reward=...` — per action within the episode
- `[END] task=... score=... steps=...` — final score per scenario
- JSON summary file (default: `baseline_results.json`)

## Docker

Build:

```bash
docker build -t incidentbench:latest .
```

Run:

```bash
docker run --rm -p 7860:7860 incidentbench:latest
```

Verify:

- `http://127.0.0.1:7860/health`
- `http://127.0.0.1:7860/docs`

## Project Structure

```text
incidentbench/
├── PROJECT_SUMMARY.md
├── TECHNICAL_NOTES.md
├── README.md
├── openenv.yaml
├── inference.py
├── models.py
├── grader.py
├── client.py
├── scenarios/
├── server/
├── tests/
└── scripts/
```

## Pre-Submission Checklist

- [x] All 15 scenarios load (5 easy / 5 medium / 5 hard).
- [x] `python3 -m pytest` passes.
- [x] `scripts/smoke_test.py` resolves a scenario and produces a valid grade.
- [x] `/health`, `/reset`, `/step`, `/state`, `/grade` are functional via `/docs`.
- [x] `inference.py` runs with required env vars and writes a score summary JSON.
- [x] Docker image builds and serves `/health`.
- [x] `openenv.yaml` and implementation behavior are aligned.

## Known Limitations

- Single in-memory episode per API instance (no concurrent sessions).
- Text matching relies on deterministic heuristics with handcrafted synonym mappings.

## Possible Extensions

- Multi-session API with explicit episode identifiers.
- Escalation workflow simulation (handoffs, approvals, cross-team coordination).
- Adversarial scenario generation for anti-gaming stress testing.
