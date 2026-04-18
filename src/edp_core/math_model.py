from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .semantic import SenseVector


@dataclass(slots=True)
class NodeMatrix:
    node_id: str
    values: list[list[float]]
    labels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SemanticEdge:
    source_id: str
    target_id: str
    sense: SenseVector
    precision: list[list[float]] | None = None
    freshness: float = 1.0
    energy: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "sense": self.sense.meaning,
            "sense_vector": self.sense.as_list(),
            "freshness": self.freshness,
            "precision": self.precision,
            "energy": self.energy,
        }


@dataclass(slots=True)
class FactorVariable:
    variable_id: str
    value: float
    certainty: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "variable_id": self.variable_id,
            "value": self.value,
            "certainty": self.certainty,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ConstraintFactor:
    factor_id: str
    description: str
    value: float
    target: float
    weight: float = 1.0
    comparator: str = "=="
    variable_ids: list[str] = field(default_factory=list)

    @property
    def residual(self) -> float:
        if self.comparator == ">=":
            return max(0.0, self.target - self.value)
        if self.comparator == "<=":
            return max(0.0, self.value - self.target)
        return self.value - self.target

    @property
    def energy(self) -> float:
        return 0.5 * self.weight * (self.residual ** 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "factor_id": self.factor_id,
            "description": self.description,
            "value": self.value,
            "target": self.target,
            "weight": self.weight,
            "comparator": self.comparator,
            "variable_ids": self.variable_ids,
            "residual": round(self.residual, 6),
            "energy": round(self.energy, 6),
        }


@dataclass(slots=True)
class FactorGraph:
    variables: dict[str, FactorVariable] = field(default_factory=dict)
    factors: list[ConstraintFactor] = field(default_factory=list)

    def add_variable(self, variable: FactorVariable) -> None:
        self.variables[variable.variable_id] = variable

    def add_factor(self, factor: ConstraintFactor) -> None:
        self.factors.append(factor)

    def total_energy(self) -> float:
        return round(sum(f.energy for f in self.factors), 6)

    def marginal_tension(self) -> dict[str, float]:
        tension: dict[str, float] = {vid: 0.0 for vid in self.variables}
        for factor in self.factors:
            share = factor.energy / max(len(factor.variable_ids), 1)
            for variable_id in factor.variable_ids:
                tension[variable_id] = round(tension.get(variable_id, 0.0) + share, 6)
        return tension

    def least_energy_targets(self) -> dict[str, float]:
        accum: dict[str, float] = {}
        weights: dict[str, float] = {}
        for factor in self.factors:
            if not factor.variable_ids:
                continue
            for variable_id in factor.variable_ids:
                accum[variable_id] = accum.get(variable_id, 0.0) + factor.target * factor.weight
                weights[variable_id] = weights.get(variable_id, 0.0) + factor.weight
        out: dict[str, float] = {}
        for variable_id, variable in self.variables.items():
            if variable_id in weights and weights[variable_id] > 0:
                out[variable_id] = round(accum[variable_id] / weights[variable_id], 6)
            else:
                out[variable_id] = variable.value
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "variables": {key: value.to_dict() for key, value in self.variables.items()},
            "factors": [factor.to_dict() for factor in self.factors],
            "total_energy": self.total_energy(),
            "marginal_tension": self.marginal_tension(),
            "least_energy_targets": self.least_energy_targets(),
        }


@dataclass(slots=True)
class SemanticGraph:
    nodes: dict[str, NodeMatrix] = field(default_factory=dict)
    edges: list[SemanticEdge] = field(default_factory=list)

    def add_node(self, node: NodeMatrix) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: SemanticEdge) -> None:
        self.edges.append(edge)

    def adjacency_matrix(self) -> list[list[float]]:
        node_ids = list(self.nodes)
        index = {node_id: i for i, node_id in enumerate(node_ids)}
        mat = [[0.0 for _ in node_ids] for _ in node_ids]
        for edge in self.edges:
            if edge.source_id in index and edge.target_id in index:
                mat[index[edge.source_id]][index[edge.target_id]] = round(edge.freshness * max(edge.sense.magnitude, 0.0), 4)
        return mat

    def laplacian_matrix(self) -> list[list[float]]:
        adj = self.adjacency_matrix()
        n = len(adj)
        lap = [[0.0 for _ in range(n)] for _ in range(n)]
        for i in range(n):
            degree = sum(adj[i])
            lap[i][i] = round(degree, 4)
            for j in range(n):
                if i != j and adj[i][j] != 0.0:
                    lap[i][j] = round(-adj[i][j], 4)
        return lap

    def total_energy(self) -> float:
        return round(sum(edge.energy for edge in self.edges), 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {
                nid: {
                    "values": node.values,
                    "labels": node.labels,
                    "metadata": node.metadata,
                }
                for nid, node in self.nodes.items()
            },
            "edges": [edge.to_dict() for edge in self.edges],
            "adjacency_matrix": self.adjacency_matrix(),
            "laplacian_matrix": self.laplacian_matrix(),
            "total_energy": self.total_energy(),
        }


@dataclass(slots=True)
class MathematicalEnvironmentExport:
    value_matrix: list[list[float]]
    certainty_matrix: list[list[float]]
    context_matrix: list[list[float]]
    graph: SemanticGraph
    factors: list[ConstraintFactor] = field(default_factory=list)
    factor_graph: FactorGraph = field(default_factory=FactorGraph)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def factor_energy(self) -> float:
        return round(sum(f.energy for f in self.factors), 6)

    @property
    def total_tension(self) -> float:
        return round(self.factor_energy + self.graph.total_energy(), 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value_matrix": self.value_matrix,
            "certainty_matrix": self.certainty_matrix,
            "context_matrix": self.context_matrix,
            "graph": self.graph.to_dict(),
            "factors": [factor.to_dict() for factor in self.factors],
            "factor_graph": self.factor_graph.to_dict(),
            "factor_energy": self.factor_energy,
            "total_tension": self.total_tension,
            "metadata": self.metadata,
        }
