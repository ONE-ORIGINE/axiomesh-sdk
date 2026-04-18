from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from edp_core.semantic import SenseVector, SENSE_NULL


class CertaintyLevel(float, Enum):
    KNOWN = 1.00
    VERIFIED = 0.95
    PROBABLE = 0.75
    ESTIMATED = 0.50
    UNCERTAIN = 0.25
    UNKNOWN = 0.00

    @classmethod
    def from_score(cls, score: float) -> "CertaintyLevel":
        if score >= 0.995:
            return cls.KNOWN
        if score >= 0.90:
            return cls.VERIFIED
        if score >= 0.65:
            return cls.PROBABLE
        if score >= 0.40:
            return cls.ESTIMATED
        if score > 0.0:
            return cls.UNCERTAIN
        return cls.UNKNOWN


class FactStatus(str, Enum):
    OBSERVED = "observed"
    DERIVED = "derived"
    STALE = "stale"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"
    EXPECTED = "expected"


@dataclass(slots=True)
class KnowledgePolicy:
    prefix: str
    default_ttl_ms: float = 0.0
    mobility: float = 0.0
    decay_rate: float = 0.98
    source_bias: dict[str, float] = field(default_factory=dict)
    contradiction_threshold: float = 0.3

    def trust_for(self, source: str) -> float:
        return self.source_bias.get(source, 1.0)


@dataclass(slots=True)
class Evidence:
    source: str
    value: Any
    weight: float = 1.0
    freshness: float = 1.0
    certainty_hint: float = 1.0
    observed_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def score(self, trust: float = 1.0) -> float:
        return max(0.0, self.weight * self.freshness * self.certainty_hint * trust)


@dataclass(slots=True)
class FactRecord:
    key: str
    value: Any
    certainty: CertaintyLevel
    source: str = "unknown"
    sense: SenseVector = field(default_factory=lambda: SENSE_NULL)
    produced_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    status: FactStatus = FactStatus.OBSERVED
    evidence: list[Evidence] = field(default_factory=list)
    contradictions: list[Evidence] = field(default_factory=list)
    revision: int = 0
    expected_value: Any = None
    fact_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    @property
    def valid(self) -> bool:
        return self.expires_at == 0.0 or time.time() < self.expires_at

    @property
    def freshness(self) -> float:
        age = max(0.0, time.time() - self.produced_at)
        return 1.0 / (1.0 + age)

    def score(self) -> float:
        return min(1.0, max(0.0, self.certainty.value * self.freshness))


@dataclass(slots=True)
class KnowledgeConstraint:
    constraint_id: str
    key: str
    comparator: str
    target: float
    weight: float = 1.0
    description: str = ""

    def residual(self, value: float) -> float:
        if self.comparator == ">=":
            return max(0.0, self.target - value)
        if self.comparator == "<=":
            return max(0.0, value - self.target)
        return abs(value - self.target)

    def energy(self, value: float) -> float:
        res = self.residual(value)
        return 0.5 * self.weight * (res ** 2)

    def holds(self, value: float) -> bool:
        if self.comparator == ">=":
            return value >= self.target
        if self.comparator == "<=":
            return value <= self.target
        return value == self.target


class KnowledgeBase:
    def __init__(self) -> None:
        self._facts: dict[str, FactRecord] = {}
        self._history: list[FactRecord] = []
        self._deltas: list[dict[str, Any]] = []
        self._policies: list[KnowledgePolicy] = []
        self._expected: dict[str, Any] = {}
        self._revalidation: list[dict[str, Any]] = []
        self._constraints: list[KnowledgeConstraint] = []

    def register_policy(self, policy: KnowledgePolicy) -> None:
        self._policies.append(policy)
        self._policies.sort(key=lambda p: len(p.prefix), reverse=True)

    def add_constraint(self, constraint: KnowledgeConstraint) -> None:
        self._constraints.append(constraint)

    def _policy_for(self, key: str) -> KnowledgePolicy | None:
        for policy in self._policies:
            if key.startswith(policy.prefix):
                return policy
        return None

    def _push_delta(self, kind: str, record: FactRecord, details: dict[str, Any] | None = None) -> None:
        self._deltas.append({
            "kind": kind,
            "key": record.key,
            "value": record.value,
            "certainty": record.certainty.name,
            "status": record.status.value,
            "source": record.source,
            "revision": record.revision,
            "expected_value": record.expected_value,
            "details": details or {},
            "at": time.time(),
        })

    def request_revalidation(self, key: str, reason: str = "") -> None:
        item = {"key": key, "reason": reason or "state changed", "at": time.time()}
        if item not in self._revalidation:
            self._revalidation.append(item)

    def put(
        self,
        key: str,
        value: Any,
        certainty: CertaintyLevel,
        source: str = "unknown",
        sense: SenseVector | None = None,
        ttl_ms: float = 0.0,
        evidence: list[Evidence] | None = None,
        status: FactStatus = FactStatus.OBSERVED,
        expected_value: Any = None,
    ) -> FactRecord:
        policy = self._policy_for(key)
        if ttl_ms <= 0 and policy and policy.default_ttl_ms > 0:
            ttl_ms = policy.default_ttl_ms
        expires_at = time.time() + ttl_ms / 1000.0 if ttl_ms > 0 else 0.0
        previous = self._facts.get(key)
        contradictions: list[Evidence] = []
        revision = (previous.revision + 1) if previous else 0
        details: dict[str, Any] = {}
        if previous is not None and previous.value != value:
            contradictions = list(previous.contradictions) + [Evidence(source=source, value=value)]
            if status == FactStatus.OBSERVED:
                status = FactStatus.CONTRADICTED
                self.request_revalidation(key, reason=f"value changed from {previous.value!r} to {value!r}")
                details["previous_value"] = previous.value
        record = FactRecord(
            key=key,
            value=value,
            certainty=certainty,
            source=source,
            sense=sense or SENSE_NULL,
            expires_at=expires_at,
            status=status,
            evidence=evidence or [],
            contradictions=contradictions,
            revision=revision,
            expected_value=self._expected.get(key) if expected_value is None else expected_value,
            fact_id=previous.fact_id if previous else str(uuid.uuid4()),
        )
        self._facts[key] = record
        self._history.append(record)
        self._push_delta("upsert", record, details=details)
        return record

    def observe(self, key: str, value: Any, source: str = "sensor", sense: SenseVector | None = None, ttl_ms: float = 0.0, weight: float = 1.0) -> FactRecord:
        return self.put(key, value, CertaintyLevel.KNOWN, source=source, sense=sense, ttl_ms=ttl_ms, evidence=[Evidence(source=source, value=value, weight=weight)], status=FactStatus.OBSERVED)

    def assert_known(self, key: str, value: Any, source: str = "sensor", sense: SenseVector | None = None, ttl_ms: float = 0.0) -> FactRecord:
        return self.put(key, value, CertaintyLevel.KNOWN, source=source, sense=sense, ttl_ms=ttl_ms, status=FactStatus.OBSERVED)

    def assert_verified(self, key: str, value: Any, source: str = "multi-sensor", sense: SenseVector | None = None, ttl_ms: float = 0.0) -> FactRecord:
        return self.put(key, value, CertaintyLevel.VERIFIED, source=source, sense=sense, ttl_ms=ttl_ms, status=FactStatus.DERIVED)

    def assert_probable(self, key: str, value: Any, source: str = "inference", sense: SenseVector | None = None, ttl_ms: float = 0.0) -> FactRecord:
        return self.put(key, value, CertaintyLevel.PROBABLE, source=source, sense=sense, ttl_ms=ttl_ms, status=FactStatus.DERIVED)

    def assert_estimated(self, key: str, value: Any, source: str = "model", sense: SenseVector | None = None, ttl_ms: float = 0.0) -> FactRecord:
        return self.put(key, value, CertaintyLevel.ESTIMATED, source=source, sense=sense, ttl_ms=ttl_ms, status=FactStatus.DERIVED)

    def expect(self, key: str, value: Any) -> None:
        self._expected[key] = value
        if key in self._facts:
            self._facts[key].expected_value = value

    def know(self, key: str) -> FactRecord | None:
        fact = self._facts.get(key)
        if fact is None:
            return None
        if not fact.valid:
            fact.status = FactStatus.STALE
            self.request_revalidation(key, reason="fact expired")
            return None
        return fact

    def value_of(self, key: str, default: Any = None) -> Any:
        fact = self.know(key)
        return fact.value if fact else default

    def certainty_of(self, key: str) -> float:
        fact = self.know(key)
        return fact.certainty.value if fact else 0.0

    def revise(self, key: str, observations: list[Evidence], sense: SenseVector | None = None) -> FactRecord:
        if not observations:
            return self.put(key, None, CertaintyLevel.UNKNOWN, source="revision", sense=sense, status=FactStatus.UNKNOWN)
        policy = self._policy_for(key)
        scores: dict[Any, float] = {}
        total = 0.0
        for evidence in observations:
            trust = policy.trust_for(evidence.source) if policy else 1.0
            score = evidence.score(trust)
            scores[evidence.value] = scores.get(evidence.value, 0.0) + score
            total += score
        winner, winner_score = max(scores.items(), key=lambda pair: pair[1])
        certainty = CertaintyLevel.from_score(winner_score / max(total, 1e-9))
        status = FactStatus.DERIVED
        return self.put(key, winner, certainty, source="revision", sense=sense, evidence=observations, status=status)

    def revise_numeric(self, key: str, observations: list[Evidence], sense: SenseVector | None = None) -> FactRecord:
        if not observations:
            return self.put(key, 0.0, CertaintyLevel.UNKNOWN, source="numeric-revision", sense=sense, status=FactStatus.UNKNOWN)
        policy = self._policy_for(key)
        total_weight = 0.0
        weighted_sum = 0.0
        spread_inputs: list[float] = []
        for evidence in observations:
            trust = policy.trust_for(evidence.source) if policy else 1.0
            score = evidence.score(trust)
            value = float(evidence.value)
            weighted_sum += value * score
            total_weight += score
            spread_inputs.append(value)
        fused = weighted_sum / max(total_weight, 1e-9)
        spread = (max(spread_inputs) - min(spread_inputs)) if len(spread_inputs) > 1 else 0.0
        certainty = CertaintyLevel.from_score(max(0.0, 1.0 - spread / 10.0))
        status = FactStatus.CONTRADICTED if policy and spread > policy.contradiction_threshold else FactStatus.DERIVED
        if status == FactStatus.CONTRADICTED:
            self.request_revalidation(key, reason=f"numeric spread={spread:.3f}")
        return self.put(key, round(fused, 6), certainty, source="fusion", sense=sense, evidence=observations, status=status)

    def deltas_since(self, offset: int = 0) -> list[dict[str, Any]]:
        return self._deltas[offset:]

    def all_facts(self, prefix: str | None = None) -> list[FactRecord]:
        facts = list(self._facts.values())
        if prefix:
            facts = [fact for fact in facts if fact.key.startswith(prefix)]
        return sorted(facts, key=lambda fact: fact.key)

    def expected_world(self, prefix: str | None = None) -> list[dict[str, Any]]:
        items = [{"key": key, "value": value} for key, value in sorted(self._expected.items())]
        if prefix:
            items = [item for item in items if item["key"].startswith(prefix)]
        return items

    def revalidation_queue(self, prefix: str | None = None) -> list[dict[str, Any]]:
        items = self._revalidation
        if prefix:
            items = [item for item in items if item["key"].startswith(prefix)]
        return items

    def contradiction_energy(self, prefix: str | None = None) -> float:
        total = 0.0
        for fact in self.all_facts(prefix):
            total += 0.1 * len(fact.contradictions)
        return round(total, 6)

    def constraint_report(self, prefix: str | None = None) -> list[dict[str, Any]]:
        out = []
        for constraint in self._constraints:
            if prefix and not constraint.key.startswith(prefix):
                continue
            value = float(self.value_of(constraint.key, 0.0) or 0.0)
            out.append({
                "constraint_id": constraint.constraint_id,
                "key": constraint.key,
                "holds": constraint.holds(value),
                "value": value,
                "target": constraint.target,
                "comparator": constraint.comparator,
                "energy": round(constraint.energy(value), 6),
                "description": constraint.description,
            })
        return out

    def reconcile_expected(self, prefix: str | None = None, tolerance: float = 0.2) -> list[dict[str, Any]]:
        anomalies = []
        for key, expected in self._expected.items():
            if prefix and not key.startswith(prefix):
                continue
            fact = self._facts.get(key)
            if fact is None:
                anomalies.append({"key": key, "reason": "missing", "expected": expected, "observed": None})
                self.request_revalidation(key, reason="expected fact missing")
                continue
            observed = fact.value
            mismatch = False
            if isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
                mismatch = abs(float(expected) - float(observed)) > tolerance
            else:
                mismatch = expected != observed
            if mismatch:
                anomalies.append({"key": key, "reason": "mismatch", "expected": expected, "observed": observed})
                self.request_revalidation(key, reason=f"expected {expected!r} observed {observed!r}")
        return anomalies

    def knowledge_tension(self, prefix: str | None = None) -> float:
        constraint_energy = sum(item["energy"] for item in self.constraint_report(prefix))
        contradiction = self.contradiction_energy(prefix)
        expectation = 0.1 * len(self.reconcile_expected(prefix))
        return round(constraint_energy + contradiction + expectation, 6)
