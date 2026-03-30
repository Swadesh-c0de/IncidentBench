from __future__ import annotations

import re
from difflib import SequenceMatcher
from statistics import mean
from typing import Iterable

from models import Difficulty, GraderResult, InternalStateSnapshot, Scenario, TaskSummary

GRADER_WEIGHTS: dict[str, float] = {
    "severity": 0.15,
    "owner_team": 0.15,
    "root_cause": 0.30,
    "mitigation": 0.25,
    "evidence_coverage": 0.10,
    "safe_resolution": 0.05,
}

STRICT_SCORE_EPSILON = 0.0001


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def clamp_open01(value: float, epsilon: float = STRICT_SCORE_EPSILON) -> float:
    return max(epsilon, min(1.0 - epsilon, value))


TOKEN_SYNONYMS: dict[str, str] = {
    "recycle": "restart",
    "redeploy": "restart",
    "reload": "restart",
    "bounce": "restart",
    "restore": "restart",
    "rollback": "rollback",
    "revert": "rollback",
    "backout": "rollback",
    "rotation": "rotate",
    "rotated": "rotate",
    "refresh": "rotate",
    "credentials": "credential",
    "secrets": "secret",
    "keys": "key",
    "misrouted": "misroute",
    "misrouting": "misroute",
    "timeouts": "timeout",
    "failed": "fail",
    "failing": "fail",
    "failures": "fail",
    "caused": "cause",
    "causing": "cause",
    "configuration": "config",
    "configs": "config",
    "deployment": "deploy",
    "deployments": "deploy",
    "workers": "worker",
    "pods": "pod",
    "host": "node",
    "machine": "node",
    "time": "clock",
    "drift": "skew",
    "check": "validation",
    "checks": "validation",
    "sync": "synchronize",
    "synchronization": "synchronize",
    "skewed": "skew",
    "stopped": "stop",
    "ntp": "time",
    "oauth": "auth",
    "smtp": "mail",
    "tls": "encryption",
    "sni": "hostname",
    "qps": "traffic",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "the",
    "to",
    "of",
    "for",
    "in",
    "on",
    "with",
    "after",
    "before",
    "from",
    "because",
    "by",
    "is",
    "was",
    "were",
    "be",
    "that",
    "this",
    "as",
    "it",
}

NEGATION_TOKENS = {"not", "no", "never", "without", "wrong", "incorrect"}


def _stem(token: str) -> str:
    if len(token) <= 4:
        return token
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def _tokenize(text: str | None) -> list[str]:
    if not text:
        return []
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    raw_tokens = [token for token in normalized.split() if token and token not in STOPWORDS]
    tokens: list[str] = []
    for token in raw_tokens:
        mapped = TOKEN_SYNONYMS.get(token, token)
        tokens.append(_stem(mapped))
    return tokens


def normalize_text(text: str | None) -> str:
    if not text:
        return ""
    return " ".join(_tokenize(text))


def _char_trigrams(text: str) -> set[str]:
    compact = text.replace(" ", "")
    if not compact:
        return set()
    if len(compact) < 3:
        return {compact}
    return {compact[index : index + 3] for index in range(len(compact) - 2)}


def _has_negation_conflict(submitted_tokens: list[str], candidate_tokens: set[str]) -> bool:
    if not submitted_tokens or not candidate_tokens:
        return False
    # Do not treat legitimate negative phrasing as conflict when the reference
    # itself contains negation (e.g., "did not reload").
    if candidate_tokens & NEGATION_TOKENS:
        return False
    for index, token in enumerate(submitted_tokens):
        if token in NEGATION_TOKENS:
            window = submitted_tokens[index + 1 : index + 4]
            if set(window) & candidate_tokens:
                return True
    return False


def text_matches(submitted: str | None, canonical: str, aliases: list[str] | None = None) -> bool:
    normalized_submitted = normalize_text(submitted)
    if not normalized_submitted:
        return False
    submitted_tokens_ordered = _tokenize(submitted)
    submitted_tokens = set(submitted_tokens_ordered)

    candidate_texts = [canonical, *(aliases or [])]
    normalized_candidates = [normalize_text(value) for value in candidate_texts if normalize_text(value)]
    if not normalized_candidates:
        return False

    for candidate in normalized_candidates:
        candidate_tokens = set(candidate.split())
        if _has_negation_conflict(submitted_tokens_ordered, candidate_tokens):
            continue

        if normalized_submitted == candidate:
            return True
        if normalized_submitted in candidate or candidate in normalized_submitted:
            return True

        if submitted_tokens and candidate_tokens:
            overlap = submitted_tokens & candidate_tokens
            recall = len(overlap) / len(candidate_tokens)
            precision = len(overlap) / len(submitted_tokens)
            if precision + recall == 0:
                f1 = 0.0
            else:
                f1 = 2 * precision * recall / (precision + recall)

            if recall >= 0.8:
                return True
            if f1 >= 0.72 and recall >= 0.65:
                return True

        overlap_count = len(submitted_tokens & candidate_tokens)
        overlap_gate = overlap_count >= 2 or len(candidate_tokens) <= 2

        sequence_ratio = SequenceMatcher(None, normalized_submitted, candidate).ratio()
        if overlap_gate and sequence_ratio >= 0.86:
            return True

        sub_trigrams = _char_trigrams(normalized_submitted)
        cand_trigrams = _char_trigrams(candidate)
        if sub_trigrams and cand_trigrams:
            trigram_overlap = len(sub_trigrams & cand_trigrams) / len(sub_trigrams | cand_trigrams)
            if overlap_gate and trigram_overlap >= 0.62:
                return True

    return False


def grade_episode(scenario: Scenario, state: InternalStateSnapshot) -> GraderResult:
    severity_component = 1.0 if state.selected_severity == scenario.true_severity.value else 0.0
    team_component = 1.0 if state.assigned_team == scenario.true_owner_team.value else 0.0

    root_cause_component = 1.0 if text_matches(
        state.submitted_root_cause,
        scenario.true_root_cause,
        scenario.true_root_cause_aliases,
    ) else 0.0

    mitigation_component = 1.0 if text_matches(
        state.submitted_mitigation,
        scenario.true_mitigation,
        scenario.true_mitigation_aliases,
    ) else 0.0

    required_ids = set(scenario.required_evidence_ids)
    inspected_ids = set(state.inspected_evidence_ids)
    if required_ids:
        evidence_component = len(required_ids & inspected_ids) / len(required_ids)
    else:
        evidence_component = 1.0

    has_required_fields = all(
        [
            severity_component == 1.0,
            team_component == 1.0,
            root_cause_component == 1.0,
            mitigation_component == 1.0,
        ]
    )
    enough_evidence = evidence_component >= 0.75
    safe_resolution_component = 1.0 if (
        state.done
        and state.resolution_attempted
        and not state.premature_resolution
        and has_required_fields
        and enough_evidence
    ) else 0.0

    components = {
        "severity": clamp01(severity_component),
        "owner_team": clamp01(team_component),
        "root_cause": clamp01(root_cause_component),
        "mitigation": clamp01(mitigation_component),
        "evidence_coverage": clamp01(evidence_component),
        "safe_resolution": clamp01(safe_resolution_component),
    }

    weighted_score = sum(components[key] * GRADER_WEIGHTS[key] for key in GRADER_WEIGHTS)
    weighted_score = clamp_open01(clamp01(weighted_score))

    details: list[str] = [
        f"Severity component: {components['severity']:.2f}",
        f"Owner team component: {components['owner_team']:.2f}",
        f"Root cause component: {components['root_cause']:.2f}",
        f"Mitigation component: {components['mitigation']:.2f}",
        f"Evidence coverage component: {components['evidence_coverage']:.2f}",
        f"Safe resolution component: {components['safe_resolution']:.2f}",
    ]

    return GraderResult(
        scenario_id=scenario.scenario_id,
        difficulty=scenario.difficulty,
        score=round(weighted_score, 4),
        components={key: round(value, 4) for key, value in components.items()},
        weights=GRADER_WEIGHTS,
        details=details,
    )


def aggregate_task_scores(results: Iterable[GraderResult]) -> list[TaskSummary]:
    by_difficulty: dict[Difficulty, list[float]] = {
        Difficulty.EASY: [],
        Difficulty.MEDIUM: [],
        Difficulty.HARD: [],
    }

    for result in results:
        by_difficulty[result.difficulty].append(result.score)

    summaries: list[TaskSummary] = []
    for difficulty, scores in by_difficulty.items():
        if not scores:
            continue
        summaries.append(
            TaskSummary(
                difficulty=difficulty,
                scenario_count=len(scores),
                average_score=round(mean(scores), 4),
                min_score=round(min(scores), 4),
                max_score=round(max(scores), 4),
            )
        )

    return summaries
