from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from edp_core import Context, ContextBinding, DistributedExecutionResult, Element, Environment, MissionObjective, MultiAgentCoordinator, SenseVector, TaskSpec, MISSION_POLICY_PRESETS
from savoir_core import KnowledgeBase, SharedKnowledgeMesh

from .registry import (
    MEP_VERSION,
    DEPRECATED_ALIASES,
    build_json_schema_catalog,
    build_markdown_spec,
    build_method_descriptor,
    build_protocol_spec,
    resolve_method_alias,
)
from .spec import (
    AgentCard,
    AgentContextView,
    CapabilityCard,
    ContextBindingSpec,
    EnvironmentCard,
    KnowledgeSnapshot,
    MEPDecision,
    MEPEnvelope,
    MEPError,
    MEPMessage,
    MEPSession,
    MultiAgentEnvelope,
    MultiContextEnvelope,
    ReplayWindow,
    StateDelta,
    StreamPacket,
    WorldSnapshot,
    NeighborhoodSnapshot,
    TaskAllocationView,
    NegotiationView,
    CausalLinkView,
    DistributedExecutionView,
    ProvenanceRecord,
)


class MEPGateway:
    def __init__(self, env: Environment, knowledge: KnowledgeBase, mesh: SharedKnowledgeMesh | None = None, coordinator: MultiAgentCoordinator | None = None):
        self.env = env
        self.knowledge = knowledge
        self.mesh = mesh
        self.coordinator = coordinator or MultiAgentCoordinator(env)
        self.coordinator.auto_register()
        self._sequence = 0
        self._sessions: dict[str, MEPSession] = {}
        self._causal_links: list[dict[str, Any]] = []
        self._provenance: list[dict[str, Any]] = []
        self._last_task_view: dict[str, Any] = {}
        self.environment_id: str = str(uuid.uuid4())
        self._faults: list[dict[str, Any]] = []
        self._recovery_stats: dict[str, int] = {"injected": 0, "triggered": 0, "retried": 0, "recovered": 0, "rerouted": 0}

    def _provenance_digest(self, payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _append_provenance(self, record: ProvenanceRecord) -> dict[str, Any]:
        prev_hash = self._provenance[-1].get("record_hash", "") if self._provenance else ""
        chain_index = len(self._provenance)
        seed = {
            "record_id": record.record_id,
            "kind": record.kind,
            "agent_id": record.agent_id,
            "entity_key": record.entity_key,
            "relation": record.relation,
            "activity": record.activity,
            "context_name": record.context_name,
            "channel": record.channel,
            "derived_from": list(record.derived_from),
            "metadata": dict(record.metadata),
            "at": record.at,
            "chain_index": chain_index,
            "prev_hash": prev_hash,
            "environment_id": self.environment_id,
            "federation_id": str(record.federation_id or ""),
        }
        record.prev_hash = prev_hash
        record.chain_index = chain_index
        record.environment_id = self.environment_id
        record.record_hash = self._provenance_digest(seed)
        item = record.to_dict()
        self._provenance.append(item)
        return item

    def verify_provenance(self) -> dict[str, Any]:
        previous = ""
        errors: list[dict[str, Any]] = []
        for index, item in enumerate(self._provenance):
            seed = {
                "record_id": item.get("record_id", ""),
                "kind": item.get("kind", ""),
                "agent_id": item.get("agent_id", ""),
                "entity_key": item.get("entity_key", ""),
                "relation": item.get("relation", ""),
                "activity": item.get("activity", ""),
                "context_name": item.get("context_name", ""),
                "channel": item.get("channel", "all"),
                "derived_from": list(item.get("derived_from", [])),
                "metadata": dict(item.get("metadata", {})),
                "at": item.get("at", 0.0),
                "chain_index": item.get("chain_index", index),
                "prev_hash": item.get("prev_hash", ""),
                "environment_id": item.get("environment_id", self.environment_id),
                "federation_id": item.get("federation_id", ""),
            }
            expected = self._provenance_digest(seed)
            if item.get("prev_hash", "") != previous or item.get("record_hash", "") != expected or item.get("chain_index", index) != index:
                errors.append({"index": index, "record_id": item.get("record_id", ""), "expected_prev_hash": previous, "actual_prev_hash": item.get("prev_hash", ""), "expected_hash": expected, "actual_hash": item.get("record_hash", "")})
            previous = item.get("record_hash", "")
        return {"ok": not errors, "count": len(self._provenance), "last_hash": previous, "errors": errors}

    def inject_fault(self, scope: str, target: str, count: int = 1, message: str = "Injected fault", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        item = {"fault_id": str(uuid.uuid4()), "scope": scope, "target": target, "count": max(1, int(count)), "message": message, "metadata": dict(metadata or {})}
        self._faults.append(item)
        self._recovery_stats["injected"] += 1
        return dict(item)

    def clear_faults(self, scope: str | None = None, target: str | None = None) -> dict[str, Any]:
        before = len(self._faults)
        self._faults = [f for f in self._faults if not ((scope is None or f.get("scope") == scope) and (target is None or f.get("target") == target))]
        return {"cleared": before - len(self._faults), "remaining": len(self._faults)}

    def fault_status(self) -> dict[str, Any]:
        return {"active_faults": [dict(f) for f in self._faults], "recovery_stats": dict(self._recovery_stats)}

    def _consume_fault(self, scope: str, target: str) -> dict[str, Any] | None:
        for item in list(self._faults):
            if item.get("scope") == scope and item.get("target") == target:
                item["count"] = int(item.get("count", 1)) - 1
                self._recovery_stats["triggered"] += 1
                if item["count"] <= 0:
                    self._faults.remove(item)
                return dict(item)
        return None

    def consume_fault(self, scope: str, target: str) -> dict[str, Any] | None:
        return self._consume_fault(scope, target) or self._consume_fault(scope, "*")

    def protocol_spec(self) -> dict[str, Any]:
        spec = build_protocol_spec()
        spec["environment_kind"] = self.env.kind.value
        spec["environment_id"] = self.environment_id
        spec["supported_actions"] = sorted({action.action_type for ctx in self.env.contexts for action in ctx.actions})
        spec["contexts"] = [ctx.name for ctx in self.env.contexts]
        spec["deprecated_alias_count"] = len(DEPRECATED_ALIASES)
        return spec

    def protocol_schema(self) -> dict[str, Any]:
        schema = build_json_schema_catalog()
        schema["environment_id"] = self.environment_id
        schema["environment_kind"] = self.env.kind.value
        return schema

    def protocol_markdown(self) -> str:
        return build_markdown_spec()

    def describe_method(self, method: str) -> dict[str, Any]:
        descriptor = build_method_descriptor(method)
        canonical, alias_info = resolve_method_alias(method)
        descriptor["environment_id"] = self.environment_id
        descriptor["environment_kind"] = self.env.kind.value
        descriptor["supported_here"] = canonical in build_protocol_spec().get("categories", {}).get(descriptor.get("category", ""), []) if descriptor.get("known") else False
        if alias_info is not None:
            descriptor["deprecated_alias"] = alias_info
        return descriptor

    def health_report(self) -> dict[str, Any]:
        provenance = self.verify_provenance()
        return {
            "protocol": "MEP",
            "version": MEP_VERSION,
            "environment_id": self.environment_id,
            "environment_kind": self.env.kind.value,
            "tick": self.env.tick,
            "counts": {
                "contexts": len(self.env.contexts),
                "elements": len(self.env.elements),
                "events": len(self.env.events),
                "reactions": len(self.env.reactions),
                "knowledge_facts": len(self.knowledge.all_facts()),
                "knowledge_deltas": len(self.knowledge.deltas_since(0)),
                "causal_links": len(self._causal_links),
                "provenance_records": len(self._provenance),
                "sessions": len(self._sessions),
            },
            "mesh": {
                "enabled": self.mesh is not None,
                "agents": len(self.mesh.locals) if self.mesh is not None else 0,
                "shared_deltas": len(self.mesh.shared.deltas_since(0)) if self.mesh is not None else 0,
            },
            "provenance": provenance,
            "last_task_view": bool(self._last_task_view),
            "coordinator": {
                "channels": len(self.coordinator.channels),
                "agents": len(self.env.elements),
            },
            "faults": self.fault_status(),
            "api": {"deprecated_aliases": len(DEPRECATED_ALIASES), "schema_export": True},
        }

    def capability_card(self) -> CapabilityCard:
        return CapabilityCard(
            name="MEP",
            version=MEP_VERSION,
            features=[
                "world", "knowledge", "replay", "stream", "sessions", "mission",
                "why", "why_not", "plan", "compatibility", "multi_agent", "shared_knowledge", "multi_context", "task_allocation", "neighborhood_sync", "negotiation", "distributed_execution", "scoped_propagation", "causal_trace", "arbitration", "rollback", "provenance", "federation", "federation_routing", "mission_policy", "federation_task_resolution", "federation_task_routing", "federation_plan_resolution", "federated_execution", "federated_mission_graph", "provenance_chain", "named_mission_policies", "federated_provenance",
            ],
            streaming=True,
            replay=True,
            sessions=True,
            multi_agent=True,
            multi_context=True,
            task_allocation=True,
            neighborhood_sync=True,
            negotiation=True,
            distributed_execution=True,
            scoped_propagation=True,
            arbitration=True,
            rollback=True,
            provenance=True,
            federation=True,
            federation_routing=True,
            federated_execution=True,
            introspection=True,
            health_reporting=True,
            fault_injection=True,
            recovery_policies=["abort", "continue", "retry_once", "reroute"],
            schema_export=True,
            method_aliases=True,
        )

    def environment_card(self) -> EnvironmentCard:
        actions = sorted({action.action_type for ctx in self.env.contexts for action in ctx.actions})
        contexts = [ctx.name for ctx in self.env.contexts]
        card = EnvironmentCard(protocol="MEP", version=MEP_VERSION, environment_kind=self.env.kind.value, supported_actions=actions, contexts=contexts, mission_policies=sorted(MISSION_POLICY_PRESETS), fault_injection=True, recovery_policies=["abort", "continue", "retry_once", "reroute"], schema_export=True, method_aliases=True)
        card.subscriptions = ["world.delta", "knowledge.delta", "events", "reactions", "agent.delta", "shared.delta", "context.delta", "task.delta", "neighborhood.delta", "causal.delta", "provenance.delta", "federation.delta"]
        return card

    def open_session(self, client_id: str) -> MEPSession:
        session = MEPSession(session_id=str(uuid.uuid4()), client_id=client_id)
        self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> MEPSession | None:
        return self._sessions.get(session_id)

    def handshake(self, client_id: str) -> MEPMessage:
        session = self.open_session(client_id)
        return MEPMessage(
            message_type="session.opened",
            version=MEP_VERSION,
            body={
                "session_id": session.session_id,
                "capabilities": self.capability_card().to_dict(),
                "environment": self.environment_card().to_dict(),
            },
        )

    def resolve_context(self, context_name: str) -> Context | None:
        return next((ctx for ctx in self.env.contexts if ctx.name == context_name), None)

    def _role_of(self, actor: Element) -> str:
        return str(actor.static_properties.get("role", actor.dynamic_properties.get("role", actor.element_type)))

    def _rule_trace_to_dict(self, trace) -> dict[str, Any]:
        return {
            "rule_id": trace.rule_id,
            "description": trace.description,
            "holds": trace.holds,
            "mode": trace.mode.value,
            "role": trace.role,
            "reason": trace.reason,
            "expression": trace.expression,
            "weight": trace.weight,
            "priority": trace.priority,
            "penalty": trace.penalty,
        }

    def _assessment_to_dict(self, assessment) -> dict[str, Any] | None:
        if assessment is None:
            return None
        return {
            "base_score": assessment.base_score,
            "final_score": assessment.final_score,
            "soft_penalty": assessment.soft_penalty,
            "transition_cost": assessment.transition_cost,
            "blocked_by": [self._rule_trace_to_dict(trace) for trace in assessment.blocked_by],
            "warnings": [self._rule_trace_to_dict(trace) for trace in assessment.warnings],
        }

    def _trace_to_dict(self, trace) -> dict[str, Any]:
        return {
            "context_name": trace.context_name,
            "actor_id": trace.actor_id,
            "active_rules": [self._rule_trace_to_dict(rule) for rule in trace.active_rules],
            "available_actions": trace.available_actions,
            "harmony": trace.harmony,
            "blockers": trace.blockers,
            "assessments": {k: self._assessment_to_dict(v) for k, v in trace.assessments.items()},
            "readiness_score": trace.readiness_score,
        }

    def agent_cards(self) -> list[AgentCard]:
        self.coordinator.auto_register()
        subsystem_map: dict[str, list[str]] = {}
        for actor in self.env.elements.values():
            parent = str(actor.static_properties.get("parent_agent_id", ""))
            if parent:
                subsystem_map.setdefault(parent, []).append(actor.element_id)
        cards: list[AgentCard] = []
        for actor in self.env.elements.values():
            role = self._role_of(actor)
            cards.append(AgentCard(
                agent_id=actor.element_id,
                name=actor.name,
                element_type=actor.element_type,
                runtime_status=actor.runtime_status.value,
                channels=self.coordinator.channels_for(actor),
                capabilities=sorted({action.action_type for ctx in self.env.contexts for action in ctx.actions}),
                roles=[role] if role else [],
                parent_agent_id=str(actor.static_properties.get("parent_agent_id", "")),
                subsystem_ids=sorted(subsystem_map.get(actor.element_id, [])),
            ))
        return cards

    def _mission_preview(self, actor: Element, objectives: list[MissionObjective]) -> dict[str, Any]:
        plan = self.env.plan_mission(actor, objectives)
        return {
            "mission_id": plan.mission_id,
            "executable": plan.executable,
            "total_score": plan.total_score,
            "stages": [
                {
                    "index": stage.index,
                    "objective_id": stage.objective_id,
                    "context_name": stage.context_name,
                    "action_type": stage.action_type,
                    "score": stage.score,
                    "transition_cost": stage.transition_cost,
                    "rationale": stage.rationale,
                }
                for stage in plan.stages
            ],
            "blocked_reasons": plan.blocked_reasons,
        }

    def preview_mission(self, actor: Element, objectives: list[MissionObjective]) -> dict[str, Any]:
        return self._mission_preview(actor, objectives)

    def preview_plan(self, actor: Element, goal_sense: SenseVector, max_steps: int = 3) -> dict[str, Any]:
        sequence = self.env.plan_sequence(actor, goal_sense, max_steps=max_steps)
        return {
            "goal": {"dimension": goal_sense.dimension, "meaning": goal_sense.meaning, "magnitude": goal_sense.magnitude},
            "executable": sequence.executable,
            "steps": [
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
            "blocked_reasons": sequence.blocked_reasons,
        }

    def preview_multi_plan(self, actors: list[Element], goal_sense: SenseVector, max_steps: int = 2, channel: str = "all") -> dict[str, Any]:
        return self.coordinator.preview_plan(actors, goal_sense, max_steps=max_steps, channel=channel).to_dict()

    def preview_multi_context_plan(self, bindings: list[ContextBinding], goal_sense: SenseVector, max_steps: int = 2) -> dict[str, Any]:
        return self.coordinator.preview_contextual_plan(bindings, goal_sense, max_steps=max_steps).to_dict()

    def explain(self, actor: Element, ctx: Context, action_type: str | None = None) -> dict[str, Any]:
        trace = ctx.trace(actor)
        result: dict[str, Any] = {"trace": self._trace_to_dict(trace)}
        if action_type is not None:
            explanations = ctx.explain_action(actor, action_type)
            assessment = trace.assessments.get(action_type)
            result["action"] = {
                "action_type": action_type,
                "available": action_type in trace.available_actions,
                "explanation": explanations,
                "assessment": self._assessment_to_dict(assessment),
                "harmony": trace.harmony.get(action_type),
            }
        return result

    def explain_why_not(self, actor: Element, ctx: Context, action_type: str) -> dict[str, Any]:
        trace = ctx.trace(actor)
        assessment = trace.assessments.get(action_type)
        blockers = ctx.explain_action(actor, action_type)
        return {
            "action_type": action_type,
            "available": action_type in trace.available_actions,
            "blockers": blockers,
            "assessment": self._assessment_to_dict(assessment),
            "readiness_score": trace.readiness_score,
        }

    def _knowledge_snapshot_for_actor(self, actor: Element, knowledge_prefix: str | None = None) -> KnowledgeSnapshot:
        if self.mesh is not None and hasattr(actor, "drone_id"):
            view = self.mesh.agent_view(getattr(actor, "drone_id"), prefix=knowledge_prefix)
            return KnowledgeSnapshot(
                facts=view.local_facts,
                expected=self.mesh.local(getattr(actor, "drone_id")).expected_world(knowledge_prefix),
                revalidation=self.mesh.local(getattr(actor, "drone_id")).revalidation_queue(knowledge_prefix),
                constraints=self.mesh.local(getattr(actor, "drone_id")).constraint_report(knowledge_prefix),
                tension=view.local_tension,
                agent_id=getattr(actor, "drone_id"),
                local_facts=view.local_facts,
                shared_facts=view.shared_facts,
            )
        return KnowledgeSnapshot(
            facts=[
                {
                    "key": fact.key,
                    "value": fact.value,
                    "certainty": fact.certainty.name,
                    "status": fact.status.value,
                    "source": fact.source,
                    "expected_value": fact.expected_value,
                }
                for fact in self.knowledge.all_facts(prefix=knowledge_prefix)
            ],
            expected=self.knowledge.expected_world(prefix=knowledge_prefix),
            revalidation=self.knowledge.revalidation_queue(prefix=knowledge_prefix),
            constraints=self.knowledge.constraint_report(prefix=knowledge_prefix),
            tension=self.knowledge.knowledge_tension(prefix=knowledge_prefix),
        )

    def _world_snapshot(self, actor: Element, ctx: Context, mission_objectives: list[MissionObjective] | None = None) -> WorldSnapshot:
        trace = ctx.trace(actor)
        return WorldSnapshot(
            context_name=ctx.name,
            situation={
                "environment": self.env.name,
                "tick": self.env.tick,
                "elements": len(self.env.elements),
                "contexts": len(self.env.contexts),
                "readiness_score": trace.readiness_score,
                "channels": self.coordinator.channels_for(actor),
                "role": self._role_of(actor),
                "parent_agent_id": str(actor.static_properties.get("parent_agent_id", "")),
            },
            actions=[
                {
                    **hp.to_dict(),
                    "assessment": self._assessment_to_dict(assessment),
                    "action_type": action.action_type,
                    "blockers": ctx.explain_action(actor, action.action_type),
                }
                for action, hp, assessment in ctx.available_actions(actor)
            ],
            rules=[self._rule_trace_to_dict(rule) for rule in trace.active_rules],
            recent_events=self.env.events[-5:],
            math_export=self.env.export_math().to_dict(),
            mission=(self._mission_preview(actor, mission_objectives) if mission_objectives else {}),
        )



    def _tasks_from_dicts(self, items: list[dict[str, Any]]) -> list[TaskSpec]:
        tasks: list[TaskSpec] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            tasks.append(TaskSpec(
                task_id=str(item.get("task_id", f"task-{idx}")),
                description=str(item.get("description", f"task-{idx}")),
                goal_dimension=str(item.get("goal_dimension", "technical")),
                goal_meaning=str(item.get("goal_meaning", item.get("description", f"task-{idx}"))),
                goal_magnitude=float(item.get("goal_magnitude", 0.8)),
                required_roles=list(item.get("required_roles", [])),
                preferred_contexts=list(item.get("preferred_contexts", [])),
                target_agent_ids=list(item.get("target_agent_ids", [])),
                depends_on=list(item.get("depends_on", [])),
                channel=str(item.get("channel", "all")),
                payload=dict(item.get("payload", {})),
                mission_policy=dict(item.get("mission_policy", {})),
                preferred_environment_tags=list(item.get("preferred_environment_tags", [])),
            ))
        return tasks

    def neighborhood_snapshot(self, agent: Element, knowledge_prefix: str | None = None) -> NeighborhoodSnapshot:
        if self.mesh is None or not hasattr(agent, 'drone_id'):
            return NeighborhoodSnapshot(agent_id=agent.element_id, neighbors=[], visible_facts=[])
        snapshot = self.mesh.neighborhood_snapshot(getattr(agent, 'drone_id'), prefix=knowledge_prefix)
        return NeighborhoodSnapshot(**snapshot)

    def assign_multi_tasks(self, bindings: list[ContextBinding], tasks: list[dict[str, Any]] | list[TaskSpec], neighborhood_radius: float = 8.0) -> TaskAllocationView:
        parsed_tasks = tasks if tasks and isinstance(tasks[0], TaskSpec) else self._tasks_from_dicts(tasks) if tasks else []
        plan = self.coordinator.assign_tasks(bindings, parsed_tasks, neighborhood_radius=neighborhood_radius)
        self._last_task_view = plan.to_dict()
        return TaskAllocationView(
            channel=plan.channel,
            tasks=[task.to_dict() for task in plan.tasks],
            assignments=[assignment.to_dict() for assignment in plan.assignments],
            dependency_layers=plan.dependency_layers,
            unmet_tasks=plan.unmet_tasks,
            neighborhood_map=plan.neighborhood_map,
            coordination_energy=plan.coordination_energy,
        )


    def negotiate_multi_task(self, bindings: list[ContextBinding], task: dict[str, Any] | TaskSpec) -> NegotiationView:
        parsed = task if isinstance(task, TaskSpec) else self._tasks_from_dicts([task])[0]
        result = self.coordinator.negotiate_task(bindings, parsed)
        if result.arbitration:
            self._append_provenance(ProvenanceRecord(
                record_id=str(uuid.uuid4()),
                kind='arbitration',
                agent_id=result.winner.get('agent_id', '') if result.winner else '',
                entity_key=parsed.task_id,
                relation='selected',
                activity='task.arbitration',
                context_name=result.winner.get('context_name', '') if result.winner else '',
                channel=result.winner.get('channel', 'all') if result.winner else 'all',
                derived_from=[bid.agent_id for bid in result.bids[:2]],
                metadata=result.arbitration,
            ))
        scoring = {"mode": "multi_criteria", "terms": ["base", "channel_bonus", "role_bonus", "context_bonus", "locality_bonus", "certainty_bonus", "load_penalty", "risk_penalty"]}
        return NegotiationView(task=result.task, winner=result.winner, bids=[bid.to_dict() for bid in result.bids], unresolved_reasons=result.unresolved_reasons, arbitration=result.arbitration, scoring=scoring)

    def causal_trace(self, agent_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        items = self._causal_links
        if agent_id is not None:
            items = [item for item in items if item.get('from_id') == agent_id or item.get('to_id') == agent_id]
        if limit is not None:
            items = items[-limit:]
        return items

    def provenance_trace(self, agent_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        items = self._provenance
        if agent_id is not None:
            items = [item for item in items if item.get('agent_id') == agent_id]
        if limit is not None:
            items = items[-limit:]
        return items

    def propagate_knowledge(self, agent: Element, key: str, channels: list[str] | None = None, max_hops: int = 1, include_shared: bool = False, shared_key: str | None = None) -> dict[str, Any]:
        if self.mesh is None or not hasattr(agent, 'drone_id'):
            return {'propagated': False, 'reason': 'mesh unavailable'}
        self.mesh.publish_scoped(getattr(agent, 'drone_id'), key, shared_key=shared_key, channels=channels, max_hops=max_hops, include_shared=include_shared)
        snapshot = self.mesh.neighborhood_snapshot(getattr(agent, 'drone_id'), prefix=shared_key or key, channels=channels, max_hops=max_hops)
        self._append_provenance(ProvenanceRecord(
            record_id=str(uuid.uuid4()),
            kind='knowledge',
            agent_id=agent.element_id,
            entity_key=shared_key or key,
            relation='propagated',
            activity='knowledge.publish_scoped',
            context_name='',
            channel=','.join(channels or ['all']),
            derived_from=[key],
            metadata={'max_hops': max_hops, 'include_shared': include_shared},
        ))
        return {'propagated': True, 'key': key, 'channels': channels or ['all'], 'max_hops': max_hops, 'include_shared': include_shared, 'snapshot': snapshot}

    def _infer_compensation(self, actor: Element, assignment: Any, task: TaskSpec, before_state: dict[str, Any]) -> tuple[str, dict[str, Any]] | None:
        payload = dict(task.payload)
        explicit = payload.get('compensate')
        if isinstance(explicit, dict) and explicit.get('action_type'):
            return str(explicit['action_type']), dict(explicit.get('payload', {}))
        if assignment.action_type == 'drone.move':
            return 'drone.move', {
                'dx': -float(payload.get('dx', 0.0)),
                'dy': -float(payload.get('dy', 0.0)),
                'dz': -float(payload.get('dz', 0.0)),
            }
        if assignment.action_type == 'drone.takeoff':
            return 'drone.land', {}
        if assignment.action_type == 'drone.goto':
            return 'drone.goto', {
                'x': float(before_state.get('x', 0.0)),
                'y': float(before_state.get('y', 0.0)),
                'z': float(before_state.get('z', 0.0)),
            }
        return None

    async def execute_multi_tasks(self, bindings: list[ContextBinding], tasks: list[dict[str, Any]] | list[TaskSpec], session: MEPSession | None = None, initiator: str = 'coordinator', neighborhood_radius: float = 8.0, rollback_policy: str = "full", recovery_policy: str = "abort") -> DistributedExecutionView:
        parsed_tasks = tasks if tasks and isinstance(tasks[0], TaskSpec) else self._tasks_from_dicts(tasks) if tasks else []
        plan = self.coordinator.assign_tasks(bindings, parsed_tasks, neighborhood_radius=neighborhood_radius)
        self._last_task_view = plan.to_dict()
        assignment_map = {assignment.task_id: assignment for assignment in plan.assignments}
        task_map = {task.task_id: task for task in plan.tasks}
        executed: list[dict[str, Any]] = []
        blocked = list(plan.unmet_tasks)
        causal_links: list[dict[str, Any]] = []
        compensations: list[dict[str, Any]] = []
        executed_stack: list[tuple[Any, Any, Any, dict[str, Any], Any]] = []
        failed_task_ids: list[str] = []
        retried_task_ids: list[str] = []
        recovered_task_ids: list[str] = []
        rolled_back = False
        failure_detected = False

        from edp_core import ReactionRecord

        for layer in plan.dependency_layers:
            if failure_detected and recovery_policy == 'abort':
                break
            for task_id in layer:
                assignment = assignment_map.get(task_id)
                if assignment is None:
                    continue
                task = task_map.get(task_id)
                if task is None:
                    continue
                if any(dep in failed_task_ids for dep in assignment.depends_on):
                    blocked.append({'task_id': task_id, 'reason': 'dependency failed', 'depends_on': list(assignment.depends_on)})
                    failed_task_ids.append(task_id)
                    continue
                actor = self.env.elements.get(assignment.agent_id)
                ctx = self.resolve_context(assignment.context_name)
                if actor is None or ctx is None:
                    blocked.append({'task_id': task_id, 'reason': 'missing actor/context/task'})
                    failed_task_ids.append(task_id)
                    if recovery_policy == 'abort':
                        failure_detected = True
                        break
                    continue
                before_state = dict(actor.physical_state)

                fault = self.consume_fault('task', task_id) or self.consume_fault('action', assignment.action_type) or self.consume_fault('agent', assignment.agent_id)
                if fault is not None:
                    reaction = ReactionRecord(assignment.action_type, ok=False, message=str(fault.get('message', 'Injected fault')), metrics={'fault_injected': True, 'fault_scope': fault.get('scope', ''), 'fault_target': fault.get('target', '')})
                else:
                    reaction = await self.env.dispatch(actor, assignment.action_type, dict(task.payload), ctx, goal=task.description)

                if (not reaction.ok) and recovery_policy == 'retry_once':
                    retried_task_ids.append(task_id)
                    self._recovery_stats['retried'] += 1
                    retry_fault = self.consume_fault('task_retry', task_id)
                    if retry_fault is not None:
                        reaction = ReactionRecord(assignment.action_type, ok=False, message=str(retry_fault.get('message', 'Injected retry fault')), metrics={'fault_injected': True, 'fault_scope': retry_fault.get('scope', ''), 'fault_target': retry_fault.get('target', '')})
                    else:
                        reaction = await self.env.dispatch(actor, assignment.action_type, dict(task.payload), ctx, goal=f'{task.description}:retry')
                    if reaction.ok:
                        recovered_task_ids.append(task_id)
                        self._recovery_stats['recovered'] += 1

                executed_item = {
                    'task_id': task_id,
                    'agent_id': assignment.agent_id,
                    'actor_name': assignment.actor_name,
                    'context_name': assignment.context_name,
                    'action_type': assignment.action_type,
                    'ok': reaction.ok,
                    'message': reaction.message,
                    'depends_on': list(assignment.depends_on),
                    'role': assignment.role,
                    'channel': plan.channel,
                    'metrics': dict(getattr(reaction, 'metrics', {}) or {}),
                }
                executed.append(executed_item)
                link = CausalLinkView(
                    link_id=str(uuid.uuid4()),
                    task_id=task_id,
                    from_id=initiator,
                    to_id=assignment.agent_id,
                    context_name=assignment.context_name,
                    action_type=assignment.action_type,
                    channel=plan.channel,
                    depends_on=list(assignment.depends_on),
                    ok=reaction.ok,
                    metadata={'actor_name': assignment.actor_name, 'role': assignment.role, 'message': reaction.message, 'recovery_policy': recovery_policy},
                ).to_dict()
                causal_links.append(link)
                self._causal_links.append(link)
                self._append_provenance(ProvenanceRecord(
                    record_id=str(uuid.uuid4()),
                    kind='execution',
                    agent_id=assignment.agent_id,
                    entity_key=task_id,
                    relation='executed' if reaction.ok else 'failed',
                    activity=assignment.action_type,
                    context_name=assignment.context_name,
                    channel=plan.channel,
                    derived_from=list(assignment.depends_on),
                    metadata={'message': reaction.message, 'initiator': initiator, 'recovery_policy': recovery_policy},
                ))
                if reaction.ok:
                    executed_stack.append((actor, ctx, assignment, before_state, task))
                else:
                    blocked.append({'task_id': task_id, 'reason': reaction.message})
                    failed_task_ids.append(task_id)
                    if recovery_policy == 'abort':
                        failure_detected = True
                        break

        if failure_detected and executed_stack and rollback_policy != 'none':
            if rollback_policy == 'layer' and failed_task_ids:
                failed_set = set(failed_task_ids)
                current_layer = next((set(layer) for layer in plan.dependency_layers if any(tid in failed_set for tid in layer)), set())
                rollback_stack = [item for item in executed_stack if item[2].task_id in current_layer]
            else:
                rollback_stack = list(executed_stack)
            if rollback_stack:
                rolled_back = True
            for actor, ctx, assignment, before_state, task in reversed(rollback_stack):
                comp = self._infer_compensation(actor, assignment, task, before_state)
                if comp is None:
                    compensations.append({'task_id': assignment.task_id, 'agent_id': assignment.agent_id, 'action_type': '', 'ok': False, 'message': 'no compensation available', 'payload': {}})
                    continue
                action_type, payload = comp
                reaction = await self.env.dispatch(actor, action_type, payload, ctx, goal=f'compensate:{assignment.task_id}')
                comp_item = {'task_id': assignment.task_id, 'agent_id': assignment.agent_id, 'action_type': action_type, 'ok': reaction.ok, 'message': reaction.message, 'payload': payload, 'rollback_policy': rollback_policy}
                compensations.append(comp_item)
                self._append_provenance(ProvenanceRecord(
                    record_id=str(uuid.uuid4()),
                    kind='compensation',
                    agent_id=assignment.agent_id,
                    entity_key=assignment.task_id,
                    relation='compensated',
                    activity=action_type,
                    context_name=assignment.context_name,
                    channel=plan.channel,
                    derived_from=[assignment.task_id],
                    metadata={'payload': payload, 'ok': reaction.ok, 'rollback_policy': rollback_policy},
                ))
        if session is not None:
            session.record({'multi_execute': True, 'executed': executed, 'blocked': blocked, 'layers': plan.dependency_layers, 'compensations': compensations, 'rolled_back': rolled_back, 'rollback_policy': rollback_policy, 'recovery_policy': recovery_policy, 'retried_task_ids': retried_task_ids, 'recovered_task_ids': recovered_task_ids})
        return DistributedExecutionView(channel=plan.channel, layers=plan.dependency_layers, executed=executed, blocked=blocked, causal_links=causal_links, compensations=compensations, rolled_back=rolled_back, failed_task_ids=failed_task_ids, rollback_policy=rollback_policy, recovery_policy=recovery_policy, retried_task_ids=retried_task_ids, recovered_task_ids=recovered_task_ids)

    def build_envelope(self, actor: Element, ctx: Context, session: MEPSession | None = None, knowledge_prefix: str | None = None, mission_objectives: list[MissionObjective] | None = None) -> MEPEnvelope:
        world = self._world_snapshot(actor, ctx, mission_objectives)
        knowledge = self._knowledge_snapshot_for_actor(actor, knowledge_prefix)
        attention = [rule["description"] for rule in world.rules if not rule["holds"] and rule["role"] == "enabler"]
        attention.extend(f"revalidate:{item['key']}" for item in knowledge.revalidation)
        if session is not None:
            session.record({"context": ctx.name, "attention": attention, "tick": self.env.tick, "actor_id": actor.element_id})
        return MEPEnvelope(
            envelope_id=str(uuid.uuid4()),
            protocol="MEP",
            version=MEP_VERSION,
            actor_id=actor.element_id,
            world=world,
            knowledge=knowledge,
            attention=attention,
        )

    def build_shared_envelope(self, actors: list[Element], ctx: Context, session: MEPSession | None = None, knowledge_prefix: str | None = None, goal_sense: SenseVector | None = None) -> MultiAgentEnvelope:
        goal = goal_sense or SenseVector.technical("coordinate", 0.7)
        world = WorldSnapshot(
            context_name=ctx.name,
            situation={
                "environment": self.env.name,
                "tick": self.env.tick,
                "elements": len(self.env.elements),
                "contexts": len(self.env.contexts),
                "agent_count": len(actors),
            },
            actions=[],
            rules=[],
            recent_events=self.env.events[-10:],
            math_export=self.env.export_math().to_dict(),
        )
        agent_views = []
        for actor in actors:
            trace = ctx.trace(actor)
            agent_views.append({
                "agent_id": actor.element_id,
                "name": actor.name,
                "channels": self.coordinator.channels_for(actor),
                "role": self._role_of(actor),
                "parent_agent_id": str(actor.static_properties.get("parent_agent_id", "")),
                "trace": self._trace_to_dict(trace),
                "knowledge": self._knowledge_snapshot_for_actor(actor, knowledge_prefix).to_dict(),
            })
        shared = self.mesh.shared_snapshot(knowledge_prefix) if self.mesh is not None else {
            "facts": [
                {"key": fact.key, "value": fact.value, "certainty": fact.certainty.name, "status": fact.status.value, "source": fact.source}
                for fact in self.knowledge.all_facts(prefix=knowledge_prefix)
            ],
            "expected": self.knowledge.expected_world(knowledge_prefix),
            "revalidation": self.knowledge.revalidation_queue(knowledge_prefix),
            "constraints": self.knowledge.constraint_report(knowledge_prefix),
            "tension": self.knowledge.knowledge_tension(knowledge_prefix),
        }
        coordination = self.preview_multi_plan(actors, goal, max_steps=2)
        if session is not None:
            session.record({"context": ctx.name, "shared": True, "tick": self.env.tick, "agents": [actor.element_id for actor in actors]})
        return MultiAgentEnvelope(
            envelope_id=str(uuid.uuid4()),
            protocol="MEP",
            version=MEP_VERSION,
            context_name=ctx.name,
            agent_ids=[actor.element_id for actor in actors],
            world=world,
            shared_knowledge=shared,
            agent_views=agent_views,
            coordination=coordination,
        )

    def build_multi_context_envelope(self, bindings: list[ContextBinding], session: MEPSession | None = None, knowledge_prefix: str | None = None, goal_sense: SenseVector | None = None) -> MultiContextEnvelope:
        goal = goal_sense or SenseVector.technical("coordinate across contexts", 0.72)
        worlds: list[WorldSnapshot] = []
        agent_views: list[AgentContextView] = []
        binding_specs: list[ContextBindingSpec] = []
        for binding in bindings:
            actor = self.env.elements.get(binding.agent_id)
            ctx = self.resolve_context(binding.context_name)
            if actor is None or ctx is None:
                continue
            worlds.append(self._world_snapshot(actor, ctx))
            agent_views.append(AgentContextView(
                agent_id=actor.element_id,
                name=actor.name,
                context_name=ctx.name,
                trace=self._trace_to_dict(ctx.trace(actor)),
                knowledge=self._knowledge_snapshot_for_actor(actor, knowledge_prefix).to_dict(),
                channels=self.coordinator.channels_for(actor),
                role=binding.role or self._role_of(actor),
                parent_agent_id=binding.parent_agent_id or str(actor.static_properties.get("parent_agent_id", "")),
            ))
            binding_specs.append(ContextBindingSpec(**binding.to_dict()))
        shared = self.mesh.shared_snapshot(knowledge_prefix) if self.mesh is not None else {
            "facts": [
                {"key": fact.key, "value": fact.value, "certainty": fact.certainty.name, "status": fact.status.value, "source": fact.source}
                for fact in self.knowledge.all_facts(prefix=knowledge_prefix)
            ],
            "expected": self.knowledge.expected_world(knowledge_prefix),
            "revalidation": self.knowledge.revalidation_queue(knowledge_prefix),
            "constraints": self.knowledge.constraint_report(knowledge_prefix),
            "tension": self.knowledge.knowledge_tension(knowledge_prefix),
        }
        coordination = self.preview_multi_context_plan(bindings, goal_sense=goal, max_steps=2)
        if session is not None:
            session.record({"multi_context": True, "bindings": [b.to_dict() for b in binding_specs], "tick": self.env.tick})
        return MultiContextEnvelope(
            envelope_id=str(uuid.uuid4()),
            protocol="MEP",
            version=MEP_VERSION,
            bindings=binding_specs,
            worlds=worlds,
            shared_knowledge=shared,
            agent_views=agent_views,
            coordination=coordination,
        )

    def build_message(self, message_type: str, body: dict[str, Any]) -> MEPMessage:
        return MEPMessage(message_type=message_type, version=MEP_VERSION, body=body)

    def build_delta(self, since_event_count: int = 0, since_knowledge_offset: int = 0) -> StateDelta:
        self._sequence += 1
        return StateDelta(
            sequence_id=self._sequence,
            event_count=len(self.env.events) - since_event_count,
            knowledge_deltas=self.knowledge.deltas_since(since_knowledge_offset),
            reaction_count=len(self.env.reactions),
        )

    def build_replay_window(self, from_event_index: int = 0) -> ReplayWindow:
        events = self.env.events[from_event_index:]
        reactions = [
            {
                "action_type": reaction.action_type,
                "ok": reaction.ok,
                "message": reaction.message,
                "created_at": reaction.created_at,
                "metrics": reaction.metrics,
            }
            for reaction in self.env.reactions[max(0, from_event_index - 1):]
        ]
        return ReplayWindow(
            from_event_index=from_event_index,
            to_event_index=len(self.env.events),
            events=events,
            reactions=reactions,
            knowledge_deltas=self.knowledge.deltas_since(from_event_index),
        )

    def stream_packet(self, channel: str, payload: dict[str, Any]) -> StreamPacket:
        self._sequence += 1
        return StreamPacket(channel=channel, sequence_id=self._sequence, payload=payload)

    def poll_updates(self, session: MEPSession) -> list[StreamPacket]:
        packets: list[StreamPacket] = []
        for channel, subscription in session.subscriptions.items():
            if channel == "events":
                new_items = self.env.events[subscription.cursor:]
                if new_items:
                    packets.append(self.stream_packet(channel, {"items": new_items}))
                    subscription.cursor = len(self.env.events)
            elif channel == "reactions":
                new_items = [
                    {"action_type": reaction.action_type, "ok": reaction.ok, "message": reaction.message, "metrics": reaction.metrics}
                    for reaction in self.env.reactions[subscription.cursor:]
                ]
                if new_items:
                    packets.append(self.stream_packet(channel, {"items": new_items}))
                    subscription.cursor = len(self.env.reactions)
            elif channel == "knowledge.delta":
                new_items = self.knowledge.deltas_since(subscription.cursor)
                if new_items:
                    packets.append(self.stream_packet(channel, {"items": new_items}))
                    subscription.cursor = len(self.knowledge.deltas_since(0))
            elif channel == "shared.delta" and self.mesh is not None:
                new_items = self.mesh.shared.deltas_since(subscription.cursor)
                if new_items:
                    packets.append(self.stream_packet(channel, {"items": new_items}))
                    subscription.cursor = len(self.mesh.shared.deltas_since(0))
            elif channel == "agent.delta":
                packets.append(self.stream_packet(channel, {"items": [card.to_dict() for card in self.agent_cards()]}))
                subscription.cursor += 1
            elif channel == "context.delta":
                packets.append(self.stream_packet(channel, {"contexts": [ctx.name for ctx in self.env.contexts], "tick": self.env.tick}))
                subscription.cursor += 1
            elif channel == "task.delta":
                if self._last_task_view:
                    packets.append(self.stream_packet(channel, self._last_task_view))
                    subscription.cursor += 1
            elif channel == "neighborhood.delta" and self.mesh is not None:
                packets.append(self.stream_packet(channel, {'neighbors': {agent_id: self.mesh.neighbors_of(agent_id) for agent_id in sorted(self.mesh.locals)}}))
                subscription.cursor += 1
            elif channel == "causal.delta":
                new_items = self._causal_links[subscription.cursor:]
                if new_items:
                    packets.append(self.stream_packet(channel, {'items': new_items}))
                    subscription.cursor = len(self._causal_links)
            elif channel == "provenance.delta":
                new_items = self._provenance[subscription.cursor:]
                if new_items:
                    packets.append(self.stream_packet(channel, {'items': new_items}))
                    subscription.cursor = len(self._provenance)
            elif channel == "world.delta":
                delta = self.build_delta(since_event_count=subscription.cursor, since_knowledge_offset=subscription.cursor)
                if delta.event_count or delta.knowledge_deltas:
                    packets.append(self.stream_packet(channel, delta.to_dict()))
                    subscription.cursor = len(self.env.events)
        return packets

    def validate_decision(self, actor: Element, ctx: Context, decision: MEPDecision) -> MEPError | None:
        if decision.decision not in {"execute", "skip", "query", "observe"}:
            return MEPError("invalid.decision", f"Unsupported decision '{decision.decision}'")
        if decision.decision != "execute":
            return None
        if not decision.action_type:
            return MEPError("invalid.action", "Missing action_type for execute decision")
        available_types = {a.action_type for a, _, _ in ctx.available_actions(actor)}
        if decision.action_type not in available_types:
            return MEPError(
                "action.unavailable",
                f"Action '{decision.action_type}' is not available in context '{ctx.name}'",
                details={"why_not": ctx.explain_action(actor, decision.action_type)},
            )
        return None

    async def execute_decision(self, actor: Element, ctx: Context, decision: MEPDecision, session: MEPSession | None = None):
        error = self.validate_decision(actor, ctx, decision)
        if error is not None:
            return error
        if decision.decision != "execute":
            return self.build_message("decision.skipped", {"decision": decision.to_dict()})
        reaction = await self.env.dispatch(actor, decision.action_type, decision.payload, ctx, goal=decision.reasoning)
        if session is not None:
            session.record({"decision": decision.to_dict(), "reaction": {"ok": reaction.ok, "action_type": reaction.action_type}})
        return self.build_message(
            "decision.executed",
            {
                "decision": decision.to_dict(),
                "reaction": {
                    "ok": reaction.ok,
                    "message": reaction.message,
                    "action_type": reaction.action_type,
                    "metrics": reaction.metrics,
                },
            },
        )
