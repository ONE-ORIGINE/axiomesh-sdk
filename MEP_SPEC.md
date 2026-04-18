# MEP 2.0.0 Specification Snapshot

MEP is the environment protocol layer of the SDK. It exposes a versioned, introspectable method surface for single-agent, multi-agent, multi-context, and federated execution.

## Scope and positioning

MEP is **not** specified as a wrapper over MCP. It is specified as an independent environment protocol.

Its native objects are:
- environments
- contexts
- bindings
- action surfaces
- certainty-aware knowledge
- causal traces
- federated execution graphs

A bridge to MCP-style systems is possible, but it would be an adapter layer. It is not the defining abstraction of MEP.

## Core goals

- represent the world as structured context instead of raw prompt text
- expose action surfaces already limited by role, context, and situation
- carry certainty-aware knowledge instead of flattening everything into probability
- support distributed, federated execution across environments
- preserve explanation, provenance, and replayability

## Required runtime methods

- `mep.handshake`
- `mep.health`
- `mep.spec`
- `mep.spec.schema`
- `mep.spec.markdown`
- `mep.method.describe`
- `mep.environment.card`

## Agent and stream methods

- `mep.agents`
- `mep.session.subscribe`
- `mep.session.unsubscribe`
- `mep.session.poll`
- `mep.replay`

## Execution and explanation methods

- `mep.envelope`
- `mep.execute`
- `mep.why`
- `mep.why_not`
- `mep.plan`
- `mep.mission.preview`

## Multi-agent and multi-context methods

- `mep.shared.envelope`
- `mep.multi.context.envelope`
- `mep.multi.context.plan`
- `mep.multi.assign`
- `mep.multi.negotiate`
- `mep.multi.execute`
- `mep.neighborhood`
- `mep.knowledge.propagate`

## Federation methods

- `mep.federation.card`
- `mep.federation.environments`
- `mep.federation.route`
- `mep.federation.resolve_task`
- `mep.federation.route_task`
- `mep.federation.resolve_plan`
- `mep.federation.execute_task`
- `mep.federation.execute_plan`
- `mep.federation.mission_graph`
- `mep.federation.execute_mission`
- `mep.federation.provenance`
- `mep.federation.provenance.verify`

## Trace and resilience methods

- `mep.causal.trace`
- `mep.provenance.trace`
- `mep.provenance.verify`
- `mep.fault.inject`
- `mep.fault.clear`
- `mep.fault.status`

## Transport

The reference runtime ships with JSON-RPC 2.0 over in-process handling, but the protocol surface is versioned separately from the transport implementation.
