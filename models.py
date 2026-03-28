from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class EvidenceType(str, Enum):
    ALERT = "alert"
    LOG = "log"
    RUNBOOK = "runbook"
    TIMELINE = "timeline"


class ActionType(str, Enum):
    INSPECT_ALERT = "inspect_alert"
    INSPECT_LOG = "inspect_log"
    INSPECT_RUNBOOK = "inspect_runbook"
    INSPECT_TIMELINE_NOTE = "inspect_timeline_note"
    SET_SEVERITY = "set_severity"
    ASSIGN_TEAM = "assign_team"
    SUBMIT_ROOT_CAUSE = "submit_root_cause"
    SUBMIT_MITIGATION = "submit_mitigation"
    ADD_NOTE = "add_note"
    RESOLVE_INCIDENT = "resolve_incident"


class SeverityLevel(str, Enum):
    SEV_1 = "SEV-1"
    SEV_2 = "SEV-2"
    SEV_3 = "SEV-3"


class TeamName(str, Enum):
    AUTH_ONCALL = "auth-oncall"
    CHECKOUT_ONCALL = "checkout-oncall"
    PAYMENTS_ONCALL = "payments-oncall"
    EMAIL_OPS = "email-ops"
    SEARCH_INFRA = "search-infra"
    NOTIFICATIONS_OPS = "notifications-ops"
    ANALYTICS_DATA = "analytics-data"
    PLATFORM_OPS = "platform-ops"


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType
    target: Optional[str] = None
    content: Optional[str] = None

    @model_validator(mode="after")
    def validate_shape(self) -> "Action":
        inspect_actions = {
            ActionType.INSPECT_ALERT,
            ActionType.INSPECT_LOG,
            ActionType.INSPECT_RUNBOOK,
            ActionType.INSPECT_TIMELINE_NOTE,
        }
        content_actions = {
            ActionType.SET_SEVERITY,
            ActionType.ASSIGN_TEAM,
            ActionType.SUBMIT_ROOT_CAUSE,
            ActionType.SUBMIT_MITIGATION,
            ActionType.ADD_NOTE,
        }

        if self.action_type in inspect_actions and (not self.target or not self.target.strip()):
            raise ValueError(f"{self.action_type.value} requires non-empty target")

        if self.action_type in content_actions and (not self.content or not self.content.strip()):
            raise ValueError(f"{self.action_type.value} requires non-empty content")

        return self


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: EvidenceType
    title: str
    content: str
    relevant: bool
    tags: list[str] = Field(default_factory=list)
    unlock_condition: Optional[str] = None


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    title: str
    difficulty: Difficulty
    service: str
    incident_summary: str
    alerts: list[EvidenceItem]
    logs: list[EvidenceItem]
    runbook_snippets: list[EvidenceItem]
    timeline_notes: list[EvidenceItem] = Field(default_factory=list)
    red_herrings: list[str] = Field(default_factory=list)
    true_severity: SeverityLevel
    true_owner_team: TeamName
    true_root_cause: str
    true_root_cause_aliases: list[str] = Field(default_factory=list)
    true_mitigation: str
    true_mitigation_aliases: list[str] = Field(default_factory=list)
    required_evidence_ids: list[str]
    max_steps: int = Field(ge=3, le=30)
    initial_visible_evidence_ids: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)

    @property
    def all_evidence(self) -> list[EvidenceItem]:
        return [*self.alerts, *self.logs, *self.runbook_snippets, *self.timeline_notes]

    @property
    def evidence_map(self) -> dict[str, EvidenceItem]:
        return {item.id: item for item in self.all_evidence}


class PublicEvidence(BaseModel):
    id: str
    type: EvidenceType
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)


class Observation(BaseModel):
    scenario_id: str
    title: str
    difficulty: Difficulty
    service: str
    incident_summary: str
    visible_alerts: list[PublicEvidence]
    visible_logs: list[PublicEvidence]
    visible_runbooks: list[PublicEvidence]
    visible_timeline_notes: list[PublicEvidence]
    known_facts: list[str]
    last_action_result: str
    selected_severity: Optional[str] = None
    assigned_team: Optional[str] = None
    submitted_root_cause: Optional[str] = None
    submitted_mitigation: Optional[str] = None
    steps_taken: int
    steps_remaining: int
    done: bool
    action_history_summary: list[str]
    available_action_types: list[ActionType]


class StepInfo(BaseModel):
    message: str
    invalid_action: bool = False
    terminal_reason: Optional[str] = None
    inspected_evidence_id: Optional[str] = None


class StepResult(BaseModel):
    observation: Observation
    reward: float
    done: bool
    info: StepInfo


class InternalStateSnapshot(BaseModel):
    scenario_id: str
    title: str
    difficulty: Difficulty
    service: str
    steps_taken: int
    max_steps: int
    steps_remaining: int
    done: bool
    total_reward: float
    selected_severity: Optional[str] = None
    assigned_team: Optional[str] = None
    submitted_root_cause: Optional[str] = None
    submitted_mitigation: Optional[str] = None
    inspected_evidence_ids: list[str]
    discovered_relevant_evidence_ids: list[str]
    known_facts: list[str]
    action_history: list[dict[str, Any]]
    resolution_attempted: bool
    premature_resolution: bool
    terminal_reason: Optional[str] = None
    last_action_result: str


class GraderResult(BaseModel):
    scenario_id: str
    difficulty: Difficulty
    score: float
    components: dict[str, float]
    weights: dict[str, float]
    details: list[str] = Field(default_factory=list)


class TaskSummary(BaseModel):
    difficulty: Difficulty
    scenario_count: int
    average_score: float
    min_score: float
    max_score: float


class ScenarioSummary(BaseModel):
    scenario_id: str
    title: str
    difficulty: Difficulty
    service: str
    max_steps: int


class ResetRequest(BaseModel):
    scenario_id: Optional[str] = None
    difficulty: Optional[Difficulty] = None


class GradeRequest(BaseModel):
    scenario_id: Optional[str] = None
