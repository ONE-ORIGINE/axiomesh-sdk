"""Compatibility shim for older `edp` imports.

This exposes the new runtime under names close to the legacy triplet,
so existing demos can migrate incrementally.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from edp_core import (
    Action,
    ActionCategory,
    Context,
    ContextKind,
    Circumstance,
    Element,
    Environment,
    EnvironmentKind,
    HarmonyProfile,
    ReactionRecord,
    RuleMode,
    RuntimeStatus,
    SenseVector,
    SemanticGraph,
    SENSE_NULL,
)

Reaction = ReactionRecord
CausalGraph = SemanticGraph
ElementState = RuntimeStatus


class ReactionStatus(str, Enum):
    SUCCESS = "success"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass(slots=True)
class ImpactScope:
    target: str = "actor"
    magnitude: float = 1.0
    element_id: str | None = None

    @classmethod
    def on_actor(cls, m: float = 1.0) -> "ImpactScope":
        return cls("actor", m)

    @classmethod
    def on_element(cls, eid: str, m: float = 1.0) -> "ImpactScope":
        return cls("element", m, eid)

    @classmethod
    def on_env(cls, m: float = 0.5) -> "ImpactScope":
        return cls("environment", m)

    @classmethod
    def broadcast(cls, m: float = 0.3) -> "ImpactScope":
        return cls("broadcast", m)

    @classmethod
    def none(cls) -> "ImpactScope":
        return cls("none", 0.0)


@dataclass(slots=True)
class Temporality:
    mode: str = "immediate"
    delay_ms: int = 0
    interval_ms: int = 0
    duration_ms: int = 0

    @classmethod
    def immediate(cls) -> "Temporality":
        return cls("immediate")

    @classmethod
    def deferred(cls, ms: int) -> "Temporality":
        return cls("deferred", delay_ms=ms)

    @classmethod
    def recurring(cls, ms: int) -> "Temporality":
        return cls("recurring", interval_ms=ms)

    @classmethod
    def temporary(cls, ms: int) -> "Temporality":
        return cls("temporary", duration_ms=ms)


@dataclass(slots=True)
class RawData:
    tag: str
    value: Any
    source: str = ""


@dataclass(slots=True)
class ContextualizedData:
    tag: str
    value: Any
    sense: SenseVector
    frame: str
    relevance: float
    is_actionable: bool


@dataclass(slots=True)
class PhenomenonPattern:
    name: str
    trigger: str
    threshold: int = 1
    window_s: float = 60.0
    attractor: SenseVector = field(default_factory=lambda: SENSE_NULL)


__all__ = [
    "Action",
    "ActionCategory",
    "Context",
    "ContextKind",
    "Circumstance",
    "Element",
    "Environment",
    "EnvironmentKind",
    "HarmonyProfile",
    "Reaction",
    "ReactionStatus",
    "ImpactScope",
    "Temporality",
    "PhenomenonPattern",
    "RawData",
    "ContextualizedData",
    "CausalGraph",
    "ElementState",
    "RuleMode",
    "SenseVector",
    "SENSE_NULL",
]
