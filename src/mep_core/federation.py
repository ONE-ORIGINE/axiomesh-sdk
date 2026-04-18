from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from edp_core import TaskSpec

from .registry import MEP_VERSION
from .spec import FederationCard


@dataclass(slots=True)
class FederatedEnvironment:
    environment_id: str
    name: str
    gateway: Any
    tags: list[str] = field(default_factory=list)

    def card(self) -> dict[str, Any]:
        env = self.gateway.environment_card().to_dict()
        env["environment_id"] = self.environment_id
        env["name"] = self.name
        env["tags"] = self.tags
        return env


class FederatedMEPHub:
    def __init__(self, federation_id: str | None = None):
        self.federation_id = federation_id or str(uuid.uuid4())
        self.environments: dict[str, FederatedEnvironment] = {}

    def register(self, name: str, gateway: Any, environment_id: str | None = None, tags: list[str] | None = None) -> str:
        env_id = environment_id or str(uuid.uuid4())
        self.environments[env_id] = FederatedEnvironment(environment_id=env_id, name=name, gateway=gateway, tags=list(tags or []))
        try:
            gateway.environment_id = env_id
        except Exception:
            pass
        return env_id

    def resolve(self, environment_id: str) -> FederatedEnvironment | None:
        return self.environments.get(environment_id)

    def routes(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for env_id, env in self.environments.items():
            items.append({
                'environment_id': env_id,
                'name': env.name,
                'methods': [
                    'mep.envelope', 'mep.multi.assign', 'mep.multi.negotiate', 'mep.multi.execute',
                    'mep.plan', 'mep.mission.preview', 'mep.provenance.trace', 'mep.provenance.verify', 'mep.fault.inject', 'mep.fault.clear', 'mep.fault.status', 'mep.federation.resolve_task', 'mep.federation.route_task', 'mep.federation.resolve_plan', 'mep.federation.execute_task', 'mep.federation.execute_plan', 'mep.federation.mission_graph', 'mep.federation.execute_mission', 'mep.federation.provenance', 'mep.federation.provenance.verify'
                ],
            })
        return items


    def federated_provenance_trace(self, limit: int | None = None) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for env_id, env in self.environments.items():
            for item in env.gateway.provenance_trace(limit=limit):
                merged = dict(item)
                merged.setdefault("environment_id", env_id)
                items.append(merged)
        items.sort(key=lambda item: (item.get("at", 0.0), item.get("chain_index", 0)))
        if limit is not None:
            items = items[-limit:]
        return {"items": items, "count": len(items)}

    def verify_federated_provenance(self) -> dict[str, Any]:
        reports = []
        for env_id, env in self.environments.items():
            report = env.gateway.verify_provenance()
            reports.append({"environment_id": env_id, "name": env.name, **report})
        return {"ok": all(r["ok"] for r in reports), "reports": reports}

    def environment_cards(self) -> list[dict[str, Any]]:
        return [env.card() for env in self.environments.values()]

    def federation_card(self) -> FederationCard:
        return FederationCard(protocol="MEP", version=MEP_VERSION, federation_id=self.federation_id, environments=self.environment_cards(), routes=self.routes())

    def resolve_task(self, task: dict[str, Any] | TaskSpec, required_method: str = "mep.multi.negotiate", preferred_tags: list[str] | None = None) -> dict[str, Any]:
        task_obj = task if isinstance(task, TaskSpec) else TaskSpec(
            task_id=str(task.get('task_id', 'task')),
            description=str(task.get('description', 'task')),
            goal_dimension=str(task.get('goal_dimension', 'technical')),
            goal_meaning=str(task.get('goal_meaning', 'task')),
            goal_magnitude=float(task.get('goal_magnitude', 0.8)),
            required_roles=list(task.get('required_roles', [])),
            preferred_contexts=list(task.get('preferred_contexts', [])),
            target_agent_ids=list(task.get('target_agent_ids', [])),
            depends_on=list(task.get('depends_on', [])),
            channel=str(task.get('channel', 'all')),
            payload=dict(task.get('payload', {})),
            mission_policy=dict(task.get('mission_policy', {})),
            preferred_environment_tags=list(task.get('preferred_environment_tags', [])),
        )
        tags = list(preferred_tags or task_obj.preferred_environment_tags)
        route_defs = {r['environment_id']: set(r.get('methods', [])) for r in self.routes()}
        scored: list[dict[str, Any]] = []
        for env_id, env in self.environments.items():
            card = env.card()
            actions = set(card.get('supported_actions', []))
            contexts = set(card.get('contexts', []))
            methods = route_defs.get(env_id, set())
            if required_method and required_method not in methods:
                continue
            score = 0.0
            if tags:
                score += 0.2 * len(set(tags) & set(env.tags))
            if task_obj.preferred_contexts:
                score += 0.15 * len(set(task_obj.preferred_contexts) & contexts)
            hint = str(task_obj.payload.get('action_type_hint', '')).strip()
            if hint and hint in actions:
                score += 0.35
            if task_obj.channel == 'internal' and 'drone' in env.tags:
                score += 0.05
            scored.append({
                'environment_id': env_id,
                'name': env.name,
                'tags': list(env.tags),
                'score': round(score, 6),
                'matched_contexts': sorted(set(task_obj.preferred_contexts) & contexts),
                'matched_actions': [hint] if hint and hint in actions else [],
                'methods': sorted(methods),
            })
        scored.sort(key=lambda item: item['score'], reverse=True)
        return {
            'task_id': task_obj.task_id,
            'required_method': required_method,
            'preferred_tags': tags,
            'candidates': scored,
            'selected': scored[0] if scored else None,
        }



    def build_mission_graph(self, tasks: list[dict[str, Any] | TaskSpec], required_method: str = "mep.multi.execute", preferred_tags: list[str] | None = None) -> dict[str, Any]:
        task_objs = [task if isinstance(task, TaskSpec) else TaskSpec(
            task_id=str(task.get('task_id', 'task')),
            description=str(task.get('description', 'task')),
            goal_dimension=str(task.get('goal_dimension', 'technical')),
            goal_meaning=str(task.get('goal_meaning', 'task')),
            goal_magnitude=float(task.get('goal_magnitude', 0.8)),
            required_roles=list(task.get('required_roles', [])),
            preferred_contexts=list(task.get('preferred_contexts', [])),
            target_agent_ids=list(task.get('target_agent_ids', [])),
            depends_on=list(task.get('depends_on', [])),
            channel=str(task.get('channel', 'all')),
            payload=dict(task.get('payload', {})),
            mission_policy=dict(task.get('mission_policy', {})),
            preferred_environment_tags=list(task.get('preferred_environment_tags', [])),
        ) for task in tasks]
        task_map = {task.task_id: task for task in task_objs}
        resolutions = [self.resolve_task(task, required_method=required_method, preferred_tags=preferred_tags) for task in task_objs]
        resolution_by_id = {str(item.get('task_id', '')): item for item in resolutions}
        selected_env = {tid: (resolution_by_id[tid].get('selected') or {}).get('environment_id') for tid in resolution_by_id}

        indegree = {task.task_id: 0 for task in task_objs}
        edges: dict[str, list[str]] = {task.task_id: [] for task in task_objs}
        for task in task_objs:
            for dep in task.depends_on:
                if dep in task_map:
                    edges.setdefault(dep, []).append(task.task_id)
                    indegree[task.task_id] += 1
        queue = sorted([tid for tid, deg in indegree.items() if deg == 0])
        layers: list[list[str]] = []
        seen: set[str] = set()
        while queue:
            current = list(queue)
            queue = []
            layer: list[str] = []
            for tid in current:
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
                queue = sorted(set(queue))
        remaining = [tid for tid in task_map if tid not in seen]
        if remaining:
            layers.append(sorted(remaining))

        stages: list[dict[str, Any]] = []
        node_views: list[dict[str, Any]] = []
        env_stage_ids: dict[tuple[int, str], str] = {}
        unresolved: list[dict[str, Any]] = []
        cross_environment_edges: list[dict[str, Any]] = []

        for task in task_objs:
            selected = (resolution_by_id[task.task_id].get('selected') or None)
            node_views.append({
                'task_id': task.task_id,
                'description': task.description,
                'depends_on': list(task.depends_on),
                'environment_id': selected.get('environment_id') if selected else None,
                'environment_name': selected.get('name') if selected else '',
                'score': float(selected.get('score', 0.0)) if selected else 0.0,
                'channel': task.channel,
            })
            if selected is None:
                unresolved.append({'task_id': task.task_id, 'reason': 'no route'})

        for layer_idx, layer in enumerate(layers):
            grouped: dict[str, list[str]] = {}
            for tid in layer:
                env_id = selected_env.get(tid)
                if not env_id:
                    continue
                grouped.setdefault(str(env_id), []).append(tid)
            for env_id, task_ids in sorted(grouped.items()):
                env = self.environments.get(env_id)
                stage_id = f"stage-{layer_idx}-{env_id[:8]}"
                env_stage_ids[(layer_idx, env_id)] = stage_id
                stages.append({
                    'stage_id': stage_id,
                    'index': layer_idx,
                    'environment_id': env_id,
                    'environment_name': env.name if env else '',
                    'task_ids': task_ids,
                    'tasks': [task_map[tid].to_dict() for tid in task_ids if tid in task_map],
                })

        edge_views: list[dict[str, Any]] = []
        for task in task_objs:
            for dep in task.depends_on:
                if dep not in task_map:
                    continue
                dep_env = selected_env.get(dep)
                task_env = selected_env.get(task.task_id)
                edge = {'from': dep, 'to': task.task_id, 'cross_environment': bool(dep_env and task_env and dep_env != task_env)}
                edge_views.append(edge)
                if edge['cross_environment']:
                    cross_environment_edges.append(edge)

        return {
            'required_method': required_method,
            'nodes': node_views,
            'edges': edge_views,
            'layers': layers,
            'stages': stages,
            'cross_environment_edges': cross_environment_edges,
            'unresolved': unresolved,
            'environment_count': len({stage['environment_id'] for stage in stages}),
            'stage_count': len(stages),
            'task_count': len(task_objs),
        }

    def resolve_plan(self, tasks: list[dict[str, Any] | TaskSpec], required_method: str = "mep.multi.execute", preferred_tags: list[str] | None = None) -> dict[str, Any]:
        resolutions = [self.resolve_task(task, required_method=required_method, preferred_tags=preferred_tags) for task in tasks]
        grouped: dict[str, dict[str, Any]] = {}
        unresolved: list[dict[str, Any]] = []
        for item in resolutions:
            selected = item.get('selected')
            if not selected:
                unresolved.append({'task_id': item.get('task_id', ''), 'required_method': item.get('required_method', required_method), 'reason': 'no route'})
                continue
            bucket = grouped.setdefault(str(selected['environment_id']), {
                'environment_id': str(selected['environment_id']),
                'name': str(selected.get('name', '')),
                'score': float(selected.get('score', 0.0)),
                'tasks': [],
                'task_ids': [],
            })
            task_id = str(item.get('task_id', ''))
            bucket['tasks'].append(item)
            bucket['task_ids'].append(task_id)
            bucket['score'] += float(selected.get('score', 0.0))
        ordered = sorted(grouped.values(), key=lambda item: (-len(item['task_ids']), -item['score'], item['environment_id']))
        return {
            'required_method': required_method,
            'groups': ordered,
            'unresolved': unresolved,
            'candidate_count': len(resolutions),
        }
