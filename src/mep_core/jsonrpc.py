from __future__ import annotations

from typing import Any

from collections import defaultdict

from edp_core import Context, ContextBinding, Element, MissionObjective, SenseVector

from .gateway import MEPGateway
from .registry import resolve_method_alias
from .spec import JsonRpcError, JsonRpcRequest, JsonRpcResponse, MEPDecision


class MEPJsonRpcServer:
    def __init__(self, gateway: MEPGateway, hub = None):
        self.gateway = gateway
        self.hub = hub

    def _sense_from_params(self, params: dict[str, Any]) -> SenseVector:
        goal = params.get("goal") or {}
        dimension = str(goal.get("dimension", params.get("dimension", "technical"))).lower()
        meaning = str(goal.get("meaning", params.get("meaning", "goal")))
        magnitude = float(goal.get("magnitude", params.get("magnitude", 0.8)))
        factory = getattr(SenseVector, dimension, SenseVector.technical)
        return factory(meaning, magnitude)

    def _mission_objectives_from_params(self, params: dict[str, Any]) -> list[MissionObjective]:
        raw = params.get("mission_objectives", []) or []
        objectives: list[MissionObjective] = []
        for idx, item in enumerate(raw):
            target = item.get("target_sense", {}) if isinstance(item, dict) else {}
            factory = getattr(SenseVector, str(target.get("dimension", "technical")).lower(), SenseVector.technical)
            target_sense = factory(str(target.get("meaning", f"objective-{idx}")), float(target.get("magnitude", 0.8)))
            objectives.append(MissionObjective(
                objective_id=str(item.get("objective_id", f"objective-{idx}")),
                description=str(item.get("description", target_sense.meaning)),
                target_sense=target_sense,
                priority=int(item.get("priority", idx + 1)),
                success_threshold=float(item.get("success_threshold", 0.0)),
                preferred_contexts=list(item.get("preferred_contexts", [])),
            ))
        return objectives

    def _actors_from_params(self, params: dict[str, Any], fallback_actor: Element | None = None) -> list[Element]:
        actor_ids = params.get("actor_ids") or []
        actors: list[Element] = []
        for actor_id in actor_ids:
            actor = self.gateway.env.elements.get(str(actor_id))
            if actor is not None:
                actors.append(actor)
        if not actors and fallback_actor is not None:
            actors = [fallback_actor]
        if not actors:
            actors = list(self.gateway.env.elements.values())
        return actors

    def _bindings_from_params(self, params: dict[str, Any], fallback_actor: Element | None = None, fallback_context: Context | None = None) -> list[ContextBinding]:
        raw = params.get("bindings") or []
        bindings: list[ContextBinding] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            bindings.append(ContextBinding(
                agent_id=str(item.get("agent_id", "")),
                context_name=str(item.get("context_name", "")),
                role=str(item.get("role", "")),
                parent_agent_id=str(item.get("parent_agent_id", "")),
                channel=str(item.get("channel", "all")),
                metadata=dict(item.get("metadata", {})),
            ))
        if not bindings and fallback_actor is not None and fallback_context is not None:
            bindings = [ContextBinding(agent_id=fallback_actor.element_id, context_name=fallback_context.name)]
        return bindings

    def _fallback_target(self, environment_id: str, actor: Element | None, context: Context | None):
        if self.hub is None:
            return None, None, None
        target = self.hub.resolve(environment_id)
        if target is None:
            return None, None, None
        target_actor = actor
        target_context = context
        if actor is not None and actor.element_id not in target.gateway.env.elements:
            target_actor = next(iter(target.gateway.env.elements.values()), None)
        elif actor is None:
            target_actor = next(iter(target.gateway.env.elements.values()), None)
        if context is not None and all(ctx.name != context.name for ctx in target.gateway.env.contexts):
            target_context = target.gateway.env.contexts[0] if target.gateway.env.contexts else None
        elif context is None:
            target_context = target.gateway.env.contexts[0] if target.gateway.env.contexts else None
        return target, target_actor, target_context

    def _default_bindings_for_target(self, target, target_actor: Element | None, target_context: Context | None, forwarded_params: dict[str, Any]) -> list[dict[str, Any]]:
        bindings = forwarded_params.get('bindings')
        if bindings:
            return list(bindings)
        if target_context is None:
            return []
        result: list[dict[str, Any]] = []
        if target_actor is not None:
            result.append(ContextBinding(agent_id=target_actor.element_id, context_name=target_context.name).to_dict())
        else:
            for actor in target.gateway.env.elements.values():
                result.append(ContextBinding(agent_id=actor.element_id, context_name=target_context.name).to_dict())
        return result

    async def _route_request(self, environment_id: str, method: str, forwarded_params: dict[str, Any], actor: Element | None, context: Context | None, request_id: Any):
        target, target_actor, target_context = self._fallback_target(environment_id, actor, context)
        if target is None:
            return None, JsonRpcResponse(id=request_id, error=JsonRpcError(-32031, 'Unknown federated environment', {'environment_id': environment_id}))
        route_fault = target.gateway.consume_fault("route", method) or target.gateway.consume_fault("route_env", environment_id)
        if route_fault is not None:
            return (target, target_actor, target_context), JsonRpcResponse(id=request_id, error=JsonRpcError(-32041, str(route_fault.get("message", "Injected route fault")), {"environment_id": environment_id, "method": method}))
        target_server = MEPJsonRpcServer(target.gateway, hub=self.hub)
        routed = await target_server.handle(JsonRpcRequest(method=method, params=forwarded_params, id=request_id), actor=target_actor, context=target_context)
        return (target, target_actor, target_context), routed

    async def handle(self, request: JsonRpcRequest, actor: Element | None = None, context: Context | None = None) -> JsonRpcResponse:
        try:
            if request.jsonrpc != "2.0":
                return JsonRpcResponse(id=request.id, error=JsonRpcError(-32600, "Invalid JSON-RPC version", {"expected": "2.0"}))
            canonical_method, alias_info = resolve_method_alias(request.method)
            request.method = canonical_method
            if alias_info is not None:
                request.params = {**request.params, "_alias": alias_info["alias"], "_canonical_method": canonical_method}
            if request.method == "mep.handshake":
                client_id = str(request.params.get("client_id", "anonymous"))
                msg = self.gateway.handshake(client_id)
                return JsonRpcResponse(id=request.id, result=msg.to_dict())
            if request.method == "mep.health":
                result = self.gateway.health_report()
                if self.hub is not None:
                    result["federation"] = self.hub.federation_card().to_dict()
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.spec":
                result = self.gateway.protocol_spec()
                if self.hub is not None:
                    result["federation_supported"] = True
                    result["federation_environment_count"] = len(self.hub.environments)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.spec.schema":
                result = self.gateway.protocol_schema()
                if self.hub is not None:
                    result["federation_supported"] = True
                    result["federation_environment_count"] = len(self.hub.environments)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.spec.markdown":
                return JsonRpcResponse(id=request.id, result={"markdown": self.gateway.protocol_markdown()})
            if request.method == "mep.method.describe":
                method_name = str(request.params.get("method", ""))
                return JsonRpcResponse(id=request.id, result=self.gateway.describe_method(method_name))
            if request.method == "mep.environment.card":
                return JsonRpcResponse(id=request.id, result=self.gateway.environment_card().to_dict())
            if request.method == "mep.fault.inject":
                scope = str(request.params.get("scope", "action"))
                target = str(request.params.get("target", "*"))
                count = int(request.params.get("count", 1))
                message = str(request.params.get("message", "Injected fault"))
                metadata = dict(request.params.get("metadata", {}))
                return JsonRpcResponse(id=request.id, result=self.gateway.inject_fault(scope, target, count=count, message=message, metadata=metadata))
            if request.method == "mep.fault.clear":
                scope = request.params.get("scope")
                target = request.params.get("target")
                return JsonRpcResponse(id=request.id, result=self.gateway.clear_faults(scope=str(scope) if scope is not None else None, target=str(target) if target is not None else None))
            if request.method == "mep.fault.status":
                return JsonRpcResponse(id=request.id, result=self.gateway.fault_status())
            if request.method == "mep.agents":
                return JsonRpcResponse(id=request.id, result={"agents": [card.to_dict() for card in self.gateway.agent_cards()]})
            if request.method == "mep.session.subscribe":
                session_id = str(request.params.get("session_id", ""))
                channel = str(request.params.get("channel", ""))
                session = self.gateway.get_session(session_id)
                if session is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32010, "Unknown session", {"session_id": session_id}))
                session.subscribe(channel)
                return JsonRpcResponse(id=request.id, result={"session_id": session_id, "subscribed": channel})
            if request.method == "mep.session.unsubscribe":
                session_id = str(request.params.get("session_id", ""))
                channel = str(request.params.get("channel", ""))
                session = self.gateway.get_session(session_id)
                if session is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32010, "Unknown session", {"session_id": session_id}))
                session.unsubscribe(channel)
                return JsonRpcResponse(id=request.id, result={"session_id": session_id, "unsubscribed": channel})
            if request.method == "mep.session.poll":
                session_id = str(request.params.get("session_id", ""))
                session = self.gateway.get_session(session_id)
                if session is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32010, "Unknown session", {"session_id": session_id}))
                packets = [packet.to_dict() for packet in self.gateway.poll_updates(session)]
                return JsonRpcResponse(id=request.id, result={"session_id": session_id, "packets": packets})
            if request.method == "mep.replay":
                start = int(request.params.get("from_event_index", 0))
                replay = self.gateway.build_replay_window(start)
                return JsonRpcResponse(id=request.id, result=replay.to_dict())
            if request.method in {"mep.envelope", "mep.execute", "mep.why", "mep.why_not", "mep.plan", "mep.mission.preview", "mep.knowledge.propagate"} and (actor is None or context is None):
                return JsonRpcResponse(id=request.id, error=JsonRpcError(-32020, "Actor and context are required", {"method": request.method}))
            if request.method == "mep.shared.envelope":
                if context is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32020, "Context is required", {"method": request.method}))
                session_id = request.params.get("session_id")
                session = self.gateway.get_session(session_id) if session_id else None
                prefix = request.params.get("knowledge_prefix")
                goal = self._sense_from_params(request.params) if (request.params.get("goal") or request.params.get("dimension") or request.params.get("meaning")) else None
                actors = self._actors_from_params(request.params, fallback_actor=actor)
                envelope = self.gateway.build_shared_envelope(actors, context, session=session, knowledge_prefix=prefix, goal_sense=goal)
                return JsonRpcResponse(id=request.id, result=envelope.to_dict())
            if request.method == "mep.multi.context.envelope":
                session_id = request.params.get("session_id")
                session = self.gateway.get_session(session_id) if session_id else None
                prefix = request.params.get("knowledge_prefix")
                goal = self._sense_from_params(request.params) if (request.params.get("goal") or request.params.get("dimension") or request.params.get("meaning")) else None
                bindings = self._bindings_from_params(request.params, fallback_actor=actor, fallback_context=context)
                envelope = self.gateway.build_multi_context_envelope(bindings, session=session, knowledge_prefix=prefix, goal_sense=goal)
                return JsonRpcResponse(id=request.id, result=envelope.to_dict())
            if request.method == "mep.multi.plan":
                actors = self._actors_from_params(request.params, fallback_actor=actor)
                goal = self._sense_from_params(request.params)
                max_steps = int(request.params.get("max_steps", 2))
                channel = str(request.params.get("channel", "all"))
                result = self.gateway.preview_multi_plan(actors, goal, max_steps=max_steps, channel=channel)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.multi.assign":
                bindings = self._bindings_from_params(request.params, fallback_actor=actor, fallback_context=context)
                tasks = list(request.params.get("tasks", []))
                radius = float(request.params.get("neighborhood_radius", 8.0))
                result = self.gateway.assign_multi_tasks(bindings, tasks, neighborhood_radius=radius)
                return JsonRpcResponse(id=request.id, result=result.to_dict())
            if request.method == "mep.multi.negotiate":
                bindings = self._bindings_from_params(request.params, fallback_actor=actor, fallback_context=context)
                task = dict(request.params.get("task", {}))
                result = self.gateway.negotiate_multi_task(bindings, task)
                return JsonRpcResponse(id=request.id, result=result.to_dict())
            if request.method == "mep.multi.execute":
                bindings = self._bindings_from_params(request.params, fallback_actor=actor, fallback_context=context)
                tasks = list(request.params.get("tasks", []))
                radius = float(request.params.get("neighborhood_radius", 8.0))
                session_id = request.params.get("session_id")
                session = self.gateway.get_session(session_id) if session_id else None
                initiator = str(request.params.get("initiator", session.client_id if session else "coordinator"))
                rollback_policy = str(request.params.get('rollback_policy', 'full'))
                recovery_policy = str(request.params.get('recovery_policy', 'abort'))
                result = await self.gateway.execute_multi_tasks(bindings, tasks, session=session, initiator=initiator, neighborhood_radius=radius, rollback_policy=rollback_policy, recovery_policy=recovery_policy)
                return JsonRpcResponse(id=request.id, result=result.to_dict())
            if request.method == "mep.causal.trace":
                agent_id = request.params.get("agent_id")
                limit = request.params.get("limit")
                result = {"items": self.gateway.causal_trace(agent_id=str(agent_id) if agent_id else None, limit=int(limit) if limit is not None else None)}
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.provenance.verify":
                return JsonRpcResponse(id=request.id, result=self.gateway.verify_provenance())
            if request.method == "mep.provenance.trace":
                agent_id = request.params.get("agent_id")
                limit = request.params.get("limit")
                result = {"items": self.gateway.provenance_trace(agent_id=str(agent_id) if agent_id else None, limit=int(limit) if limit is not None else None)}
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.neighborhood":
                if actor is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32020, "Actor is required", {"method": request.method}))
                prefix = request.params.get("knowledge_prefix")
                result = self.gateway.neighborhood_snapshot(actor, knowledge_prefix=prefix)
                return JsonRpcResponse(id=request.id, result=result.to_dict())
            if request.method == "mep.multi.context.plan":
                bindings = self._bindings_from_params(request.params, fallback_actor=actor, fallback_context=context)
                goal = self._sense_from_params(request.params)
                max_steps = int(request.params.get("max_steps", 2))
                result = self.gateway.preview_multi_context_plan(bindings, goal, max_steps=max_steps)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.federation.card":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                return JsonRpcResponse(id=request.id, result=self.hub.federation_card().to_dict())
            if request.method == "mep.federation.environments":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                return JsonRpcResponse(id=request.id, result={"environments": self.hub.environment_cards()})


            if request.method == "mep.federation.provenance":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                limit = request.params.get("limit")
                return JsonRpcResponse(id=request.id, result=self.hub.federated_provenance_trace(limit=int(limit) if limit is not None else None))
            if request.method == "mep.federation.provenance.verify":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                return JsonRpcResponse(id=request.id, result=self.hub.verify_federated_provenance())

            if request.method == "mep.federation.resolve_task":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                task = dict(request.params.get("task", {}))
                required_method = str(request.params.get("required_method", "mep.multi.negotiate"))
                preferred_tags = list(request.params.get("preferred_tags", [])) or None
                result = self.hub.resolve_task(task, required_method=required_method, preferred_tags=preferred_tags)
                return JsonRpcResponse(id=request.id, result=result)

            if request.method == "mep.federation.route_task":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                task = dict(request.params.get("task", {}))
                required_method = str(request.params.get("required_method", "mep.multi.negotiate"))
                preferred_tags = list(request.params.get("preferred_tags", [])) or None
                forwarded_params = dict(request.params.get("forward_params", {}))
                resolution = self.hub.resolve_task(task, required_method=required_method, preferred_tags=preferred_tags)
                selected = resolution.get("selected")
                if not selected:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32032, "No federated route for task", {"task_id": task.get("task_id", "")}))
                environment_id = str(selected["environment_id"])
                target_info = self._fallback_target(environment_id, actor, context)
                target, target_actor, target_context = target_info
                merged_params = dict(forwarded_params)
                if required_method in {"mep.multi.negotiate", "mep.multi.assign", "mep.multi.execute"}:
                    bindings = self._default_bindings_for_target(target, target_actor, target_context, merged_params)
                    if bindings:
                        merged_params["bindings"] = bindings
                if required_method == "mep.multi.negotiate":
                    merged_params.setdefault("task", task)
                elif required_method in {"mep.multi.assign", "mep.multi.execute"}:
                    merged_params.setdefault("tasks", [task])
                _, routed = await self._route_request(environment_id, required_method, merged_params, actor, context, request.id)
                if routed.error is not None:
                    return routed
                return JsonRpcResponse(id=request.id, result={"resolution": resolution, "environment_id": environment_id, "method": required_method, "response": routed.to_dict()})


            if request.method == "mep.federation.mission_graph":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                tasks = list(request.params.get("tasks", []))
                required_method = str(request.params.get("required_method", "mep.multi.execute"))
                preferred_tags = list(request.params.get("preferred_tags", [])) or None
                result = self.hub.build_mission_graph(tasks, required_method=required_method, preferred_tags=preferred_tags)
                return JsonRpcResponse(id=request.id, result=result)

            if request.method == "mep.federation.execute_mission":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                tasks = list(request.params.get("tasks", []))
                preferred_tags = list(request.params.get("preferred_tags", [])) or None
                forwarded_params = dict(request.params.get("forward_params", {}))
                rollback_policy = str(request.params.get("rollback_policy", "full"))
                graph = self.hub.build_mission_graph(tasks, required_method="mep.multi.execute", preferred_tags=preferred_tags)
                stage_results = []
                failed_stages = []
                halted = False
                for stage in sorted(graph.get("stages", []), key=lambda s: (s.get("index", 0), s.get("stage_id", ""))):
                    if halted:
                        failed_stages.append({"stage_id": stage.get("stage_id", ""), "reason": "halted_by_previous_failure"})
                        continue
                    environment_id = str(stage.get("environment_id", ""))
                    stage_tasks = list(stage.get("tasks", []))
                    target, target_actor, target_context = self._fallback_target(environment_id, actor, context)
                    merged_params = dict(forwarded_params)
                    bindings = self._default_bindings_for_target(target, target_actor, target_context, merged_params)
                    if bindings:
                        merged_params["bindings"] = bindings
                    merged_params["tasks"] = stage_tasks
                    merged_params["rollback_policy"] = rollback_policy
                    _, routed = await self._route_request(environment_id, "mep.multi.execute", merged_params, actor, context, request.id)
                    if routed.error is not None:
                        failed_stages.append({"stage_id": stage.get("stage_id", ""), "environment_id": environment_id, "error": routed.error.to_dict()})
                        halted = True
                        continue
                    payload = routed.to_dict()
                    stage_results.append({"stage_id": stage.get("stage_id", ""), "environment_id": environment_id, "response": payload})
                    result_payload = ((payload.get("result") or {}).get("result") or {})
                    if result_payload.get("failed_task_ids") or result_payload.get("blocked"):
                        halted = True
                return JsonRpcResponse(id=request.id, result={"graph": graph, "stage_results": stage_results, "failed_stages": failed_stages, "rollback_policy": rollback_policy})

            if request.method == "mep.federation.resolve_plan":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                tasks = list(request.params.get("tasks", []))
                required_method = str(request.params.get("required_method", "mep.multi.execute"))
                preferred_tags = list(request.params.get("preferred_tags", [])) or None
                result = self.hub.resolve_plan(tasks, required_method=required_method, preferred_tags=preferred_tags)
                return JsonRpcResponse(id=request.id, result=result)

            if request.method == "mep.federation.execute_task":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                task = dict(request.params.get("task", {}))
                preferred_tags = list(request.params.get("preferred_tags", [])) or None
                forwarded_params = dict(request.params.get("forward_params", {}))
                rollback_policy = str(request.params.get("rollback_policy", "full"))
                recovery_policy = str(request.params.get("recovery_policy", "abort"))
                resolution = self.hub.resolve_task(task, required_method="mep.multi.execute", preferred_tags=preferred_tags)
                candidates = list(resolution.get("candidates", []))
                if not candidates:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32032, "No federated execution route for task", {"task_id": task.get("task_id", "")}))
                routed = None
                environment_id = ""
                attempts = []
                for cand in candidates:
                    environment_id = str(cand["environment_id"])
                    target, target_actor, target_context = self._fallback_target(environment_id, actor, context)
                    merged_params = dict(forwarded_params)
                    bindings = self._default_bindings_for_target(target, target_actor, target_context, merged_params)
                    if bindings:
                        merged_params["bindings"] = bindings
                    merged_params.setdefault("tasks", [task])
                    merged_params.setdefault("rollback_policy", rollback_policy)
                    merged_params.setdefault("recovery_policy", recovery_policy)
                    _, routed = await self._route_request(environment_id, "mep.multi.execute", merged_params, actor, context, request.id)
                    attempts.append({"environment_id": environment_id, "ok": routed.error is None})
                    if routed.error is None:
                        if environment_id != str((resolution.get("selected") or {}).get("environment_id", environment_id)):
                            self.gateway._recovery_stats["rerouted"] += 1
                        break
                    if recovery_policy != "reroute":
                        return routed
                if routed is None or routed.error is not None:
                    return routed if routed is not None else JsonRpcResponse(id=request.id, error=JsonRpcError(-32032, "No federated execution route for task", {"task_id": task.get("task_id", "")}))
                return JsonRpcResponse(id=request.id, result={"resolution": resolution, "environment_id": environment_id, "method": "mep.multi.execute", "response": routed.to_dict(), "attempts": attempts, "recovery_policy": recovery_policy})

            if request.method == "mep.federation.execute_plan":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                tasks = list(request.params.get("tasks", []))
                preferred_tags = list(request.params.get("preferred_tags", [])) or None
                forwarded_params = dict(request.params.get("forward_params", {}))
                rollback_policy = str(request.params.get("rollback_policy", "full"))
                resolution = self.hub.resolve_plan(tasks, required_method="mep.multi.execute", preferred_tags=preferred_tags)
                executions = []
                failed_routes = []
                for group in resolution.get("groups", []):
                    environment_id = str(group["environment_id"])
                    target, target_actor, target_context = self._fallback_target(environment_id, actor, context)
                    merged_params = dict(forwarded_params)
                    bindings = self._default_bindings_for_target(target, target_actor, target_context, merged_params)
                    if bindings:
                        merged_params["bindings"] = bindings
                    merged_params["tasks"] = [item.get("task", {}) if isinstance(item, dict) and "task" in item else next((t for t in tasks if str(t.get('task_id','')) == str(item.get('task_id',''))), {}) for item in group.get("tasks", [])]
                    merged_params["rollback_policy"] = rollback_policy
                    _, routed = await self._route_request(environment_id, "mep.multi.execute", merged_params, actor, context, request.id)
                    if routed.error is not None:
                        failed_routes.append({"environment_id": environment_id, "error": routed.error.to_dict()})
                        continue
                    executions.append({"environment_id": environment_id, "task_ids": list(group.get("task_ids", [])), "response": routed.to_dict()})
                return JsonRpcResponse(id=request.id, result={"resolution": resolution, "executions": executions, "failed_routes": failed_routes, "rollback_policy": rollback_policy})
            if request.method == "mep.federation.route":
                if self.hub is None:
                    return JsonRpcResponse(id=request.id, error=JsonRpcError(-32030, "Federation hub unavailable", {"method": request.method}))
                environment_id = str(request.params.get("environment_id", ""))
                method = str(request.params.get("forward_method", ""))
                forwarded_params = dict(request.params.get("forward_params", {}))
                _, routed = await self._route_request(environment_id, method, forwarded_params, actor, context, request.id)
                if routed.error is not None:
                    return routed
                return JsonRpcResponse(id=request.id, result={"environment_id": environment_id, "method": method, "response": routed.to_dict()})
            if request.method == "mep.envelope":
                session_id = request.params.get("session_id")
                session = self.gateway.get_session(session_id) if session_id else None
                prefix = request.params.get("knowledge_prefix")
                objectives = self._mission_objectives_from_params(request.params)
                envelope = self.gateway.build_envelope(actor, context, session=session, knowledge_prefix=prefix, mission_objectives=objectives or None)
                return JsonRpcResponse(id=request.id, result=envelope.to_dict())
            if request.method == "mep.why":
                action_type = request.params.get("action_type")
                result = self.gateway.explain(actor, context, action_type=str(action_type) if action_type else None)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.why_not":
                action_type = str(request.params.get("action_type", ""))
                result = self.gateway.explain_why_not(actor, context, action_type)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.plan":
                goal = self._sense_from_params(request.params)
                max_steps = int(request.params.get("max_steps", 3))
                result = self.gateway.preview_plan(actor, goal, max_steps=max_steps)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.mission.preview":
                objectives = self._mission_objectives_from_params(request.params)
                result = self.gateway.preview_mission(actor, objectives)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.knowledge.propagate":
                key = str(request.params.get("key", ""))
                channels = list(request.params.get("channels", [])) or None
                max_hops = int(request.params.get("max_hops", 1))
                include_shared = bool(request.params.get("include_shared", False))
                shared_key = request.params.get("shared_key")
                result = self.gateway.propagate_knowledge(actor, key, channels=channels, max_hops=max_hops, include_shared=include_shared, shared_key=str(shared_key) if shared_key else None)
                return JsonRpcResponse(id=request.id, result=result)
            if request.method == "mep.execute":
                session_id = request.params.get("session_id")
                session = self.gateway.get_session(session_id) if session_id else None
                decision = MEPDecision(
                    decision=str(request.params.get("decision", "execute")),
                    action_type=str(request.params.get("action_type", "")),
                    payload=dict(request.params.get("payload", {})),
                    reasoning=str(request.params.get("reasoning", "")),
                    confidence=float(request.params.get("confidence", 0.0)),
                )
                result = await self.gateway.execute_decision(actor, context, decision, session=session)
                if hasattr(result, "to_dict"):
                    return JsonRpcResponse(id=request.id, result=result.to_dict())
                return JsonRpcResponse(id=request.id, result=result)
            return JsonRpcResponse(id=request.id, error=JsonRpcError(-32601, "Method not found", {"method": request.method}))
        except Exception as exc:  # pragma: no cover
            return JsonRpcResponse(id=request.id, error=JsonRpcError(-32000, "MEP server failure", {"exception": str(exc)}))
