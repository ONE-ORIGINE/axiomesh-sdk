from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .contracts import (
    ActionAssessment,
    ActionCategory,
    ActionRequest,
    ContextKind,
    ContextTrace,
    EnvironmentKind,
    PlanSequence,
    PlanStep,
    PlanningDecision,
    ReactionRecord,
    RuleMode,
    RuntimeStatus,
)
from .mission import MissionObjective, MissionPlan, MissionStage
from .math_model import ConstraintFactor, FactorGraph, FactorVariable, MathematicalEnvironmentExport, NodeMatrix, SemanticEdge, SemanticGraph
from .rules import Circumstance, RuleBook
from .semantic import HarmonyProfile, SenseVector, SENSE_NULL, compute_harmony

Handler = Callable[[Any, ActionRequest, "Context"], Awaitable[ReactionRecord]]


@dataclass(slots=True)
class Action:
    action_type: str
    category: ActionCategory
    description: str
    sense: SenseVector
    handler: Handler | None = None
    guards: list[Circumstance] = field(default_factory=list)
    expected_reaction_sense: SenseVector = field(default_factory=lambda: SENSE_NULL)
    cost: float = 0.0

    async def execute(self, actor: "Element", request: ActionRequest, ctx: "Context") -> ReactionRecord:
        assessment = ctx.assess_action(actor, self, payload=request.payload)
        if not assessment.executable:
            reasons = "; ".join(trace.reason for trace in assessment.blocked_by)
            return ReactionRecord(self.action_type, ok=False, message=f"Blocked: {reasons}")
        if self.handler is None:
            return ReactionRecord(self.action_type, ok=True, message="No-op action", metrics={"score": assessment.final_score})
        reaction = await self.handler(actor, request, ctx)
        reaction.metrics.setdefault("score", round(assessment.final_score, 4))
        reaction.metrics.setdefault("soft_penalty", round(assessment.soft_penalty, 4))
        reaction.metrics.setdefault("transition_cost", round(assessment.transition_cost, 4))
        return reaction

    def harmony(self, ctx: "Context", current_sense: SenseVector | None = None) -> HarmonyProfile:
        sense = current_sense or ctx.basis
        return compute_harmony(
            self.sense,
            ctx.basis,
            sense,
            expected_reaction=self.expected_reaction_sense,
            observed_reaction=None,
            action_type=self.action_type,
        )


class Element:
    reserved_names = {"runtime_status", "physical_state", "knowledge_state", "mission_state"}

    def __init__(self, name: str, element_type: str, sense: SenseVector | None = None):
        self.element_id = str(uuid.uuid4())
        self.name = name
        self.element_type = element_type
        self.sense = sense or SenseVector.social(name, 0.5)
        self.runtime_status = RuntimeStatus.PENDING
        self.physical_state: dict[str, Any] = {}
        self.knowledge_state: dict[str, Any] = {}
        self.mission_state: dict[str, Any] = {}
        self.static_properties: dict[str, Any] = {}
        self.dynamic_properties: dict[str, Any] = {}
        self._env: Environment | None = None

    def set_static(self, key: str, value: Any) -> None:
        if key in self.reserved_names:
            raise ValueError(f"'{key}' is reserved")
        self.static_properties[key] = value

    def set_dynamic(self, key: str, value: Any) -> None:
        if key in self.reserved_names:
            raise ValueError(f"'{key}' is reserved")
        self.dynamic_properties[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.dynamic_properties.get(key, self.static_properties.get(key, default))

    async def on_admitted(self, env: "Environment") -> None:
        self._env = env
        self.runtime_status = RuntimeStatus.ACTIVE

    async def on_impacted(self, reaction: ReactionRecord, request: ActionRequest, ctx: "Context") -> None:
        return None

    async def on_tick(self, tick: int) -> None:
        return None

    def node_matrix(self, dims: list[str]) -> NodeMatrix:
        values = [[float(self.physical_state.get(dim, 0.0)) for dim in dims]]
        certainty = [[float(self.knowledge_state.get(f"{dim}_certainty", 0.0)) for dim in dims]]
        quality = [[float(self.knowledge_state.get(f"{dim}_quality", 0.0)) for dim in dims]]
        mission = [[float(self.mission_state.get(dim, 0.0)) if isinstance(self.mission_state.get(dim, 0.0), (int, float)) else 0.0 for dim in dims]]
        return NodeMatrix(
            node_id=self.element_id,
            values=values + certainty + quality + mission,
            labels=["physical", "certainty", "quality", "mission"],
            metadata={"name": self.name, "type": self.element_type},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "name": self.name,
            "element_type": self.element_type,
            "runtime_status": self.runtime_status.value,
            **self.static_properties,
            **self.dynamic_properties,
        }


class Context:
    def __init__(self, name: str, kind: ContextKind, basis: SenseVector, parent: "Context | None" = None):
        self.context_id = str(uuid.uuid4())
        self.name = name
        self.kind = kind
        self.basis = basis
        self.parent = parent
        self.data: dict[str, Any] = {}
        self.circumstances: list[Circumstance] = []
        self.actions: list[Action] = []
        self.elements: list[dict[str, Any]] = []

    def set(self, key: str, value: Any) -> "Context":
        self.data[key] = value
        return self

    def include(self, element: dict[str, Any]) -> "Context":
        self.elements.append(element)
        return self

    def add_rule(self, rule: Circumstance) -> "Context":
        self.circumstances.append(rule)
        return self

    def add_action(self, action: Action) -> "Context":
        self.actions.append(action)
        return self

    def transition_cost_to(self, other: "Context | None") -> float:
        if other is None:
            return 0.0
        return round(self.basis.angular_distance(other.basis), 4)

    def _scope(self, actor: Element, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        scope = dict(self.data)
        scope.update(actor.static_properties)
        scope.update(actor.dynamic_properties)
        scope.update(actor.physical_state)
        scope.update({k: v for k, v in actor.knowledge_state.items() if not k.endswith("_source")})
        scope.update({k: v for k, v in actor.mission_state.items() if isinstance(v, (int, float, bool, str))})
        if payload:
            scope.update({f"payload_{k}": v for k, v in payload.items()})
        scope.setdefault("runtime_status", actor.runtime_status.value)
        return scope

    def when_expr(
        self,
        cid: str,
        description: str,
        expression: str,
        role: str = "enabler",
        weight: float = 1.0,
        mode: RuleMode = RuleMode.HARD,
        priority: int = 100,
        penalty: float | None = None,
    ) -> "Context":
        rule = Circumstance.expr(
            cid,
            description,
            expression,
            resolver=lambda _ctx, frame: self._scope(frame["actor"], frame.get("payload")),
            role=role,
            weight=weight,
            mode=mode,
            priority=priority,
            penalty=penalty,
        )
        self.circumstances.append(rule)
        return self

    def rulebook(self) -> RuleBook:
        rules: list[Circumstance] = []
        cursor: Context | None = self
        seen: set[str] = set()
        while cursor is not None:
            for rule in cursor.circumstances:
                if rule.id not in seen:
                    seen.add(rule.id)
                    rules.append(rule)
            cursor = cursor.parent
        return RuleBook(sorted(rules, key=lambda rule: (rule.priority, rule.id)))

    def assess_action(self, actor: Element, action: Action, current_sense: SenseVector | None = None, payload: dict[str, Any] | None = None) -> ActionAssessment:
        frame = {"actor_id": actor.element_id, "actor": actor, "payload": payload or {}}
        base = action.harmony(self, current_sense).score - action.cost
        blocked: list = []
        warnings: list = []
        for trace in self.rulebook().evaluate(self, frame):
            if trace.role == "enabler" and not trace.holds:
                if trace.mode == RuleMode.HARD:
                    blocked.append(trace)
                else:
                    warnings.append(trace)
        for guard in action.guards:
            trace = guard.trace(self, frame)
            if not trace.holds:
                if trace.mode == RuleMode.HARD:
                    blocked.append(trace)
                else:
                    warnings.append(trace)
        soft_penalty = sum(trace.penalty for trace in warnings)
        final_score = base - soft_penalty
        return ActionAssessment(
            action_type=action.action_type,
            base_score=round(base, 4),
            final_score=round(final_score, 4),
            soft_penalty=round(soft_penalty, 4),
            blocked_by=sorted(blocked, key=lambda t: (t.priority, t.rule_id)),
            warnings=sorted(warnings, key=lambda t: (t.priority, t.rule_id)),
            transition_cost=0.0,
        )

    def available_actions(self, actor: Element, current_sense: SenseVector | None = None) -> list[tuple[Action, HarmonyProfile, ActionAssessment]]:
        out: list[tuple[Action, HarmonyProfile, ActionAssessment]] = []
        seen: set[str] = set()
        cursor: Context | None = self
        while cursor is not None:
            for action in cursor.actions:
                if action.action_type in seen:
                    continue
                seen.add(action.action_type)
                harmony = action.harmony(self, current_sense)
                assessment = self.assess_action(actor, action, current_sense)
                if assessment.executable:
                    out.append((action, harmony, assessment))
            cursor = cursor.parent
        out.sort(key=lambda pair: pair[2].final_score, reverse=True)
        return out

    def explain_action(self, actor: Element, action_type: str) -> list[str]:
        cursor: Context | None = self
        explanations: list[str] = []
        found = False
        while cursor is not None:
            for action in cursor.actions:
                if action.action_type != action_type:
                    continue
                found = True
                assessment = self.assess_action(actor, action)
                if assessment.blocked_by:
                    explanations.extend(trace.reason for trace in assessment.blocked_by)
                explanations.extend(f"warning: {trace.reason}" for trace in assessment.warnings)
            cursor = cursor.parent
        deduped = []
        seen = set()
        for item in explanations:
            if item not in seen:
                deduped.append(item)
                seen.add(item)
        if not found:
            return [f"Action '{action_type}' is not registered in context '{self.name}'"]
        return deduped

    def trace(self, actor: Element, current_sense: SenseVector | None = None) -> ContextTrace:
        frame = {"actor_id": actor.element_id, "actor": actor}
        traces = self.rulebook().evaluate(self, frame)
        available = self.available_actions(actor, current_sense)
        blockers: dict[str, list[str]] = {}
        assessments: dict[str, ActionAssessment] = {}
        cursor: Context | None = self
        action_types: set[str] = set()
        while cursor is not None:
            action_types.update(a.action_type for a in cursor.actions)
            cursor = cursor.parent
        for action_type in sorted(action_types):
            reasons = self.explain_action(actor, action_type)
            if reasons:
                blockers[action_type] = reasons
        for action_type in sorted(action_types):
            action = next((a for ctx in self._iter_contexts() for a in ctx.actions if a.action_type == action_type), None)
            if action is not None:
                assessments[action_type] = self.assess_action(actor, action, current_sense)
        hard_total = sum(1 for trace in traces if trace.mode == RuleMode.HARD and trace.role == "enabler")
        hard_ok = sum(1 for trace in traces if trace.mode == RuleMode.HARD and trace.role == "enabler" and trace.holds)
        soft_penalty = sum(trace.penalty for trace in traces if trace.mode == RuleMode.SOFT and trace.role == "enabler" and not trace.holds)
        readiness = 1.0 if hard_total == 0 else hard_ok / hard_total
        readiness = max(0.0, readiness - min(0.5, soft_penalty))
        return ContextTrace(
            context_name=self.name,
            actor_id=actor.element_id,
            active_rules=traces,
            available_actions=[action.action_type for action, _, _ in available],
            harmony={action.action_type: hp.to_dict() for action, hp, _ in available},
            blockers=blockers,
            assessments=assessments,
            readiness_score=round(readiness, 4),
        )

    def _iter_contexts(self):
        cursor: Context | None = self
        while cursor is not None:
            yield cursor
            cursor = cursor.parent


class Environment:
    def __init__(self, name: str, kind: EnvironmentKind = EnvironmentKind.REACTIVE):
        self.environment_id = str(uuid.uuid4())
        self.name = name
        self.kind = kind
        self.root_context = Context(name, ContextKind.GLOBAL, SenseVector.technical("global frame", 0.25))
        self.contexts: list[Context] = []
        self.elements: dict[str, Element] = {}
        self.events: list[dict[str, Any]] = []
        self.reactions: list[ReactionRecord] = []
        self.tick = 0
        self.callbacks: dict[str, list[Callable]] = {"reaction": [], "event": []}

    async def admit(self, element: Element) -> None:
        self.elements[element.element_id] = element
        await element.on_admitted(self)
        self._emit("element.admitted", {"element_id": element.element_id, "name": element.name})

    def create_context(self, name: str, kind: ContextKind, basis: SenseVector, parent: Context | None = None) -> Context:
        ctx = Context(name, kind, basis, parent=parent or self.root_context)
        self.contexts.append(ctx)
        return ctx

    def on_reaction(self, cb: Callable[[ReactionRecord], None]) -> None:
        self.callbacks["reaction"].append(cb)

    def on_event(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self.callbacks["event"].append(cb)

    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload, "at": time.time(), "index": len(self.events)}
        self.events.append(event)
        for cb in self.callbacks["event"]:
            cb(event)

    async def dispatch(self, actor: Element, action_type: str, payload: dict[str, Any], ctx: Context, goal: str = "") -> ReactionRecord:
        request = ActionRequest(actor_id=actor.element_id, action_type=action_type, payload=payload, context_name=ctx.name, goal=goal)
        for action, _, assessment in ctx.available_actions(actor):
            if action.action_type != action_type:
                continue
            reaction = await action.execute(actor, request, ctx)
            reaction.metrics.setdefault("final_score", assessment.final_score)
            self.reactions.append(reaction)
            await actor.on_impacted(reaction, request, ctx)
            self._emit("action.executed", {"action_type": action_type, "ok": reaction.ok, "context": ctx.name, "score": assessment.final_score})
            for cb in self.callbacks["reaction"]:
                cb(reaction)
            return reaction
        reaction = ReactionRecord(action_type, ok=False, message=f"Action '{action_type}' not available in '{ctx.name}'")
        self.reactions.append(reaction)
        return reaction

    async def evolve(self) -> int:
        self.tick += 1
        for element in self.elements.values():
            await element.on_tick(self.tick)
        self._emit("environment.tick", {"tick": self.tick})
        return self.tick

    def plan(self, actor: Element, goal_sense: SenseVector, contexts: list[Context] | None = None, previous_context: Context | None = None) -> PlanningDecision | None:
        candidates: list[PlanningDecision] = []
        for ctx in contexts or self.contexts:
            trace = ctx.trace(actor, current_sense=goal_sense)
            available = ctx.available_actions(actor, current_sense=goal_sense)
            transition_cost = ctx.transition_cost_to(previous_context)
            if available:
                action, _, assessment = available[0]
                goal_distance = action.sense.angular_distance(goal_sense)
                score = assessment.final_score - transition_cost * 0.15
                candidates.append(
                    PlanningDecision(
                        context_name=ctx.name,
                        action_type=action.action_type,
                        harmony_score=round(score, 4),
                        goal_distance=round(goal_distance, 4),
                        warnings=[trace.reason for trace in assessment.warnings],
                        rationale=f"Best action in {ctx.name} for goal '{goal_sense.meaning}'",
                        transition_cost=transition_cost,
                    )
                )
            else:
                flat_blockers: list[str] = []
                for reasons in trace.blockers.values():
                    flat_blockers.extend(reasons)
                candidates.append(
                    PlanningDecision(
                        context_name=ctx.name,
                        action_type="",
                        harmony_score=-1.0,
                        goal_distance=1.0,
                        blockers=flat_blockers,
                        rationale=f"No action available in {ctx.name}",
                        transition_cost=transition_cost,
                    )
                )
        executable = [c for c in candidates if c.executable]
        if executable:
            return sorted(executable, key=lambda c: (-(c.harmony_score), c.goal_distance, c.transition_cost))[0]
        return sorted(candidates, key=lambda c: (len(c.blockers), c.goal_distance, c.transition_cost))[0] if candidates else None

    def plan_sequence(self, actor: Element, goal_sense: SenseVector, contexts: list[Context] | None = None, max_steps: int = 2) -> PlanSequence:
        ordered_contexts = contexts or self.contexts
        steps: list[PlanStep] = []
        blocked_reasons: list[str] = []
        current_goal = goal_sense
        previous_context: Context | None = None
        for step_index in range(max_steps):
            decision = self.plan(actor, current_goal, ordered_contexts, previous_context=previous_context)
            if decision is None:
                blocked_reasons.append("No contexts available")
                break
            if not decision.executable or not decision.action_type:
                blocked_reasons.extend(decision.blockers or [decision.rationale])
                break
            steps.append(PlanStep(index=step_index, context_name=decision.context_name, action_type=decision.action_type, score=decision.harmony_score, rationale=decision.rationale, transition_cost=decision.transition_cost))
            previous_context = next((ctx for ctx in ordered_contexts if ctx.name == decision.context_name), previous_context)
            current_goal = SenseVector(current_goal.dimension, f"{current_goal.meaning}:step{step_index+1}", current_goal.magnitude, current_goal.values)
        return PlanSequence(steps=steps, blocked_reasons=blocked_reasons)

    def plan_mission(self, actor: Element, objectives: list[MissionObjective], contexts: list[Context] | None = None) -> MissionPlan:
        ordered_objectives = sorted(objectives, key=lambda obj: obj.priority)
        stages: list[MissionStage] = []
        blocked: list[str] = []
        total = 0.0
        previous_context: Context | None = None
        context_pool = contexts or self.contexts
        for idx, objective in enumerate(ordered_objectives):
            pool = [ctx for ctx in context_pool if not objective.preferred_contexts or ctx.name in objective.preferred_contexts] or context_pool
            decision = self.plan(actor, objective.target_sense, pool, previous_context=previous_context)
            if decision is None or not decision.executable or not decision.action_type or decision.harmony_score < objective.success_threshold:
                blocked.append(f"{objective.objective_id}: unable to satisfy '{objective.description}'")
                continue
            stages.append(MissionStage(index=idx, objective_id=objective.objective_id, context_name=decision.context_name, action_type=decision.action_type, score=decision.harmony_score, transition_cost=decision.transition_cost, rationale=decision.rationale))
            total += decision.harmony_score
            previous_context = next((ctx for ctx in pool if ctx.name == decision.context_name), previous_context)
        return MissionPlan(mission_id=str(uuid.uuid4()), stages=stages, blocked_reasons=blocked, total_score=round(total, 4))

    def export_math(self, state_dims: list[str] | None = None) -> MathematicalEnvironmentExport:
        dims = state_dims or ["x", "y", "z", "battery", "vx", "vy", "vz", "yaw"]
        value_matrix: list[list[float]] = []
        certainty_matrix: list[list[float]] = []
        graph = SemanticGraph()
        factors: list[ConstraintFactor] = []
        factor_graph = FactorGraph()
        first_element = next(iter(self.elements.values()), None)
        for element in self.elements.values():
            value_row = [float(element.physical_state.get(dim, 0.0)) for dim in dims]
            certainty_row = [float(element.knowledge_state.get(f"{dim}_certainty", 0.0)) for dim in dims]
            value_matrix.append(value_row)
            certainty_matrix.append(certainty_row)
            graph.add_node(element.node_matrix(dims))
            for dim, value, certainty in zip(dims, value_row, certainty_row):
                factor_graph.add_variable(FactorVariable(
                    variable_id=f"{element.element_id}:{dim}",
                    value=value,
                    certainty=certainty,
                    metadata={"element_name": element.name, "dimension": dim},
                ))
            if "battery" in dims:
                battery = float(element.physical_state.get("battery", 0.0))
                factor = ConstraintFactor(
                    f"battery.safe:{element.element_id}",
                    f"Battery safety for {element.name}",
                    battery,
                    15.0,
                    weight=0.01,
                    comparator=">=",
                    variable_ids=[f"{element.element_id}:battery"],
                )
                factors.append(factor)
                factor_graph.add_factor(factor)
            if all(dim in dims for dim in ("x", "y", "z")):
                altitude = float(element.physical_state.get("z", 0.0))
                z_factor = ConstraintFactor(
                    f"altitude.floor:{element.element_id}",
                    f"Non-negative altitude for {element.name}",
                    altitude,
                    0.0,
                    weight=0.02,
                    comparator=">=",
                    variable_ids=[f"{element.element_id}:z"],
                )
                factors.append(z_factor)
                factor_graph.add_factor(z_factor)
        for context in self.contexts:
            included = [e.get("element_id") for e in context.elements if e.get("element_id")]
            if not included:
                included = list(self.elements.keys())
            readiness_energy = max(0.0, 1.0 - context.trace(first_element).readiness_score) if first_element else 0.0
            for src in included:
                for dst in included:
                    if src == dst:
                        continue
                    graph.add_edge(SemanticEdge(src, dst, context.basis, freshness=1.0, energy=readiness_energy))
            readiness_factor = ConstraintFactor(
                f"ctx.readiness:{context.name}",
                f"Context readiness for {context.name}",
                1.0 - readiness_energy,
                1.0,
                weight=0.5,
                comparator="==",
                variable_ids=[f"context:{context.name}:readiness"],
            )
            factors.append(readiness_factor)
            factor_graph.add_variable(FactorVariable(
                variable_id=f"context:{context.name}:readiness",
                value=1.0 - readiness_energy,
                certainty=1.0,
                metadata={"context": context.name},
            ))
            factor_graph.add_factor(readiness_factor)
        context_matrix = [ctx.basis.as_list() for ctx in self.contexts]
        metadata = {
            "environment_id": self.environment_id,
            "name": self.name,
            "tick": self.tick,
            "elements": len(self.elements),
            "contexts": [ctx.name for ctx in self.contexts],
            "factor_graph_variables": len(factor_graph.variables),
            "factor_graph_factors": len(factor_graph.factors),
        }
        return MathematicalEnvironmentExport(
            value_matrix=value_matrix,
            certainty_matrix=certainty_matrix,
            context_matrix=context_matrix,
            graph=graph,
            factors=factors,
            factor_graph=factor_graph,
            metadata=metadata,
        )
