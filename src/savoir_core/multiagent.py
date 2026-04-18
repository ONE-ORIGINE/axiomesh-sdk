from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .certainty import CertaintyLevel, Evidence, FactRecord, KnowledgeBase, KnowledgePolicy


@dataclass(slots=True)
class AgentKnowledgeView:
    agent_id: str
    local_facts: list[dict[str, Any]] = field(default_factory=list)
    shared_facts: list[dict[str, Any]] = field(default_factory=list)
    local_tension: float = 0.0
    shared_tension: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "local_facts": self.local_facts,
            "shared_facts": self.shared_facts,
            "local_tension": self.local_tension,
            "shared_tension": self.shared_tension,
        }


class SharedKnowledgeMesh:
    def __init__(self, shared: KnowledgeBase | None = None):
        self.shared = shared or KnowledgeBase()
        self.locals: dict[str, KnowledgeBase] = {}
        self._policies: list[KnowledgePolicy] = []
        self._neighbors: dict[str, set[str]] = {}
        self._links: dict[str, dict[str, dict[str, Any]]] = {}

    def register_policy(self, policy: KnowledgePolicy) -> None:
        self._policies.append(policy)
        self.shared.register_policy(policy)
        for kb in self.locals.values():
            kb.register_policy(policy)

    def local(self, agent_id: str) -> KnowledgeBase:
        if agent_id not in self.locals:
            kb = KnowledgeBase()
            for policy in self._policies:
                kb.register_policy(policy)
            self.locals[agent_id] = kb
        return self.locals[agent_id]

    def observe(self, agent_id: str, key: str, value: Any, source: str = "sensor", share: bool = False) -> FactRecord:
        local = self.local(agent_id).observe(key, value, source=source)
        if share:
            self.shared.observe(key, value, source=f"{agent_id}:{source}")
        return local

    def expect(self, agent_id: str, key: str, value: Any, share: bool = False) -> None:
        self.local(agent_id).expect(key, value)
        if share:
            self.shared.expect(key, value)

    def revise_numeric(self, agent_id: str, key: str, observations: list[Evidence], share: bool = False):
        local_record = self.local(agent_id).revise_numeric(key, observations)
        if share:
            shared_obs = [Evidence(source=f"{agent_id}:{obs.source}", value=obs.value, weight=obs.weight, freshness=obs.freshness, certainty_hint=obs.certainty_hint, metadata=dict(obs.metadata)) for obs in observations]
            self.shared.revise_numeric(key, shared_obs)
        return local_record

    def publish_fact(self, agent_id: str, key: str, shared_key: str | None = None) -> None:
        fact = self.local(agent_id).know(key)
        if fact is None:
            return
        self.shared.put(shared_key or key, fact.value, fact.certainty, source=f"{agent_id}:{fact.source}", sense=fact.sense, status=fact.status, expected_value=fact.expected_value)

    def sync_prefix(self, agent_id: str, prefix: str) -> None:
        local = self.local(agent_id)
        for fact in local.all_facts(prefix):
            self.shared.put(fact.key, fact.value, fact.certainty, source=f"{agent_id}:{fact.source}", sense=fact.sense, status=fact.status, expected_value=fact.expected_value)

    def agent_view(self, agent_id: str, prefix: str | None = None) -> AgentKnowledgeView:
        local = self.local(agent_id)
        local_facts = [
            {"key": fact.key, "value": fact.value, "certainty": fact.certainty.name, "status": fact.status.value, "source": fact.source}
            for fact in local.all_facts(prefix)
        ]
        shared_facts = [
            {"key": fact.key, "value": fact.value, "certainty": fact.certainty.name, "status": fact.status.value, "source": fact.source}
            for fact in self.shared.all_facts(prefix)
        ]
        return AgentKnowledgeView(
            agent_id=agent_id,
            local_facts=local_facts,
            shared_facts=shared_facts,
            local_tension=local.knowledge_tension(prefix),
            shared_tension=self.shared.knowledge_tension(prefix),
        )

    def shared_snapshot(self, prefix: str | None = None) -> dict[str, Any]:
        return {
            "facts": [
                {"key": fact.key, "value": fact.value, "certainty": fact.certainty.name, "status": fact.status.value, "source": fact.source}
                for fact in self.shared.all_facts(prefix)
            ],
            "expected": self.shared.expected_world(prefix),
            "revalidation": self.shared.revalidation_queue(prefix),
            "constraints": self.shared.constraint_report(prefix),
            "tension": self.shared.knowledge_tension(prefix),
        }


    def connect(self, left_agent_id: str, right_agent_id: str, channel: str = 'all', relation: str = 'peer', max_hops: int = 1) -> None:
        self._neighbors.setdefault(left_agent_id, set()).add(right_agent_id)
        self._neighbors.setdefault(right_agent_id, set()).add(left_agent_id)
        self._links.setdefault(left_agent_id, {})[right_agent_id] = {'channel': channel, 'relation': relation, 'max_hops': max_hops}
        self._links.setdefault(right_agent_id, {})[left_agent_id] = {'channel': channel, 'relation': relation, 'max_hops': max_hops}

    def neighbors_of(self, agent_id: str, channels: list[str] | None = None) -> list[str]:
        if not channels or 'all' in channels:
            return sorted(self._neighbors.get(agent_id, set()))
        allowed = set(channels)
        out = []
        for neighbor in sorted(self._neighbors.get(agent_id, set())):
            meta = self._links.get(agent_id, {}).get(neighbor, {})
            if meta.get('channel', 'all') in allowed:
                out.append(neighbor)
        return out

    def publish_to_neighbors(self, agent_id: str, key: str, shared_key: str | None = None, channels: list[str] | None = None, max_hops: int = 1) -> None:
        fact = self.local(agent_id).know(key)
        if fact is None:
            return
        queue: list[tuple[str, int]] = [(agent_id, 0)]
        seen = {agent_id}
        allowed = set(channels or ['all'])
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_hops:
                continue
            for neighbor in self._neighbors.get(current, set()):
                meta = self._links.get(current, {}).get(neighbor, {'channel': 'all'})
                if channels and meta.get('channel', 'all') not in allowed:
                    continue
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                self.local(neighbor).put(shared_key or key, fact.value, fact.certainty, source=f"neighbor:{agent_id}:{fact.source}", sense=fact.sense, status=fact.status, expected_value=fact.expected_value)
                queue.append((neighbor, depth + 1))

    def publish_scoped(self, agent_id: str, key: str, shared_key: str | None = None, channels: list[str] | None = None, max_hops: int = 1, include_shared: bool = False) -> None:
        self.publish_to_neighbors(agent_id, key, shared_key=shared_key, channels=channels, max_hops=max_hops)
        if include_shared:
            self.publish_fact(agent_id, key, shared_key=shared_key)

    def neighborhood_snapshot(self, agent_id: str, prefix: str | None = None, channels: list[str] | None = None, max_hops: int = 1) -> dict[str, Any]:
        visible: list[dict[str, Any]] = []
        queue: list[tuple[str, int]] = [(agent_id, 0)]
        seen = {agent_id}
        allowed = set(channels or ['all'])
        while queue:
            current, depth = queue.pop(0)
            if depth >= max_hops:
                continue
            for neighbor in self._neighbors.get(current, set()):
                meta = self._links.get(current, {}).get(neighbor, {'channel': 'all', 'relation': 'peer'})
                if channels and meta.get('channel', 'all') not in allowed:
                    continue
                if neighbor in seen:
                    continue
                seen.add(neighbor)
                for fact in self.local(neighbor).all_facts(prefix):
                    visible.append({
                        'neighbor_id': neighbor,
                        'key': fact.key,
                        'value': fact.value,
                        'certainty': fact.certainty.name,
                        'status': fact.status.value,
                        'source': fact.source,
                        'channel': meta.get('channel', 'all'),
                        'relation': meta.get('relation', 'peer'),
                        'hops': depth + 1,
                    })
                queue.append((neighbor, depth + 1))
        return {
            'agent_id': agent_id,
            'neighbors': self.neighbors_of(agent_id, channels=channels),
            'visible_facts': visible,
        }
