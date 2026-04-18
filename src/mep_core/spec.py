from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CapabilityCard:
    name: str
    version: str
    features: list[str]
    transport: list[str] = field(default_factory=lambda: ["json-rpc", "inproc", "stream"])
    streaming: bool = False
    replay: bool = False
    sessions: bool = False
    multi_agent: bool = False
    multi_context: bool = False
    task_allocation: bool = False
    neighborhood_sync: bool = False
    negotiation: bool = False
    distributed_execution: bool = False
    scoped_propagation: bool = False
    arbitration: bool = False
    rollback: bool = False
    provenance: bool = False
    federation: bool = False
    federation_routing: bool = False
    federated_execution: bool = False
    federated_mission_graph: bool = False
    provenance_chain: bool = False
    introspection: bool = False
    health_reporting: bool = False
    fault_injection: bool = False
    recovery_policies: list[str] = field(default_factory=list)
    schema_export: bool = False
    method_aliases: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "features": self.features,
            "transport": self.transport,
            "streaming": self.streaming,
            "replay": self.replay,
            "sessions": self.sessions,
            "multi_agent": self.multi_agent,
            "multi_context": self.multi_context,
            "task_allocation": self.task_allocation,
            "neighborhood_sync": self.neighborhood_sync,
            "negotiation": self.negotiation,
            "distributed_execution": self.distributed_execution,
            "scoped_propagation": self.scoped_propagation,
            "arbitration": self.arbitration,
            "rollback": self.rollback,
            "provenance": self.provenance,
            "federation": self.federation,
            "federation_routing": self.federation_routing,
            "federated_mission_graph": self.federated_mission_graph,
            "provenance_chain": self.provenance_chain,
            "introspection": self.introspection,
            "health_reporting": self.health_reporting,
            "fault_injection": self.fault_injection,
            "recovery_policies": self.recovery_policies,
            "schema_export": self.schema_export,
            "method_aliases": self.method_aliases,
        }


@dataclass(slots=True)
class EnvironmentCard:
    protocol: str
    version: str
    environment_kind: str
    supported_actions: list[str]
    contexts: list[str]
    certainty_model: str = "savoir-v5"
    causal_trace: bool = True
    world_export: bool = True
    decision_validation: bool = True
    replay_window: bool = True
    sessions: bool = True
    agents: bool = True
    shared_knowledge: bool = True
    multi_context: bool = True
    task_allocation: bool = True
    neighborhood_sync: bool = True
    negotiation: bool = True
    distributed_execution: bool = True
    scoped_propagation: bool = True
    arbitration: bool = True
    rollback: bool = True
    provenance: bool = True
    federation: bool = True
    federation_routing: bool = True
    federated_mission_graph: bool = True
    provenance_chain: bool = True
    introspection: bool = True
    health_reporting: bool = True
    fault_injection: bool = True
    recovery_policies: list[str] = field(default_factory=lambda: ["abort", "continue", "retry_once", "reroute"])
    schema_export: bool = True
    method_aliases: bool = True
    mission_policies: list[str] = field(default_factory=lambda: ["balanced", "risk_averse", "certainty_first", "locality_first", "throughput", "emergency", "stealth"])
    subscriptions: list[str] = field(default_factory=lambda: ["world.delta", "knowledge.delta", "events", "reactions", "agent.delta", "shared.delta", "context.delta", "task.delta", "neighborhood.delta", "provenance.delta", "federation.delta"])

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "version": self.version,
            "environment_kind": self.environment_kind,
            "supported_actions": self.supported_actions,
            "contexts": self.contexts,
            "certainty_model": self.certainty_model,
            "causal_trace": self.causal_trace,
            "world_export": self.world_export,
            "decision_validation": self.decision_validation,
            "replay_window": self.replay_window,
            "sessions": self.sessions,
            "agents": self.agents,
            "shared_knowledge": self.shared_knowledge,
            "multi_context": self.multi_context,
            "task_allocation": self.task_allocation,
            "neighborhood_sync": self.neighborhood_sync,
            "negotiation": self.negotiation,
            "distributed_execution": self.distributed_execution,
            "scoped_propagation": self.scoped_propagation,
            "arbitration": self.arbitration,
            "rollback": self.rollback,
            "provenance": self.provenance,
            "federation": self.federation,
            "federation_routing": self.federation_routing,
            "federated_mission_graph": self.federated_mission_graph,
            "provenance_chain": self.provenance_chain,
            "introspection": self.introspection,
            "health_reporting": self.health_reporting,
            "fault_injection": self.fault_injection,
            "recovery_policies": self.recovery_policies,
            "schema_export": self.schema_export,
            "method_aliases": self.method_aliases,
            "mission_policies": self.mission_policies,
            "subscriptions": self.subscriptions,
        }


@dataclass(slots=True)
class AgentCard:
    agent_id: str
    name: str
    element_type: str
    runtime_status: str
    channels: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    parent_agent_id: str = ""
    subsystem_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "agent_id": self.agent_id,
            "name": self.name,
            "element_type": self.element_type,
            "runtime_status": self.runtime_status,
            "channels": self.channels,
            "capabilities": self.capabilities,
            "roles": self.roles,
            "subsystem_ids": self.subsystem_ids,
        }
        if self.parent_agent_id:
            payload["parent_agent_id"] = self.parent_agent_id
        return payload


@dataclass(slots=True)
class WorldSnapshot:
    context_name: str
    situation: dict[str, Any]
    actions: list[dict[str, Any]]
    rules: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]
    math_export: dict[str, Any]
    mission: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_name": self.context_name,
            "situation": self.situation,
            "actions": self.actions,
            "rules": self.rules,
            "recent_events": self.recent_events,
            "math_export": self.math_export,
            "mission": self.mission,
        }


@dataclass(slots=True)
class KnowledgeSnapshot:
    facts: list[dict[str, Any]]
    expected: list[dict[str, Any]] = field(default_factory=list)
    revalidation: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, Any]] = field(default_factory=list)
    tension: float = 0.0
    agent_id: str = ""
    local_facts: list[dict[str, Any]] = field(default_factory=list)
    shared_facts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "facts": self.facts,
            "expected": self.expected,
            "revalidation": self.revalidation,
            "constraints": self.constraints,
            "tension": self.tension,
        }
        if self.agent_id:
            payload["agent_id"] = self.agent_id
        if self.local_facts:
            payload["local_facts"] = self.local_facts
        if self.shared_facts:
            payload["shared_facts"] = self.shared_facts
        return payload


@dataclass(slots=True)
class AgentContextView:
    agent_id: str
    name: str
    context_name: str
    trace: dict[str, Any]
    knowledge: dict[str, Any]
    channels: list[str] = field(default_factory=list)
    role: str = ""
    parent_agent_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "agent_id": self.agent_id,
            "name": self.name,
            "context_name": self.context_name,
            "trace": self.trace,
            "knowledge": self.knowledge,
            "channels": self.channels,
            "role": self.role,
        }
        if self.parent_agent_id:
            payload["parent_agent_id"] = self.parent_agent_id
        return payload


@dataclass(slots=True)
class ContextBindingSpec:
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
class NeighborhoodSnapshot:
    agent_id: str
    neighbors: list[str] = field(default_factory=list)
    visible_facts: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"agent_id": self.agent_id, "neighbors": self.neighbors, "visible_facts": self.visible_facts}


@dataclass(slots=True)
class TaskAllocationView:
    channel: str
    tasks: list[dict[str, Any]] = field(default_factory=list)
    assignments: list[dict[str, Any]] = field(default_factory=list)
    dependency_layers: list[list[str]] = field(default_factory=list)
    unmet_tasks: list[dict[str, Any]] = field(default_factory=list)
    neighborhood_map: dict[str, list[str]] = field(default_factory=dict)
    coordination_energy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "tasks": self.tasks,
            "assignments": self.assignments,
            "dependency_layers": self.dependency_layers,
            "unmet_tasks": self.unmet_tasks,
            "neighborhood_map": self.neighborhood_map,
            "coordination_energy": self.coordination_energy,
        }


@dataclass(slots=True)
class MEPEnvelope:
    envelope_id: str
    protocol: str
    version: str
    actor_id: str
    world: WorldSnapshot
    knowledge: KnowledgeSnapshot
    attention: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "protocol": self.protocol,
            "version": self.version,
            "actor_id": self.actor_id,
            "world": self.world.to_dict(),
            "knowledge": self.knowledge.to_dict(),
            "attention": self.attention,
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(slots=True)
class MultiAgentEnvelope:
    envelope_id: str
    protocol: str
    version: str
    context_name: str
    agent_ids: list[str]
    world: WorldSnapshot
    shared_knowledge: dict[str, Any]
    agent_views: list[dict[str, Any]] = field(default_factory=list)
    coordination: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "protocol": self.protocol,
            "version": self.version,
            "context_name": self.context_name,
            "agent_ids": self.agent_ids,
            "world": self.world.to_dict(),
            "shared_knowledge": self.shared_knowledge,
            "agent_views": self.agent_views,
            "coordination": self.coordination,
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(slots=True)
class MultiContextEnvelope:
    envelope_id: str
    protocol: str
    version: str
    bindings: list[ContextBindingSpec]
    worlds: list[WorldSnapshot]
    shared_knowledge: dict[str, Any]
    agent_views: list[AgentContextView] = field(default_factory=list)
    coordination: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "protocol": self.protocol,
            "version": self.version,
            "bindings": [binding.to_dict() for binding in self.bindings],
            "worlds": [world.to_dict() for world in self.worlds],
            "shared_knowledge": self.shared_knowledge,
            "agent_views": [view.to_dict() for view in self.agent_views],
            "coordination": self.coordination,
            "created_at": self.created_at,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass(slots=True)
class NegotiationView:
    task: dict[str, Any]
    winner: dict[str, Any] | None = None
    bids: list[dict[str, Any]] = field(default_factory=list)
    unresolved_reasons: list[str] = field(default_factory=list)
    arbitration: dict[str, Any] = field(default_factory=dict)
    scoring: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "winner": self.winner,
            "bids": self.bids,
            "unresolved_reasons": self.unresolved_reasons,
            "arbitration": self.arbitration,
            "scoring": self.scoring,
        }


@dataclass(slots=True)
class CausalLinkView:
    link_id: str
    task_id: str
    from_id: str
    to_id: str
    context_name: str
    action_type: str
    channel: str = 'all'
    depends_on: list[str] = field(default_factory=list)
    ok: bool = True
    at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "task_id": self.task_id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "context_name": self.context_name,
            "action_type": self.action_type,
            "channel": self.channel,
            "depends_on": self.depends_on,
            "ok": self.ok,
            "at": self.at,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class DistributedExecutionView:
    channel: str
    layers: list[list[str]] = field(default_factory=list)
    executed: list[dict[str, Any]] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    causal_links: list[dict[str, Any]] = field(default_factory=list)
    compensations: list[dict[str, Any]] = field(default_factory=list)
    rolled_back: bool = False
    failed_task_ids: list[str] = field(default_factory=list)
    rollback_policy: str = "full"
    recovery_policy: str = "abort"
    retried_task_ids: list[str] = field(default_factory=list)
    recovered_task_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "layers": self.layers,
            "executed": self.executed,
            "blocked": self.blocked,
            "causal_links": self.causal_links,
            "compensations": self.compensations,
            "rolled_back": self.rolled_back,
            "failed_task_ids": self.failed_task_ids,
            "rollback_policy": self.rollback_policy,
            "recovery_policy": self.recovery_policy,
            "retried_task_ids": self.retried_task_ids,
            "recovered_task_ids": self.recovered_task_ids,
        }


@dataclass(slots=True)
class ArbitrationView:
    policy: str
    margin: float = 0.0
    candidates: list[str] = field(default_factory=list)
    selected_agent_id: str = ""
    selected_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy,
            "margin": self.margin,
            "candidates": self.candidates,
            "selected_agent_id": self.selected_agent_id,
            "selected_by": self.selected_by,
        }


@dataclass(slots=True)
class CompensationView:
    task_id: str
    agent_id: str
    action_type: str
    ok: bool
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "ok": self.ok,
            "message": self.message,
            "payload": self.payload,
        }


@dataclass(slots=True)
class ProvenanceRecord:
    record_id: str
    kind: str
    agent_id: str
    entity_key: str
    relation: str
    activity: str
    context_name: str = ""
    channel: str = "all"
    derived_from: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    at: float = field(default_factory=time.time)
    chain_index: int = 0
    prev_hash: str = ""
    record_hash: str = ""
    federation_id: str = ""
    environment_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "agent_id": self.agent_id,
            "entity_key": self.entity_key,
            "relation": self.relation,
            "activity": self.activity,
            "context_name": self.context_name,
            "channel": self.channel,
            "derived_from": self.derived_from,
            "metadata": self.metadata,
            "at": self.at,
            "chain_index": self.chain_index,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
            "federation_id": self.federation_id,
            "environment_id": self.environment_id,
        }


@dataclass(slots=True)
class FederationCard:
    protocol: str
    version: str
    federation_id: str
    environments: list[dict[str, Any]] = field(default_factory=list)
    routes: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": self.protocol,
            "version": self.version,
            "federation_id": self.federation_id,
            "environments": self.environments,
            "routes": self.routes,
        }


@dataclass(slots=True)
class MEPDecision:
    decision: str
    action_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "action_type": self.action_type,
            "payload": self.payload,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


@dataclass(slots=True)
class MEPMessage:
    message_type: str
    version: str
    body: dict[str, Any]
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_type": self.message_type,
            "version": self.version,
            "body": self.body,
            "message_id": self.message_id,
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class StateDelta:
    sequence_id: int
    event_count: int
    knowledge_deltas: list[dict[str, Any]]
    reaction_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "event_count": self.event_count,
            "knowledge_deltas": self.knowledge_deltas,
            "reaction_count": self.reaction_count,
        }


@dataclass(slots=True)
class ReplayWindow:
    from_event_index: int
    to_event_index: int
    events: list[dict[str, Any]]
    reactions: list[dict[str, Any]]
    knowledge_deltas: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_event_index": self.from_event_index,
            "to_event_index": self.to_event_index,
            "events": self.events,
            "reactions": self.reactions,
            "knowledge_deltas": self.knowledge_deltas,
        }


@dataclass(slots=True)
class StreamPacket:
    channel: str
    sequence_id: int
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"channel": self.channel, "sequence_id": self.sequence_id, "payload": self.payload}


@dataclass(slots=True)
class SessionSubscription:
    channel: str
    cursor: int = 0


@dataclass(slots=True)
class MEPSession:
    session_id: str
    client_id: str
    subscriptions: dict[str, SessionSubscription] = field(default_factory=dict)
    memory: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def subscribe(self, channel: str) -> None:
        self.subscriptions.setdefault(channel, SessionSubscription(channel=channel))

    def unsubscribe(self, channel: str) -> None:
        self.subscriptions.pop(channel, None)

    def record(self, item: dict[str, Any]) -> None:
        self.memory.append(item)
        if len(self.memory) > 50:
            self.memory[:] = self.memory[-50:]


@dataclass(slots=True)
class MEPError:
    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


@dataclass(slots=True)
class JsonRpcError:
    code: int
    message: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data:
            payload["data"] = self.data
        return payload


@dataclass(slots=True)
class JsonRpcRequest:
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str | int | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        payload = {"jsonrpc": self.jsonrpc, "method": self.method, "params": self.params}
        if self.id is not None:
            payload["id"] = self.id
        return payload


@dataclass(slots=True)
class JsonRpcResponse:
    result: dict[str, Any] | None = None
    error: JsonRpcError | None = None
    id: str | int | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            payload["error"] = self.error.to_dict()
        else:
            payload["result"] = self.result
        return payload
