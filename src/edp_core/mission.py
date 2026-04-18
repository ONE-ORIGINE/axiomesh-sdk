from __future__ import annotations

from dataclasses import dataclass, field

from .semantic import SenseVector


@dataclass(slots=True)
class MissionObjective:
    objective_id: str
    description: str
    target_sense: SenseVector
    priority: int = 100
    success_threshold: float = 0.65
    preferred_contexts: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class MissionStage:
    index: int
    objective_id: str
    context_name: str
    action_type: str
    score: float
    transition_cost: float
    rationale: str


@dataclass(slots=True)
class MissionPlan:
    mission_id: str
    stages: list[MissionStage] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    total_score: float = 0.0

    @property
    def executable(self) -> bool:
        return bool(self.stages) and not self.blocked_reasons
