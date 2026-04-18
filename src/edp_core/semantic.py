from __future__ import annotations

import math
from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple

DIMS = 8

class SemanticDim(IntEnum):
    CAUSAL = 0
    TEMPORAL = 1
    SPATIAL = 2
    NORMATIVE = 3
    SOCIAL = 4
    FINANCIAL = 5
    TECHNICAL = 6
    EMERGENT = 7


@dataclass(frozen=True)
class SenseVector:
    dimension: str
    meaning: str
    magnitude: float
    values: Tuple[float, ...]

    @classmethod
    def of(cls, dim: str, meaning: str, axis: SemanticDim, mag: float = 1.0) -> "SenseVector":
        values = [0.0] * DIMS
        values[int(axis)] = mag
        return cls(dim, meaning, mag, tuple(values))

    @classmethod
    def causal(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("causal", meaning, SemanticDim.CAUSAL, mag)

    @classmethod
    def temporal(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("temporal", meaning, SemanticDim.TEMPORAL, mag)

    @classmethod
    def spatial(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("spatial", meaning, SemanticDim.SPATIAL, mag)

    @classmethod
    def normative(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("normative", meaning, SemanticDim.NORMATIVE, mag)

    @classmethod
    def social(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("social", meaning, SemanticDim.SOCIAL, mag)

    @classmethod
    def financial(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("financial", meaning, SemanticDim.FINANCIAL, mag)

    @classmethod
    def technical(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("technical", meaning, SemanticDim.TECHNICAL, mag)

    @classmethod
    def emergent(cls, meaning: str, mag: float = 1.0) -> "SenseVector":
        return cls.of("emergent", meaning, SemanticDim.EMERGENT, mag)

    def dot(self, other: "SenseVector") -> float:
        return sum(a * b for a, b in zip(self.values, other.values))

    def norm(self) -> float:
        return math.sqrt(sum(v * v for v in self.values))

    def cosine(self, other: "SenseVector") -> float:
        na = self.norm()
        nb = other.norm()
        if na == 0.0 or nb == 0.0:
            return 0.0
        return self.dot(other) / (na * nb)

    def angular_distance(self, other: "SenseVector") -> float:
        return math.acos(max(-1.0, min(1.0, self.cosine(other)))) / math.pi

    def apply_context_operator(self, context: "SenseVector", alpha: float = 0.7) -> "SenseVector":
        hadamard = tuple(a * b for a, b in zip(self.values, context.values))
        mixed = tuple(alpha * a + (1.0 - alpha) * h for a, h in zip(self.values, hadamard))
        norm = math.sqrt(sum(v * v for v in mixed)) or 1.0
        return SenseVector(self.dimension, f"{self.meaning}@{context.meaning}", self.magnitude, tuple(v / norm for v in mixed))

    def delta(self, other: "SenseVector") -> "SenseVector":
        d = tuple(b - a for a, b in zip(self.values, other.values))
        mag = math.sqrt(sum(v * v for v in d))
        return SenseVector("delta", f"Δ({self.meaning}->{other.meaning})", mag, d)

    def as_list(self) -> list[float]:
        return list(self.values)

    def __repr__(self) -> str:
        return f"φ({self.dimension}:{self.meaning}|{self.magnitude:.2f}|)"


SENSE_NULL = SenseVector("none", "", 0.0, tuple([0.0] * DIMS))


@dataclass(slots=True)
class HarmonyProfile:
    context_alignment: float
    semantic_alignment: float
    reaction_coherence: float
    dissonance: float
    action_type: str = ""
    alpha: float = 0.35
    beta: float = 0.30
    gamma: float = 0.25
    delta: float = 0.10

    @property
    def score(self) -> float:
        return (
            self.alpha * self.context_alignment
            + self.beta * self.semantic_alignment
            + self.gamma * self.reaction_coherence
            - self.delta * self.dissonance
        )

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type,
            "score": round(self.score, 4),
            "context_alignment": round(self.context_alignment, 4),
            "semantic_alignment": round(self.semantic_alignment, 4),
            "reaction_coherence": round(self.reaction_coherence, 4),
            "dissonance": round(self.dissonance, 4),
        }


def compute_harmony(
    action_vec: SenseVector,
    context_vec: SenseVector,
    current_vec: SenseVector,
    expected_reaction: SenseVector | None = None,
    observed_reaction: SenseVector | None = None,
    action_type: str = "",
) -> HarmonyProfile:
    ctx = action_vec.cosine(context_vec)
    sem = action_vec.cosine(current_vec) if current_vec != SENSE_NULL else ctx
    coherence = 0.0
    dissonance = 0.0
    if expected_reaction and observed_reaction:
        coherence = expected_reaction.cosine(observed_reaction)
        dissonance = min(1.0, expected_reaction.delta(observed_reaction).magnitude)
    return HarmonyProfile(ctx, sem, coherence, dissonance, action_type=action_type)
