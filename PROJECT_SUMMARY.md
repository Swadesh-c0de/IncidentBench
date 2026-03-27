# IncidentBench — Project Summary

## One-Liner

IncidentBench is a deterministic evaluation environment that tests whether autonomous agents can safely triage and resolve realistic SaaS production incidents.

## Motivation

On-call incident response is one of the most consequential tasks in modern software operations. It demands evidence-based reasoning under pressure, correct ownership routing, and safe decision-making — all properties that are difficult to evaluate with free-form benchmarks. IncidentBench creates a structured sandbox where these capabilities can be measured objectively, without relying on subjective grading or LLM judges.

## What Ships in This Package

- **15 hand-crafted synthetic scenarios** across three difficulty tiers (5 easy, 5 medium, 5 hard).
- **Typed Pydantic models** for actions, observations, and state.
- **Deterministic environment API** — `reset()`, `step(action)`, `state()` — with zero randomness.
- **Rubric-based grader** that outputs a validator-safe score in `(0.0, 1.0)`.
- **Dense per-step reward** providing partial-progress signal throughout each episode.
- **FastAPI server** for local and containerized deployment.
- **Baseline `inference.py`** using the OpenAI client with required env vars.
- **Dockerfile** and comprehensive test suite.

## Quick Evaluation Path (2–3 minutes)

1. Start the API (`uvicorn server.app:app`) and open `/docs`.
2. Call `POST /reset` with `easy_auth_token_expiry`.
3. Call `POST /step` with an inspect action, then `GET /state`.
4. Call `POST /grade` — verify the returned score is between 0 and 1.
5. Run `python3 -m pytest` for deterministic test coverage.

## Alignment with Judging Criteria

| Criterion | How IncidentBench Addresses It |
|---|---|
| Real-world utility | Models on-call incident response — a task performed thousands of times daily across the industry |
| Task & grader quality | Explicit objectives per scenario, fully deterministic grading, meaningful difficulty progression |
| Environment design | Stateful evidence unlocking, safety-aware transitions, shaped reward with coverage milestones |
| Spec compliance | Typed models, OpenEnv-style manifest, deployable API + Docker, working inference script |

## Key Files

| File | Purpose |
|---|---|
| `server/environment.py` | Core environment dynamics |
| `grader.py` | Deterministic scoring rubric |
| `openenv.yaml` | OpenEnv manifest |
| `inference.py` | Baseline agent runner |
| `tests/` | Comprehensive test suite |
