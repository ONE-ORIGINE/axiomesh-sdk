from __future__ import annotations

import math
from dataclasses import dataclass, field
from collections import defaultdict, deque
from typing import Any

from .semantic import SenseVector


MISSION_POLICY_PRESETS: dict[str, dict[str, float]] = {
    "balanced": {},
    "risk_averse": {"risk_weight": 1.8, "certainty_weight": 1.3, "load_weight": 0.9, "locality_weight": 0.8},
    "certainty_first": {"certainty_weight": 1.9, "risk_weight": 1.2, "load_weight": 0.8},
    "locality_first": {"locality_weight": 1.8, "channel_weight": 1.2, "risk_weight": 1.0},
    "throughput": {"load_weight": 1.8, "base_weight": 1.1, "risk_weight": 0.7, "certainty_weight": 0.8},
    "emergency": {"base_weight": 1.2, "role_weight": 1.3, "context_weight": 1.3, "risk_weight": 1.6, "certainty_weight": 1.5},
    "stealth": {"channel_weight": 1.4, "locality_weight": 1.3, "risk_weight": 1.3, "base_weight": 0.9},
}


def resolve_mission_policy(policy: dict[str, float] | None) -> dict[str, float]:
    policy = dict(policy or {})
    preset = str(policy.pop("preset", policy.pop("policy_name", "balanced")) or "balanced").strip().lower()
    merged = dict(MISSION_POLICY_PRESETS.get(preset, MISSION_POLICY_PRESETS["balanced"]))
    merged.update(policy)
    merged["preset"] = preset
    return merged


@dataclass(slots=True)
class TaskSpec:
    task_id: str
    description: str
    goal_dimension: str = "technical"
    goal_meaning: str = "task"
    goal_magnitude: float = 0.8
    required_roles: list[str] = field(default_factory=list)
    preferred_contexts: list[str] = field(default_factory=list)
    target_agent_ids: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    channel: str = "all"
    payload: dict[str, Any] = field(default_factory=dict)
    mission_policy: dict[str, float] = field(default_factory=dict)
    preferred_environment_tags: list[str] = field(default_factory=list)

    def to_goal_sense(self) -> SenseVector:
        factory = getattr(SenseVector, self.goal_dimension, SenseVector.technical)
        return factory(self.goal_meaning, self.goal_magnitude)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "goal_dimension": self.goal_dimension,
            "goal_meaning": self.goal_meaning,
            "goal_magnitude": self.goal_magnitude,
            "required_roles": self.required_roles,
            "preferred_contexts": self.preferred_contexts,
            "target_agent_ids": self.target_agent_ids,
            "depends_on": self.depends_on,
            "channel": self.channel,
            "payload": self.payload,
            "mission_policy": self.mission_policy,
            "preferred_environment_tags": self.preferred_environment_tags,
        }


@dataclass(slots=True)
class TaskAssignment:
    task_id: str
    agent_id: str
    actor_name: str
    context_name: str
    role: str
    action_type: str
    score: float
    executable: bool
    depends_on: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "actor_name": self.actor_name,
            "context_name": self.context_name,
            "role": self.role,
            "action_type": self.action_type,
            "score": self.score,
            "executable": self.executable,
            "depends_on": self.depends_on,
            "warnings": self.warnings,
            "rationale": self.rationale,
        }


@dataclass(slots=True)
class CooperativeExecutionPlan:
    channel: str
    tasks: list[TaskSpec] = field(default_factory=list)
    assignments: list[TaskAssignment] = field(default_factory=list)
    dependency_layers: list[list[str]] = field(default_factory=list)
    unmet_tasks: list[dict[str, Any]] = field(default_factory=list)
    neighborhood_map: dict[str, list[str]] = field(default_factory=dict)
    coordination_energy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "tasks": [task.to_dict() for task in self.tasks],
            "assignments": [assignment.to_dict() for assignment in self.assignments],
            "dependency_layers": self.dependency_layers,
            "unmet_tasks": self.unmet_tasks,
            "neighborhood_map": self.neighborhood_map,
            "coordination_energy": self.coordination_energy,
        }


@dataclass(slots=True)
class NegotiationBid:
    task_id: str
    agent_id: str
    actor_name: str
    context_name: str
    role: str
    channel: str
    bid_score: float
    executable: bool
    rationale: str = ""
    warnings: list[str] = field(default_factory=list)
    score_components: dict[str, float] = field(default_factory=dict)
    workload: float = 0.0
    capacity: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "actor_name": self.actor_name,
            "context_name": self.context_name,
            "role": self.role,
            "channel": self.channel,
            "bid_score": self.bid_score,
            "executable": self.executable,
            "rationale": self.rationale,
            "warnings": self.warnings,
            "score_components": self.score_components,
            "workload": self.workload,
            "capacity": self.capacity,
        }


@dataclass(slots=True)
class NegotiationResult:
    task: dict[str, Any]
    winner: dict[str, Any] | None = None
    bids: list[NegotiationBid] = field(default_factory=list)
    unresolved_reasons: list[str] = field(default_factory=list)
    arbitration: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "winner": self.winner,
            "bids": [bid.to_dict() for bid in self.bids],
            "unresolved_reasons": self.unresolved_reasons,
            "arbitration": self.arbitration,
        }


@dataclass(slots=True)
class DistributedActionResult:
    task_id: str
    agent_id: str
    actor_name: str
    context_name: str
    action_type: str
    ok: bool
    message: str
    depends_on: list[str] = field(default_factory=list)
    role: str = ""
    channel: str = "all"
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "actor_name": self.actor_name,
            "context_name": self.context_name,
            "action_type": self.action_type,
            "ok": self.ok,
            "message": self.message,
            "depends_on": self.depends_on,
            "role": self.role,
            "channel": self.channel,
            "metrics": self.metrics,
        }


@dataclass(slots=True)
class DistributedExecutionResult:
    channel: str
    layers: list[list[str]] = field(default_factory=list)
    executed: list[DistributedActionResult] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    causal_links: list[dict[str, Any]] = field(default_factory=list)
    compensations: list[dict[str, Any]] = field(default_factory=list)
    rolled_back: bool = False
    failed_task_ids: list[str] = field(default_factory=list)
    rollback_policy: str = "full"

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "layers": self.layers,
            "executed": [item.to_dict() for item in self.executed],
            "blocked": self.blocked,
            "causal_links": self.causal_links,
            "compensations": self.compensations,
            "rolled_back": self.rolled_back,
            "failed_task_ids": self.failed_task_ids,
            "rollback_policy": self.rollback_policy,
        }


@dataclass(slots=True)
class AgentChannel:
    name: str
    members: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "members": sorted(self.members), "metadata": self.metadata}


@dataclass(slots=True)
class ContextBinding:
    agent_id: str
    context_name: str
    role: str = ""
    parent_agent_id: str = ""
    channel: str = "all"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "context_name": self.context_name,
            "role": self.role,
            "parent_agent_id": self.parent_agent_id,
            "channel": self.channel,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class CoordinationItem:
    agent_id: str
    actor_name: str
    context_name: str = ""
    executable: bool = False
    steps: list[dict[str, Any]] = field(default_factory=list)
    blocked_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    score: float = 0.0
    role: str = ""
    parent_agent_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "actor_name": self.actor_name,
            "context_name": self.context_name,
            "executable": self.executable,
            "steps": self.steps,
            "blocked_reasons": self.blocked_reasons,
            "warnings": self.warnings,
            "score": self.score,
            "role": self.role,
            "parent_agent_id": self.parent_agent_id,
        }


@dataclass(slots=True)
class MultiAgentPlan:
    channel: str
    goal: dict[str, Any]
    items: list[CoordinationItem] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    coordination_energy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "goal": self.goal,
            "items": [item.to_dict() for item in self.items],
            "conflicts": self.conflicts,
            "coordination_energy": self.coordination_energy,
        }





def _floatish(value: Any, default: float) -> float:
    try:
        return float(value)
    except Exception:
        return default

def _policy_value(policy: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(policy.get(key, default))
    except Exception:
        return default

class MultiAgentCoordinator:
    def __init__(self, env):
        self.env = env
        self.channels: dict[str, AgentChannel] = {"all": AgentChannel("all")}

    def ensure_channel(self, name: str, **metadata: Any) -> AgentChannel:
        channel = self.channels.setdefault(name, AgentChannel(name=name))
        if metadata:
            channel.metadata.update(metadata)
        return channel

    def add_member(self, channel_name: str, actor_or_id) -> None:
        actor_id = getattr(actor_or_id, "element_id", actor_or_id)
        self.ensure_channel(channel_name).members.add(str(actor_id))

    def remove_member(self, channel_name: str, actor_or_id) -> None:
        actor_id = getattr(actor_or_id, "element_id", actor_or_id)
        if channel_name in self.channels:
            self.channels[channel_name].members.discard(str(actor_id))

    def _role_for(self, actor) -> str:
        return str(actor.static_properties.get("role", actor.dynamic_properties.get("role", actor.element_type)))

    def _load_metrics(self, actor) -> tuple[float, float]:
        workload = _floatish(actor.dynamic_properties.get('task_load', 0.0), 0.0)
        capacity = max(0.1, _floatish(actor.static_properties.get('task_capacity', actor.dynamic_properties.get('task_capacity', 1.0)), 1.0))
        return workload, capacity

    def _knowledge_quality(self, actor) -> float:
        battery = actor.dynamic_properties.get('battery_pct', actor.dynamic_properties.get('battery', 100.0))
        gps_lock = actor.dynamic_properties.get('gps_lock', True)
        try:
            battery_ratio = max(0.0, min(1.0, float(battery) / 100.0))
        except Exception:
            battery_ratio = 1.0
        return round(0.6 * battery_ratio + (0.4 if gps_lock else 0.0), 6)

    def _locality_bonus(self, actor, task: TaskSpec) -> float:
        target = task.payload.get('target_position')
        if not isinstance(target, (list, tuple)) or len(target) != 3:
            return 0.0
        ax, ay, az = self._position(actor)
        tx, ty, tz = [float(v) for v in target]
        dist = math.sqrt((ax-tx)**2 + (ay-ty)**2 + (az-tz)**2)
        return round(max(0.0, 0.2 - 0.02 * dist), 6)

    def auto_register(self) -> None:
        self.ensure_channel("all")
        for actor in self.env.elements.values():
            self.add_member("all", actor)
            self.add_member(f"type:{actor.element_type}", actor)
            role = self._role_for(actor)
            if role:
                self.add_member(f"role:{role}", actor)
            parent = actor.static_properties.get("parent_agent_id")
            if parent:
                self.add_member(f"parent:{parent}", actor)

    def members(self, channel_name: str) -> list:
        self.auto_register()
        ids = self.channels.get(channel_name, AgentChannel(channel_name)).members
        return [self.env.elements[aid] for aid in sorted(ids) if aid in self.env.elements]

    def channels_for(self, actor_or_id) -> list[str]:
        actor_id = getattr(actor_or_id, "element_id", actor_or_id)
        self.auto_register()
        return sorted(name for name, channel in self.channels.items() if str(actor_id) in channel.members)

    def binding_for(self, actor, context_name: str, channel: str = "all") -> ContextBinding:
        return ContextBinding(
            agent_id=actor.element_id,
            context_name=context_name,
            role=self._role_for(actor),
            parent_agent_id=str(actor.static_properties.get("parent_agent_id", "")),
            channel=channel,
            metadata={"name": actor.name, "element_type": actor.element_type},
        )

    def bindings_for_channel(self, channel_name: str, context_name: str) -> list[ContextBinding]:
        return [self.binding_for(actor, context_name, channel=channel_name) for actor in self.members(channel_name)]

    def _position(self, actor) -> tuple[float, float, float]:
        return (
            float(actor.physical_state.get("x", 0.0)),
            float(actor.physical_state.get("y", 0.0)),
            float(actor.physical_state.get("z", 0.0)),
        )

    def _conflicts(self, actors: list, min_separation: float) -> tuple[list[dict[str, Any]], float]:
        conflicts: list[dict[str, Any]] = []
        energy = 0.0
        for i, left in enumerate(actors):
            lx, ly, lz = self._position(left)
            for right in actors[i + 1 :]:
                rx, ry, rz = self._position(right)
                dist = math.sqrt((lx - rx) ** 2 + (ly - ry) ** 2 + (lz - rz) ** 2)
                if dist < min_separation:
                    severity = round((min_separation - dist) / max(min_separation, 1e-9), 4)
                    energy += severity
                    conflicts.append(
                        {
                            "type": "separation",
                            "left": left.element_id,
                            "right": right.element_id,
                            "distance": round(dist, 4),
                            "threshold": min_separation,
                            "severity": severity,
                        }
                    )
        return conflicts, energy

    def preview_plan(self, actors: list, goal_sense: SenseVector, max_steps: int = 2, channel: str = "all", min_separation: float = 2.0) -> MultiAgentPlan:
        self.auto_register()
        if channel != "all":
            allowed = {actor.element_id for actor in self.members(channel)}
            actors = [actor for actor in actors if actor.element_id in allowed]
        items: list[CoordinationItem] = []
        for actor in actors:
            sequence = self.env.plan_sequence(actor, goal_sense, max_steps=max_steps)
            score = round(sum(step.score for step in sequence.steps), 4)
            items.append(
                CoordinationItem(
                    agent_id=actor.element_id,
                    actor_name=actor.name,
                    executable=sequence.executable,
                    steps=[
                        {
                            "index": step.index,
                            "context_name": step.context_name,
                            "action_type": step.action_type,
                            "score": step.score,
                            "transition_cost": step.transition_cost,
                            "rationale": step.rationale,
                        }
                        for step in sequence.steps
                    ],
                    blocked_reasons=sequence.blocked_reasons,
                    score=score,
                    role=self._role_for(actor),
                    parent_agent_id=str(actor.static_properties.get("parent_agent_id", "")),
                )
            )
        conflicts, energy = self._conflicts(actors, min_separation=min_separation)
        return MultiAgentPlan(
            channel=channel,
            goal={"dimension": goal_sense.dimension, "meaning": goal_sense.meaning, "magnitude": goal_sense.magnitude},
            items=items,
            conflicts=conflicts,
            coordination_energy=round(energy, 6),
        )

    def preview_contextual_plan(self, bindings: list[ContextBinding], goal_sense: SenseVector, max_steps: int = 2, min_separation: float = 2.0) -> MultiAgentPlan:
        self.auto_register()
        items: list[CoordinationItem] = []
        bound_actors = []
        for binding in bindings:
            actor = self.env.elements.get(binding.agent_id)
            if actor is None:
                continue
            bound_actors.append(actor)
            ctx = next((ctx for ctx in self.env.contexts if ctx.name == binding.context_name), None)
            if ctx is None:
                items.append(
                    CoordinationItem(
                        agent_id=binding.agent_id,
                        actor_name=str(binding.metadata.get("name", binding.agent_id)),
                        context_name=binding.context_name,
                        executable=False,
                        blocked_reasons=[f"Unknown context '{binding.context_name}'"],
                        role=binding.role,
                        parent_agent_id=binding.parent_agent_id,
                    )
                )
                continue
            sequence = self.env.plan_sequence(actor, goal_sense, contexts=[ctx], max_steps=max_steps)
            score = round(sum(step.score for step in sequence.steps), 4)
            items.append(
                CoordinationItem(
                    agent_id=actor.element_id,
                    actor_name=actor.name,
                    context_name=ctx.name,
                    executable=sequence.executable,
                    steps=[
                        {
                            "index": step.index,
                            "context_name": step.context_name,
                            "action_type": step.action_type,
                            "score": step.score,
                            "transition_cost": step.transition_cost,
                            "rationale": step.rationale,
                        }
                        for step in sequence.steps
                    ],
                    blocked_reasons=sequence.blocked_reasons,
                    score=score,
                    role=binding.role or self._role_for(actor),
                    parent_agent_id=binding.parent_agent_id or str(actor.static_properties.get("parent_agent_id", "")),
                )
            )
        conflicts, energy = self._conflicts(bound_actors, min_separation=min_separation)
        return MultiAgentPlan(
            channel="multi-context",
            goal={"dimension": goal_sense.dimension, "meaning": goal_sense.meaning, "magnitude": goal_sense.magnitude},
            items=items,
            conflicts=conflicts,
            coordination_energy=round(energy, 6),
        )


    def neighborhood(self, actors: list | None = None, radius: float = 8.0) -> dict[str, list[str]]:
        self.auto_register()
        actors = actors or list(self.env.elements.values())
        mapping: dict[str, list[str]] = {}
        for actor in actors:
            ax, ay, az = self._position(actor)
            neighbors: list[str] = []
            for other in actors:
                if other.element_id == actor.element_id:
                    continue
                bx, by, bz = self._position(other)
                dist = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
                if dist <= radius:
                    neighbors.append(other.element_id)
            mapping[actor.element_id] = sorted(neighbors)
        return mapping

    def _context_for_binding(self, binding: ContextBinding):
        return next((ctx for ctx in self.env.contexts if ctx.name == binding.context_name), None)

    def _task_candidates(self, bindings: list[ContextBinding], task: TaskSpec) -> list[TaskAssignment]:
        candidates: list[TaskAssignment] = []
        task_goal = task.to_goal_sense()
        for binding in bindings:
            if task.channel and binding.channel not in {task.channel, 'all'} and task.channel != 'all':
                continue
            actor = self.env.elements.get(binding.agent_id)
            if actor is None:
                continue
            if task.target_agent_ids and actor.element_id not in task.target_agent_ids:
                continue
            role = binding.role or self._role_for(actor)
            if task.required_roles and role not in set(task.required_roles):
                continue
            if task.preferred_contexts and binding.context_name not in set(task.preferred_contexts):
                continue
            ctx = self._context_for_binding(binding)
            if ctx is None:
                continue
            sequence = self.env.plan_sequence(actor, task_goal, contexts=[ctx], max_steps=1)
            action_hint = str(task.payload.get('action_type_hint', '')).strip()
            if action_hint:
                hinted = next((a for a in ctx.actions if a.action_type == action_hint), None)
                if hinted is not None:
                    assessment = ctx.assess_action(actor, hinted, payload=task.payload)
                    score = round(assessment.final_score + (0.05 if role in set(task.required_roles or [role]) else 0.0), 4)
                    assignment = TaskAssignment(
                        task_id=task.task_id,
                        agent_id=actor.element_id,
                        actor_name=actor.name,
                        context_name=ctx.name,
                        role=role,
                        action_type=hinted.action_type,
                        score=score,
                        executable=assessment.executable,
                        depends_on=list(task.depends_on),
                        warnings=[trace.reason for trace in assessment.blocked_by + assessment.warnings],
                        rationale=f"{task.description} via hinted action {ctx.name}:{hinted.action_type}",
                    )
                    candidates.append(assignment)
                    continue
            if sequence.steps:
                step = sequence.steps[0]
                score = round(step.score + (0.05 if role in set(task.required_roles or [role]) else 0.0), 4)
                assignment = TaskAssignment(
                    task_id=task.task_id,
                    agent_id=actor.element_id,
                    actor_name=actor.name,
                    context_name=ctx.name,
                    role=role,
                    action_type=step.action_type,
                    score=score,
                    executable=sequence.executable,
                    depends_on=list(task.depends_on),
                    warnings=list(sequence.blocked_reasons),
                    rationale=f"{task.description} via {ctx.name}",
                )
            else:
                assignment = TaskAssignment(
                    task_id=task.task_id,
                    agent_id=actor.element_id,
                    actor_name=actor.name,
                    context_name=ctx.name,
                    role=role,
                    action_type='',
                    score=-1.0,
                    executable=False,
                    depends_on=list(task.depends_on),
                    warnings=list(sequence.blocked_reasons),
                    rationale=f"No executable step for {task.description} in {ctx.name}",
                )
            candidates.append(assignment)
        candidates.sort(key=lambda item: (item.executable, item.score), reverse=True)
        return candidates

    def _topological_layers(self, tasks: list[TaskSpec]) -> list[list[str]]:
        task_map = {task.task_id: task for task in tasks}
        indegree = {task.task_id: 0 for task in tasks}
        edges: dict[str, list[str]] = defaultdict(list)
        for task in tasks:
            for dep in task.depends_on:
                if dep in task_map:
                    edges[dep].append(task.task_id)
                    indegree[task.task_id] += 1
        queue = deque(sorted([tid for tid, degree in indegree.items() if degree == 0]))
        layers: list[list[str]] = []
        seen = set()
        while queue:
            layer: list[str] = []
            for _ in range(len(queue)):
                tid = queue.popleft()
                if tid in seen:
                    continue
                seen.add(tid)
                layer.append(tid)
                for nxt in edges.get(tid, []):
                    indegree[nxt] -= 1
            if layer:
                layers.append(layer)
                for tid in layer:
                    for nxt in edges.get(tid, []):
                        if indegree[nxt] == 0:
                            queue.append(nxt)
        remaining = [tid for tid in task_map if tid not in seen]
        if remaining:
            layers.append(sorted(remaining))
        return layers

    def negotiate_task(self, bindings: list[ContextBinding], task: TaskSpec) -> NegotiationResult:
        self.auto_register()
        policy = resolve_mission_policy(task.mission_policy)
        base_w = _policy_value(policy, 'base_weight', 1.0)
        channel_w = _policy_value(policy, 'channel_weight', 1.0)
        role_w = _policy_value(policy, 'role_weight', 1.0)
        context_w = _policy_value(policy, 'context_weight', 1.0)
        locality_w = _policy_value(policy, 'locality_weight', 1.0)
        certainty_w = _policy_value(policy, 'certainty_weight', 1.0)
        load_w = _policy_value(policy, 'load_weight', 1.0)
        risk_w = _policy_value(policy, 'risk_weight', 1.0)
        bids: list[NegotiationBid] = []
        for candidate in self._task_candidates(bindings, task):
            actor = self.env.elements.get(candidate.agent_id)
            workload, capacity = self._load_metrics(actor) if actor is not None else (0.0, 1.0)
            load_ratio = workload / capacity if capacity > 0 else 1.0
            channel_bonus = 0.05 if task.channel == 'all' or candidate.context_name and any(b.agent_id == candidate.agent_id and (b.channel == task.channel or task.channel == 'all') for b in bindings) else 0.0
            role_bonus = 0.05 if not task.required_roles or candidate.role in task.required_roles else -0.15
            context_bonus = 0.05 if not task.preferred_contexts or candidate.context_name in task.preferred_contexts else 0.0
            locality_bonus = self._locality_bonus(actor, task) if actor is not None else 0.0
            certainty_bonus = self._knowledge_quality(actor) * 0.1 if actor is not None else 0.0
            load_penalty = min(0.4, load_ratio * 0.2)
            risk_penalty = 0.0
            if candidate.warnings:
                risk_penalty += 0.03 * len(candidate.warnings)
            if not candidate.executable:
                risk_penalty += 0.25
            weighted = {
                'base': round(candidate.score * base_w, 6),
                'channel_bonus': round(channel_bonus * channel_w, 6),
                'role_bonus': round(role_bonus * role_w, 6),
                'context_bonus': round(context_bonus * context_w, 6),
                'locality_bonus': round(locality_bonus * locality_w, 6),
                'certainty_bonus': round(certainty_bonus * certainty_w, 6),
                'load_penalty': round(-load_penalty * load_w, 6),
                'risk_penalty': round(-risk_penalty * risk_w, 6),
            }
            bid_score = round(sum(weighted.values()), 6)
            bids.append(NegotiationBid(
                task_id=task.task_id,
                agent_id=candidate.agent_id,
                actor_name=candidate.actor_name,
                context_name=candidate.context_name,
                role=candidate.role,
                channel=next((b.channel for b in bindings if b.agent_id == candidate.agent_id and b.context_name == candidate.context_name), 'all'),
                bid_score=bid_score,
                executable=candidate.executable,
                rationale=candidate.rationale,
                warnings=list(candidate.warnings),
                score_components=weighted,
                workload=round(workload, 6),
                capacity=round(capacity, 6),
            ))
        bids.sort(key=lambda bid: (bid.executable, bid.bid_score, -bid.workload), reverse=True)
        winner = bids[0].to_dict() if bids and bids[0].executable else None
        unresolved = [] if winner is not None else [f"No executable bid for task '{task.task_id}'"]
        arbitration: dict[str, Any] = {'mission_policy': policy.get('preset', 'balanced'), 'policy_weights': {
            'base_weight': base_w, 'channel_weight': channel_w, 'role_weight': role_w, 'context_weight': context_w,
            'locality_weight': locality_w, 'certainty_weight': certainty_w, 'load_weight': load_w, 'risk_weight': risk_w,
        }}
        if len(bids) >= 2 and bids[0].executable and bids[1].executable:
            margin = round(bids[0].bid_score - bids[1].bid_score, 6)
            if margin <= 0.075:
                selected = sorted([bids[0], bids[1]], key=lambda b: (b.workload / max(0.1, b.capacity), -b.score_components.get('certainty_bonus', 0.0), -b.score_components.get('locality_bonus', 0.0)))[0]
                winner = selected.to_dict()
                arbitration.update({
                    'policy': 'multi_criteria_tie_break',
                    'margin': margin,
                    'candidates': [bids[0].agent_id, bids[1].agent_id],
                    'selected_by': 'load->certainty->locality',
                    'selected_agent_id': selected.agent_id,
                })
        return NegotiationResult(task=task.to_dict(), winner=winner, bids=bids, unresolved_reasons=unresolved, arbitration=arbitration)

    def assign_tasks(self, bindings: list[ContextBinding], tasks: list[TaskSpec], neighborhood_radius: float = 8.0) -> CooperativeExecutionPlan:
        self.auto_register()
        assignments: list[TaskAssignment] = []
        unmet: list[dict[str, Any]] = []
        projected_loads: dict[str, float] = defaultdict(float)
        for task in tasks:
            candidates = self._task_candidates(bindings, task)
            selected = None
            ranked = sorted(candidates, key=lambda c: (c.executable, c.score - projected_loads[c.agent_id] * 0.15), reverse=True)
            for candidate in ranked:
                actor = self.env.elements.get(candidate.agent_id)
                workload, capacity = self._load_metrics(actor) if actor is not None else (0.0, 1.0)
                projected_ratio = (workload + projected_loads[candidate.agent_id] + 1.0) / max(0.1, capacity)
                if projected_ratio <= 1.2 or candidate.role in {'safety', 'perception'}:
                    selected = candidate
                    break
            if selected is None and ranked:
                selected = ranked[0]
            if selected is None:
                unmet.append({"task_id": task.task_id, "reason": "no candidate matched role/context", "depends_on": list(task.depends_on)})
                continue
            assignments.append(selected)
            projected_loads[selected.agent_id] += 1.0
        involved = [self.env.elements[a.agent_id] for a in assignments if a.agent_id in self.env.elements]
        conflicts, energy = self._conflicts(involved, min_separation=2.0)
        if conflicts:
            for conflict in conflicts:
                unmet.append({"task_id": "conflict", "reason": conflict})
        neighborhood_map = self.neighborhood(involved, radius=neighborhood_radius)
        return CooperativeExecutionPlan(
            channel=bindings[0].channel if bindings else 'all',
            tasks=tasks,
            assignments=assignments,
            dependency_layers=self._topological_layers(tasks),
            unmet_tasks=unmet,
            neighborhood_map=neighborhood_map,
            coordination_energy=round(energy + 0.05 * len(unmet), 6),
        )
