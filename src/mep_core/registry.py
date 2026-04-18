from __future__ import annotations

from typing import Any

MEP_VERSION = "2.0.0"
SDK_VERSION = "1.0.1"

METHOD_SPECS: dict[str, dict[str, Any]] = {
    "mep.handshake": {"category": "core", "requires_actor": False, "requires_context": False, "summary": "Open a stateful MEP session and return capability/environment cards.", "params": {"client_id": "string"}},
    "mep.health": {"category": "core", "requires_actor": False, "requires_context": False, "summary": "Return runtime health, counters, provenance integrity, and federation status.", "params": {}},
    "mep.spec": {"category": "core", "requires_actor": False, "requires_context": False, "summary": "Return the protocol method registry and versioned beta surface.", "params": {}},
    "mep.spec.schema": {"category": "core", "requires_actor": False, "requires_context": False, "summary": "Return JSON-schema-like request contracts for the protocol surface.", "params": {}},
    "mep.spec.markdown": {"category": "core", "requires_actor": False, "requires_context": False, "summary": "Return a markdown rendering of the public MEP method catalog.", "params": {}},
    "mep.method.describe": {"category": "core", "requires_actor": False, "requires_context": False, "summary": "Describe one method, including alias/deprecation metadata if relevant.", "params": {"method": "string"}},
    "mep.environment.card": {"category": "core", "requires_actor": False, "requires_context": False, "summary": "Describe the environment capability surface.", "params": {}},
    "mep.agents": {"category": "agents", "requires_actor": False, "requires_context": False, "summary": "List agents known to the gateway.", "params": {}},
    "mep.session.subscribe": {"category": "stream", "requires_actor": False, "requires_context": False, "summary": "Subscribe a session to a delta/event channel.", "params": {"session_id": "string", "channel": "string"}},
    "mep.session.unsubscribe": {"category": "stream", "requires_actor": False, "requires_context": False, "summary": "Remove a session subscription.", "params": {"session_id": "string", "channel": "string"}},
    "mep.session.poll": {"category": "stream", "requires_actor": False, "requires_context": False, "summary": "Poll queued stream packets for a session.", "params": {"session_id": "string"}},
    "mep.replay": {"category": "stream", "requires_actor": False, "requires_context": False, "summary": "Return a replay window over events, reactions, and knowledge deltas.", "params": {"from_event_index": "int"}},
    "mep.envelope": {"category": "world", "requires_actor": True, "requires_context": True, "summary": "Build a single-agent envelope.", "params": {"session_id": "string?", "knowledge_prefix": "string?"}},
    "mep.execute": {"category": "world", "requires_actor": True, "requires_context": True, "summary": "Validate and execute a decision.", "params": {"decision": "object"}},
    "mep.why": {"category": "explain", "requires_actor": True, "requires_context": True, "summary": "Explain why an action is available.", "params": {"action_type": "string"}},
    "mep.why_not": {"category": "explain", "requires_actor": True, "requires_context": True, "summary": "Explain why an action is blocked or degraded.", "params": {"action_type": "string"}},
    "mep.plan": {"category": "plan", "requires_actor": True, "requires_context": True, "summary": "Preview a local action sequence toward a goal.", "params": {"goal": "sense"}},
    "mep.mission.preview": {"category": "plan", "requires_actor": True, "requires_context": True, "summary": "Preview a mission plan over objectives.", "params": {"mission_objectives": "list"}},
    "mep.shared.envelope": {"category": "multi-agent", "requires_actor": False, "requires_context": True, "summary": "Build a shared-context multi-agent envelope.", "params": {"actor_ids": "list?"}},
    "mep.multi.context.envelope": {"category": "multi-context", "requires_actor": False, "requires_context": False, "summary": "Build a multi-context envelope from explicit bindings.", "params": {"bindings": "list"}},
    "mep.multi.context.plan": {"category": "multi-context", "requires_actor": False, "requires_context": False, "summary": "Preview a coordinated plan over multiple contexts.", "params": {"bindings": "list", "goal": "sense"}},
    "mep.multi.assign": {"category": "multi-agent", "requires_actor": False, "requires_context": False, "summary": "Allocate tasks across agents and dependency layers.", "params": {"bindings": "list", "tasks": "list"}},
    "mep.multi.negotiate": {"category": "multi-agent", "requires_actor": False, "requires_context": False, "summary": "Negotiate task ownership across agents.", "params": {"bindings": "list", "task": "object"}},
    "mep.multi.execute": {"category": "multi-agent", "requires_actor": False, "requires_context": False, "summary": "Execute a cooperative task set.", "params": {"bindings": "list", "tasks": "list"}},
    "mep.neighborhood": {"category": "mesh", "requires_actor": True, "requires_context": True, "summary": "Return neighbor visibility from the shared knowledge mesh.", "params": {"knowledge_prefix": "string?"}},
    "mep.causal.trace": {"category": "trace", "requires_actor": True, "requires_context": True, "summary": "Return recent causal links.", "params": {"limit": "int?"}},
    "mep.provenance.trace": {"category": "trace", "requires_actor": True, "requires_context": True, "summary": "Return provenance records.", "params": {"limit": "int?"}},
    "mep.provenance.verify": {"category": "trace", "requires_actor": True, "requires_context": True, "summary": "Verify the local provenance chain.", "params": {}},
    "mep.knowledge.propagate": {"category": "mesh", "requires_actor": True, "requires_context": True, "summary": "Propagate a fact through mesh edges by channel/hops.", "params": {"key": "string", "channels": "list?", "max_hops": "int?"}},
    "mep.federation.card": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Describe the federation.", "params": {}},
    "mep.federation.environments": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "List federated environments.", "params": {}},
    "mep.federation.route": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Forward an arbitrary JSON-RPC call to another environment.", "params": {"environment_id": "string", "forward_method": "string", "forward_params": "object?"}},
    "mep.federation.resolve_task": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Resolve a task to an environment.", "params": {"task": "object"}},
    "mep.federation.route_task": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Resolve and route a task method.", "params": {"task": "object"}},
    "mep.federation.resolve_plan": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Resolve a task batch into per-environment groups.", "params": {"tasks": "list"}},
    "mep.federation.execute_task": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Execute one task on the selected environment.", "params": {"task": "object"}},
    "mep.federation.execute_plan": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Execute a resolved batch across environments.", "params": {"tasks": "list"}},
    "mep.federation.mission_graph": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Build a federated mission graph.", "params": {"tasks": "list"}},
    "mep.federation.execute_mission": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Execute a federated mission graph stage by stage.", "params": {"tasks": "list"}},
    "mep.federation.provenance": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Aggregate provenance across environments.", "params": {"limit": "int?"}},
    "mep.federation.provenance.verify": {"category": "federation", "requires_actor": False, "requires_context": False, "summary": "Verify provenance chains across environments.", "params": {}},
    "mep.fault.inject": {"category": "fault", "requires_actor": False, "requires_context": False, "summary": "Inject a synthetic fault into an action, task, route, or environment.", "params": {"scope": "string", "target": "string", "count": "int?", "message": "string?", "metadata": "object?"}},
    "mep.fault.clear": {"category": "fault", "requires_actor": False, "requires_context": False, "summary": "Clear synthetic faults by optional scope/target.", "params": {"scope": "string?", "target": "string?"}},
    "mep.fault.status": {"category": "fault", "requires_actor": False, "requires_context": False, "summary": "Return active synthetic faults and recovery counters.", "params": {}},
}

DEPRECATED_ALIASES: dict[str, str] = {
    "mep.capabilities": "mep.environment.card",
    "mep.world.envelope": "mep.envelope",
    "mep.session.updates": "mep.session.poll",
    "mep.trace": "mep.causal.trace",
    "mep.provenance": "mep.provenance.trace",
    "mep.federation.list": "mep.federation.environments",
}

_TYPE_TO_SCHEMA = {
    "string": {"type": "string"},
    "string?": {"type": ["string", "null"]},
    "int": {"type": "integer"},
    "int?": {"type": ["integer", "null"]},
    "float": {"type": "number"},
    "float?": {"type": ["number", "null"]},
    "bool": {"type": "boolean"},
    "bool?": {"type": ["boolean", "null"]},
    "list": {"type": "array"},
    "list?": {"type": ["array", "null"]},
    "object": {"type": "object"},
    "object?": {"type": ["object", "null"]},
    "sense": {
        "type": "object",
        "properties": {
            "dimension": {"type": "string"},
            "meaning": {"type": "string"},
            "magnitude": {"type": "number"},
        },
        "required": ["dimension", "meaning"],
    },
}


def _param_schema(type_name: str) -> dict[str, Any]:
    return dict(_TYPE_TO_SCHEMA.get(type_name, {"type": ["string", "number", "boolean", "object", "array", "null"]}))


def resolve_method_alias(method: str) -> tuple[str, dict[str, Any] | None]:
    canonical = DEPRECATED_ALIASES.get(method, method)
    if canonical == method:
        return canonical, None
    return canonical, {
        "alias": method,
        "canonical": canonical,
        "deprecated": True,
        "removal_hint": "Use the canonical method name in future clients.",
    }


def build_method_descriptor(method: str) -> dict[str, Any]:
    canonical, alias_info = resolve_method_alias(method)
    spec = METHOD_SPECS.get(canonical)
    if spec is None:
        return {
            "method": method,
            "canonical_method": canonical,
            "known": False,
            "deprecated_alias": alias_info,
        }
    aliases = sorted(alias for alias, target in DEPRECATED_ALIASES.items() if target == canonical)
    return {
        "method": canonical,
        "canonical_method": canonical,
        "known": True,
        "deprecated_alias": alias_info,
        "aliases": aliases,
        **spec,
    }


def build_protocol_spec() -> dict[str, Any]:
    methods = []
    categories: dict[str, list[str]] = {}
    alias_map: dict[str, list[str]] = {}
    for name, spec in sorted(METHOD_SPECS.items()):
        item = {"method": name, **spec, "aliases": sorted(alias for alias, target in DEPRECATED_ALIASES.items() if target == name)}
        methods.append(item)
        categories.setdefault(spec["category"], []).append(name)
        if item["aliases"]:
            alias_map[name] = item["aliases"]
    return {
        "protocol": "MEP",
        "version": MEP_VERSION,
        "sdk_version": SDK_VERSION,
        "method_count": len(methods),
        "categories": {k: sorted(v) for k, v in sorted(categories.items())},
        "aliases": alias_map,
        "methods": methods,
    }


def build_json_schema_catalog() -> dict[str, Any]:
    methods: dict[str, Any] = {}
    for name, spec in sorted(METHOD_SPECS.items()):
        params = spec.get("params", {})
        methods[name] = {
            "summary": spec.get("summary", ""),
            "category": spec.get("category", "unknown"),
            "requires_actor": bool(spec.get("requires_actor", False)),
            "requires_context": bool(spec.get("requires_context", False)),
            "aliases": sorted(alias for alias, target in DEPRECATED_ALIASES.items() if target == name),
            "request_schema": {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "jsonrpc": {"const": "2.0"},
                    "method": {"enum": [name, *sorted(alias for alias, target in DEPRECATED_ALIASES.items() if target == name)]},
                    "params": {
                        "type": "object",
                        "properties": {k: _param_schema(v) for k, v in params.items()},
                        "required": [k for k, v in params.items() if not str(v).endswith('?')],
                        "additionalProperties": True,
                    },
                    "id": {"type": ["string", "integer", "null"]},
                },
                "required": ["jsonrpc", "method", "params"],
                "additionalProperties": False,
            },
        }
    return {
        "protocol": "MEP",
        "version": MEP_VERSION,
        "sdk_version": SDK_VERSION,
        "method_count": len(methods),
        "deprecated_aliases": dict(DEPRECATED_ALIASES),
        "methods": methods,
    }


def build_markdown_spec() -> str:
    spec = build_protocol_spec()
    lines = [
        f"# MEP Method Catalog {MEP_VERSION}",
        "",
        f"SDK version: {SDK_VERSION}",
        "",
        "## Categories",
        "",
    ]
    for category, names in spec["categories"].items():
        lines.append(f"- **{category}**: {', '.join(names)}")
    lines.extend(["", "## Methods", ""])
    for method in spec["methods"]:
        lines.append(f"### `{method['method']}`")
        lines.append("")
        lines.append(method["summary"])
        lines.append("")
        lines.append(f"- Category: `{method['category']}`")
        lines.append(f"- Requires actor: `{str(method['requires_actor']).lower()}`")
        lines.append(f"- Requires context: `{str(method['requires_context']).lower()}`")
        if method.get("aliases"):
            lines.append(f"- Aliases: {', '.join('`'+a+'`' for a in method['aliases'])}")
        if method.get("params"):
            lines.append("- Params:")
            for key, kind in method["params"].items():
                lines.append(f"  - `{key}`: `{kind}`")
        else:
            lines.append("- Params: none")
        lines.append("")
    if DEPRECATED_ALIASES:
        lines.extend(["## Deprecated Aliases", ""])
        for alias, target in sorted(DEPRECATED_ALIASES.items()):
            lines.append(f"- `{alias}` -> `{target}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"
