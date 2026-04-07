# Technical Notes

## Reproducibility Guarantees

IncidentBench is engineered for bit-exact reproducibility across runs.

- Every scenario is a static JSON file under `scenarios/`. No procedural generation.
- State transitions and grading computations involve zero randomness.
- No outbound network requests occur during environment execution.
- Calling `reset(scenario_id=...)` with the same ID always produces an identical initial state.
- Evidence visibility is governed by deterministic unlock conditions (boolean combinations of previously inspected evidence IDs).

## How Grading Works

Grading is a **post-episode** computation, fully independent from the per-step reward signal.

### Rubric Weights

| Component | Weight |
|---|---:|
| Severity correctness | 0.15 |
| Owner team correctness | 0.15 |
| Root cause correctness | 0.30 |
| Mitigation correctness | 0.25 |
| Evidence coverage adequacy | 0.10 |
| Safe resolution behavior | 0.05 |

Each component evaluates to a value in `[0.0, 1.0]`. The weighted sum is then epsilon-clamped into the open interval `(0, 1)` to ensure strict validators never encounter exact boundary values.

### How Text Matching Works

Root cause and mitigation comparisons use a deterministic pipeline:

1. **Normalization:** lowercasing, punctuation removal
2. **Light stemming:** rule-based suffix stripping
3. **Synonym expansion:** controlled token-level mappings (e.g., "recycle" → "restart")
4. **Token overlap scoring:** precision, recall, and F1 against the reference answer
5. **Sequence similarity:** bounded `SequenceMatcher` ratio check
6. **Character trigram overlap:** Jaccard index over trigram sets

This design accepts reasonable paraphrases while remaining entirely deterministic — no model-based evaluation at any stage.

### Negation Handling

Submitted answers that explicitly negate key concepts from the reference answer (e.g., "this was **not** a clock skew issue") are rejected, **unless** the reference itself contains negation (e.g., "gateway did **not** reload new version").

## Reward Function Design

The per-step reward is a dense signal meant to guide learning. It is **not** used for final scoring.

### Positive Rewards

| Trigger | Reward |
|---|---|
| First-time inspection of relevant evidence | +0.03 |
| First-time inspection of neutral evidence | +0.01 |
| Evidence coverage hits 50% of required set | +0.015 |
| Full required evidence set covered | +0.02 |
| Correct severity assignment | +0.10 |
| Correct team assignment | +0.10 |
| Correct root cause submission | +0.20 |
| Correct mitigation submission | +0.20 |
| Safe final resolution | +0.20 |

### Negative Rewards

| Trigger | Penalty |
|---|---|
| Per-step living cost | −0.005 |
| Re-inspecting already-seen relevant evidence | −0.02 |
| Repeated irrelevant or invalid inspection | −0.03 |
| Unsafe or premature resolution (base) | −0.20 |
| Resolving with wrong root cause | additional −0.10 |
| Resolving with very low evidence coverage | additional −0.05 |
| Speculative root cause/mitigation (coverage < 34%) | −0.02 |
| Exact-duplicate action (same type + same content) | −0.01 |
| Three or more identical actions | −0.02 + message |

## Episode Termination Conditions

An episode ends when either:

- The agent calls `resolve_incident`, or
- The step budget is exhausted.

Step budgets scale by tier:

| Tier | Max Steps |
|---|---:|
| Easy | 8 |
| Medium | 10 |
| Hard | 12 |

The test suite enforces that every scenario has `max_steps >= len(required_evidence_ids) + 5`, ensuring agents always have room for inspect → classify → resolve without needing brittle shortcuts.

## Grader Robustness Measures

- Alias matching uses strictly deterministic normalization and bounded fuzzy thresholds.
- Negated statements conflicting with the candidate reference are explicitly blocked.
- Safe resolution credit requires **both** correctness across all fields **and** adequate evidence coverage — correct labels alone are insufficient.

## Test Suite Focus Areas

The test suite targets the critical paths that evaluators and validators rely on:

- Pydantic model and action validation
- Deterministic step behavior (same input → same output)
- Invalid action handling and graceful error responses
- Reward progression and penalty mechanics
- Grader bounds, alias matching, and paraphrase acceptance
- Scenario loading, integrity, and uniqueness constraints
- API endpoint contracts and grading flow
- Step-budget sufficiency for full resolution paths
