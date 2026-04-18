from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .semantic import SenseVector, SENSE_NULL


class ActionCategory(str, Enum):
    COMMAND = "command"
    QUERY = "query"
    SIGNAL = "signal"
    TRANSFORM = "transform"
    LIFECYCLE = "lifecycle"


class RuntimeStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    DEGRADED = "degraded"
    SUSPENDED = "suspended"
    EJECTED = "ejected"


class ContextKind(str, Enum):
    GLOBAL = "global"
    TEMPORAL = "temporal"
    SPATIAL = "spatial"
    SEMANTIC = "semantic"
    CAUSAL = "causal"
    OBSERVATION = "observation"
    GOVERNANCE = "governance"


class EnvironmentKind(str, Enum):
    STATIC = "static"
    REACTIVE = "reactive"
    DYNAMIC = "dynamic"
    LIVING = "living"


class RuleMode(str, Enum):
    HARD = "hard"
    SOFT = "soft"


@dataclass(slots=True)
class ActionRequest:
    actor_id: str
    action_type: str
    payload: dict[str, Any]
    context_name: str
    requested_at: float = field(default_factory=time.time)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""


@dataclass(slots=True)
class ReactionRecord:
    action_type: str
    ok: bool
    message: str = ""
    result: dict[str, Any] | None = None
    sense: SenseVector = field(default_factory=lambda: SENSE_NULL)
    impact_ids: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    chain_depth: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)

    def line(self) -> str:
        icon = "✓" if self.ok else "✗"
        return f"{icon} {self.action_type} | {self.message}"


@dataclass(slots=True)
class RuleTrace:
    rule_id: str
    description: str
    holds: bool
    role: str = "enabler"
    reason: str = ""
    expression: str = ""
    weight: float = 1.0
    mode: RuleMode = RuleMode.HARD
    priority: int = 100
    penalty: float = 0.0


@dataclass(slots=True)
class ActionAssessment:
    action_type: str
    base_score: float
    final_score: float
    soft_penalty: float = 0.0
    blocked_by: list[RuleTrace] = field(default_factory=list)
    warnings: list[RuleTrace] = field(default_factory=list)
    transition_cost: float = 0.0

    @property
    def executable(self) -> bool:
        return not self.blocked_by


@dataclass(slots=True)
class ContextTrace:
    context_name: str
    actor_id: str
    active_rules: list[RuleTrace] = field(default_factory=list)
    available_actions: list[str] = field(default_factory=list)
    harmony: dict[str, dict] = field(default_factory=dict)
    blockers: dict[str, list[str]] = field(default_factory=dict)
    assessments: dict[str, ActionAssessment] = field(default_factory=dict)
    readiness_score: float = 0.0


@dataclass(slots=True)
class PlanningDecision:
    context_name: str
    action_type: str
    harmony_score: float
    goal_distance: float
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rationale: str = ""
    transition_cost: float = 0.0

    @property
    def executable(self) -> bool:
        return not self.blockers


@dataclass(slots=True)
class PlanStep:
    index: int
    context_name: str
    action_type: str
    score: float
    rationale: str = ""
    transition_cost: float = 0.0


@dataclass(slots=True)
class PlanSequence:
    steps: list[PlanStep] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)

    @property
    def executable(self) -> bool:
        return not self.blocked_reasons and bool(self.steps)
