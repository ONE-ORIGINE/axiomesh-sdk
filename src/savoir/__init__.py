"""Compatibility shim for older `savoir` imports."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from savoir_core import CertaintyLevel, KnowledgeBase


class EnvironmentalStateMatrix:
    def __init__(self, element_ids: list[str] | None = None, property_dims: list[str] | None = None):
        self.element_ids = list(element_ids or [])
        self.property_dims = list(property_dims or [])
        self._matrix: dict[str, dict[str, tuple[float, float]]] = {
            eid: {dim: (0.0, 0.0) for dim in self.property_dims} for eid in self.element_ids
        }

    def set(self, element_id: str, prop: str, value: float, certainty: float = 1.0):
        if element_id not in self._matrix:
            self._matrix[element_id] = {dim: (0.0, 0.0) for dim in self.property_dims}
            self.element_ids.append(element_id)
        if prop not in self.property_dims:
            self.property_dims.append(prop)
            for row in self._matrix.values():
                row.setdefault(prop, (0.0, 0.0))
        self._matrix[element_id][prop] = (float(value), float(certainty))

    def get(self, element_id: str, prop: str) -> tuple[float, float]:
        return self._matrix.get(element_id, {}).get(prop, (0.0, 0.0))

    def certainty_of(self, element_id: str, prop: str) -> float:
        return self.get(element_id, prop)[1]

    def flatten(self) -> list[float]:
        out: list[float] = []
        for eid in self.element_ids:
            for dim in self.property_dims:
                v, c = self.get(eid, dim)
                out.extend([v, c])
        return out

    def average_certainty(self) -> float:
        vals = [c for row in self._matrix.values() for _, c in row.values()]
        return sum(vals) / len(vals) if vals else 0.0


class ReactionTransitionMatrix:
    def __init__(self):
        self._matrix: dict[str, dict[str, float]] = {}

    def register(self, action_type: str, effects: dict[str, float]):
        self._matrix[action_type] = dict(effects)

    def expected_effects(self, action_type: str) -> dict[str, float]:
        return dict(self._matrix.get(action_type, {}))


class Savoir(KnowledgeBase):
    def __init__(self, element_ids: list[str] | None = None, property_dims: list[str] | None = None):
        super().__init__()
        self.state_matrix = EnvironmentalStateMatrix(element_ids, property_dims)
        self.transition_matrix = ReactionTransitionMatrix()

    def record_action_outcome(self, action_type: str, element_id: str, payload: dict[str, Any], certainty: CertaintyLevel):
        effects = self.transition_matrix.expected_effects(action_type)
        for dim, delta in effects.items():
            current_value, _ = self.state_matrix.get(element_id, dim)
            new_value = float(payload.get(dim, current_value + delta))
            self.state_matrix.set(element_id, dim, new_value, certainty.value)
            self.assert_known(f"{element_id}.{dim}", new_value, source=f"action:{action_type}")

    @property
    def known_count(self) -> int:
        return len(self.all_facts())

    def to_llm_context(self, prefix: str | None = None) -> str:
        facts = self.all_facts(prefix)
        return "\n".join(f"- {fact.key}={fact.value!r} [{fact.certainty.name}]" for fact in facts)


__all__ = [
    "CertaintyLevel",
    "EnvironmentalStateMatrix",
    "ReactionTransitionMatrix",
    "Savoir",
]
