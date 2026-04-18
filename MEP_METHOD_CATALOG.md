# MEP Method Catalog 2.0.0

SDK version: 1.0.1

## Categories

- **agents**: mep.agents
- **core**: mep.environment.card, mep.handshake, mep.health, mep.method.describe, mep.spec, mep.spec.markdown, mep.spec.schema
- **explain**: mep.why, mep.why_not
- **fault**: mep.fault.clear, mep.fault.inject, mep.fault.status
- **federation**: mep.federation.card, mep.federation.environments, mep.federation.execute_mission, mep.federation.execute_plan, mep.federation.execute_task, mep.federation.mission_graph, mep.federation.provenance, mep.federation.provenance.verify, mep.federation.resolve_plan, mep.federation.resolve_task, mep.federation.route, mep.federation.route_task
- **mesh**: mep.knowledge.propagate, mep.neighborhood
- **multi-agent**: mep.multi.assign, mep.multi.execute, mep.multi.negotiate, mep.shared.envelope
- **multi-context**: mep.multi.context.envelope, mep.multi.context.plan
- **plan**: mep.mission.preview, mep.plan
- **stream**: mep.replay, mep.session.poll, mep.session.subscribe, mep.session.unsubscribe
- **trace**: mep.causal.trace, mep.provenance.trace, mep.provenance.verify
- **world**: mep.envelope, mep.execute

## Methods

### `mep.agents`

List agents known to the gateway.

- Category: `agents`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.causal.trace`

Return recent causal links.

- Category: `trace`
- Requires actor: `true`
- Requires context: `true`
- Aliases: `mep.trace`
- Params:
  - `limit`: `int?`

### `mep.envelope`

Build a single-agent envelope.

- Category: `world`
- Requires actor: `true`
- Requires context: `true`
- Aliases: `mep.world.envelope`
- Params:
  - `session_id`: `string?`
  - `knowledge_prefix`: `string?`

### `mep.environment.card`

Describe the environment capability surface.

- Category: `core`
- Requires actor: `false`
- Requires context: `false`
- Aliases: `mep.capabilities`
- Params: none

### `mep.execute`

Validate and execute a decision.

- Category: `world`
- Requires actor: `true`
- Requires context: `true`
- Params:
  - `decision`: `object`

### `mep.fault.clear`

Clear synthetic faults by optional scope/target.

- Category: `fault`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `scope`: `string?`
  - `target`: `string?`

### `mep.fault.inject`

Inject a synthetic fault into an action, task, route, or environment.

- Category: `fault`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `scope`: `string`
  - `target`: `string`
  - `count`: `int?`
  - `message`: `string?`
  - `metadata`: `object?`

### `mep.fault.status`

Return active synthetic faults and recovery counters.

- Category: `fault`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.federation.card`

Describe the federation.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.federation.environments`

List federated environments.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Aliases: `mep.federation.list`
- Params: none

### `mep.federation.execute_mission`

Execute a federated mission graph stage by stage.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `tasks`: `list`

### `mep.federation.execute_plan`

Execute a resolved batch across environments.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `tasks`: `list`

### `mep.federation.execute_task`

Execute one task on the selected environment.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `task`: `object`

### `mep.federation.mission_graph`

Build a federated mission graph.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `tasks`: `list`

### `mep.federation.provenance`

Aggregate provenance across environments.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `limit`: `int?`

### `mep.federation.provenance.verify`

Verify provenance chains across environments.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.federation.resolve_plan`

Resolve a task batch into per-environment groups.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `tasks`: `list`

### `mep.federation.resolve_task`

Resolve a task to an environment.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `task`: `object`

### `mep.federation.route`

Forward an arbitrary JSON-RPC call to another environment.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `environment_id`: `string`
  - `forward_method`: `string`
  - `forward_params`: `object?`

### `mep.federation.route_task`

Resolve and route a task method.

- Category: `federation`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `task`: `object`

### `mep.handshake`

Open a stateful MEP session and return capability/environment cards.

- Category: `core`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `client_id`: `string`

### `mep.health`

Return runtime health, counters, provenance integrity, and federation status.

- Category: `core`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.knowledge.propagate`

Propagate a fact through mesh edges by channel/hops.

- Category: `mesh`
- Requires actor: `true`
- Requires context: `true`
- Params:
  - `key`: `string`
  - `channels`: `list?`
  - `max_hops`: `int?`

### `mep.method.describe`

Describe one method, including alias/deprecation metadata if relevant.

- Category: `core`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `method`: `string`

### `mep.mission.preview`

Preview a mission plan over objectives.

- Category: `plan`
- Requires actor: `true`
- Requires context: `true`
- Params:
  - `mission_objectives`: `list`

### `mep.multi.assign`

Allocate tasks across agents and dependency layers.

- Category: `multi-agent`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `bindings`: `list`
  - `tasks`: `list`

### `mep.multi.context.envelope`

Build a multi-context envelope from explicit bindings.

- Category: `multi-context`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `bindings`: `list`

### `mep.multi.context.plan`

Preview a coordinated plan over multiple contexts.

- Category: `multi-context`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `bindings`: `list`
  - `goal`: `sense`

### `mep.multi.execute`

Execute a cooperative task set.

- Category: `multi-agent`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `bindings`: `list`
  - `tasks`: `list`

### `mep.multi.negotiate`

Negotiate task ownership across agents.

- Category: `multi-agent`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `bindings`: `list`
  - `task`: `object`

### `mep.neighborhood`

Return neighbor visibility from the shared knowledge mesh.

- Category: `mesh`
- Requires actor: `true`
- Requires context: `true`
- Params:
  - `knowledge_prefix`: `string?`

### `mep.plan`

Preview a local action sequence toward a goal.

- Category: `plan`
- Requires actor: `true`
- Requires context: `true`
- Params:
  - `goal`: `sense`

### `mep.provenance.trace`

Return provenance records.

- Category: `trace`
- Requires actor: `true`
- Requires context: `true`
- Aliases: `mep.provenance`
- Params:
  - `limit`: `int?`

### `mep.provenance.verify`

Verify the local provenance chain.

- Category: `trace`
- Requires actor: `true`
- Requires context: `true`
- Params: none

### `mep.replay`

Return a replay window over events, reactions, and knowledge deltas.

- Category: `stream`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `from_event_index`: `int`

### `mep.session.poll`

Poll queued stream packets for a session.

- Category: `stream`
- Requires actor: `false`
- Requires context: `false`
- Aliases: `mep.session.updates`
- Params:
  - `session_id`: `string`

### `mep.session.subscribe`

Subscribe a session to a delta/event channel.

- Category: `stream`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `session_id`: `string`
  - `channel`: `string`

### `mep.session.unsubscribe`

Remove a session subscription.

- Category: `stream`
- Requires actor: `false`
- Requires context: `false`
- Params:
  - `session_id`: `string`
  - `channel`: `string`

### `mep.shared.envelope`

Build a shared-context multi-agent envelope.

- Category: `multi-agent`
- Requires actor: `false`
- Requires context: `true`
- Params:
  - `actor_ids`: `list?`

### `mep.spec`

Return the protocol method registry and versioned beta surface.

- Category: `core`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.spec.markdown`

Return a markdown rendering of the public MEP method catalog.

- Category: `core`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.spec.schema`

Return JSON-schema-like request contracts for the protocol surface.

- Category: `core`
- Requires actor: `false`
- Requires context: `false`
- Params: none

### `mep.why`

Explain why an action is available.

- Category: `explain`
- Requires actor: `true`
- Requires context: `true`
- Params:
  - `action_type`: `string`

### `mep.why_not`

Explain why an action is blocked or degraded.

- Category: `explain`
- Requires actor: `true`
- Requires context: `true`
- Params:
  - `action_type`: `string`

## Deprecated Aliases

- `mep.capabilities` -> `mep.environment.card`
- `mep.federation.list` -> `mep.federation.environments`
- `mep.provenance` -> `mep.provenance.trace`
- `mep.session.updates` -> `mep.session.poll`
- `mep.trace` -> `mep.causal.trace`
- `mep.world.envelope` -> `mep.envelope`
