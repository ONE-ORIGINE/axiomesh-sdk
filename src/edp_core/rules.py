from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Callable

from .contracts import RuleMode, RuleTrace


class SafeExpression:
    allowed_nodes = {
        ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
        ast.Compare, ast.Name, ast.Load, ast.Constant, ast.Gt, ast.GtE,
        ast.Lt, ast.LtE, ast.Eq, ast.NotEq, ast.In, ast.NotIn,
        ast.BinOp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod,
        ast.USub, ast.UAdd,
    }

    def __init__(self, expression: str):
        self.expression = expression
        self._tree = ast.parse(expression, mode="eval")
        for node in ast.walk(self._tree):
            if type(node) not in self.allowed_nodes:
                raise ValueError(f"Unsupported syntax in rule expression: {type(node).__name__}")

    def eval(self, scope: dict[str, Any]) -> bool:
        return bool(self._eval(self._tree.body, scope))

    def _eval(self, node: ast.AST, scope: dict[str, Any]) -> Any:
        if isinstance(node, ast.BoolOp):
            values = [self._eval(v, scope) for v in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not self._eval(node.operand, scope)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -self._eval(node.operand, scope)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
            return +self._eval(node.operand, scope)
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left, scope)
            right = self._eval(node.right, scope)
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            if isinstance(node.op, ast.Mod):
                return left % right
        if isinstance(node, ast.Compare):
            left = self._eval(node.left, scope)
            result = True
            for op, comp in zip(node.ops, node.comparators):
                right = self._eval(comp, scope)
                if isinstance(op, ast.Gt):
                    result = result and (left > right)
                elif isinstance(op, ast.GtE):
                    result = result and (left >= right)
                elif isinstance(op, ast.Lt):
                    result = result and (left < right)
                elif isinstance(op, ast.LtE):
                    result = result and (left <= right)
                elif isinstance(op, ast.Eq):
                    result = result and (left == right)
                elif isinstance(op, ast.NotEq):
                    result = result and (left != right)
                elif isinstance(op, ast.In):
                    result = result and (left in right)
                elif isinstance(op, ast.NotIn):
                    result = result and (left not in right)
                left = right
            return result
        if isinstance(node, ast.Name):
            return scope.get(node.id, False)
        if isinstance(node, ast.Constant):
            return node.value
        raise ValueError(f"Unsupported node: {type(node).__name__}")


class Circumstance:
    def __init__(
        self,
        cid: str,
        description: str,
        fn: Callable[[Any, dict], bool],
        role: str = "enabler",
        weight: float = 1.0,
        expression: str = "",
        mode: RuleMode = RuleMode.HARD,
        priority: int = 100,
        penalty: float | None = None,
    ):
        self.id = cid
        self.description = description
        self._fn = fn
        self.role = role
        self.weight = weight
        self.expression = expression
        self.mode = mode
        self.priority = priority
        self.penalty = float(weight if penalty is None else penalty)

    def evaluate(self, ctx: Any, frame: dict) -> bool:
        try:
            return bool(self._fn(ctx, frame))
        except Exception:
            return False

    def trace(self, ctx: Any, frame: dict) -> RuleTrace:
        holds = self.evaluate(ctx, frame)
        prefix = "✓" if holds else "✗"
        detail = f" [{self.mode.value}/p{self.priority}]"
        reason = f"{prefix} {self.description}{detail}"
        if self.expression:
            reason += f" | expr={self.expression}"
        if not holds and self.mode == RuleMode.SOFT:
            reason += f" | penalty={self.penalty:.3f}"
        return RuleTrace(
            rule_id=self.id,
            description=self.description,
            holds=holds,
            role=self.role,
            reason=reason,
            expression=self.expression,
            weight=self.weight,
            mode=self.mode,
            priority=self.priority,
            penalty=self.penalty,
        )

    def __and__(self, other: "Circumstance") -> "Circumstance":
        return Circumstance(
            f"({self.id}&{other.id})",
            f"({self.description}) AND ({other.description})",
            lambda c, f: self.evaluate(c, f) and other.evaluate(c, f),
            role="enabler",
            weight=min(self.weight, other.weight),
            expression=f"({self.expression or self.id}) and ({other.expression or other.id})",
            mode=RuleMode.HARD if RuleMode.HARD in (self.mode, other.mode) else RuleMode.SOFT,
            priority=min(self.priority, other.priority),
            penalty=self.penalty + other.penalty,
        )

    def __or__(self, other: "Circumstance") -> "Circumstance":
        return Circumstance(
            f"({self.id}|{other.id})",
            f"({self.description}) OR ({other.description})",
            lambda c, f: self.evaluate(c, f) or other.evaluate(c, f),
            role="enabler",
            weight=max(self.weight, other.weight),
            expression=f"({self.expression or self.id}) or ({other.expression or other.id})",
            mode=RuleMode.SOFT if RuleMode.SOFT in (self.mode, other.mode) else RuleMode.HARD,
            priority=min(self.priority, other.priority),
            penalty=max(self.penalty, other.penalty),
        )

    def __invert__(self) -> "Circumstance":
        return Circumstance(
            f"~{self.id}",
            f"NOT ({self.description})",
            lambda c, f: not self.evaluate(c, f),
            role="blocker",
            weight=-self.weight,
            expression=f"not ({self.expression or self.id})",
            mode=self.mode,
            priority=self.priority,
            penalty=self.penalty,
        )

    @classmethod
    def when(
        cls,
        cid: str,
        description: str,
        fn: Callable[[Any, dict], bool],
        role: str = "enabler",
        weight: float = 1.0,
        mode: RuleMode = RuleMode.HARD,
        priority: int = 100,
        penalty: float | None = None,
    ) -> "Circumstance":
        return cls(cid, description, fn, role=role, weight=weight, mode=mode, priority=priority, penalty=penalty)

    @classmethod
    def expr(
        cls,
        cid: str,
        description: str,
        expression: str,
        resolver: Callable[[Any, dict], dict[str, Any]],
        role: str = "enabler",
        weight: float = 1.0,
        mode: RuleMode = RuleMode.HARD,
        priority: int = 100,
        penalty: float | None = None,
    ) -> "Circumstance":
        compiled = SafeExpression(expression)
        return cls(
            cid,
            description,
            lambda ctx, frame: compiled.eval(resolver(ctx, frame)),
            role=role,
            weight=weight,
            expression=expression,
            mode=mode,
            priority=priority,
            penalty=penalty,
        )

    @classmethod
    def always(cls, cid: str = "always") -> "Circumstance":
        return cls(cid, f"Always ({cid})", lambda *_: True)

    @classmethod
    def never(cls, cid: str = "never") -> "Circumstance":
        return cls(cid, f"Never ({cid})", lambda *_: False, role="blocker")


@dataclass(slots=True)
class RuleBook:
    rules: list[Circumstance]

    def evaluate(self, ctx: Any, frame: dict) -> list[RuleTrace]:
        return sorted((rule.trace(ctx, frame) for rule in self.rules), key=lambda t: (t.priority, t.rule_id))

    def blockers(self, ctx: Any, frame: dict) -> list[RuleTrace]:
        traces = self.evaluate(ctx, frame)
        return [trace for trace in traces if not trace.holds and trace.mode == RuleMode.HARD and trace.role == "enabler"]

    def warnings(self, ctx: Any, frame: dict) -> list[RuleTrace]:
        traces = self.evaluate(ctx, frame)
        return [trace for trace in traces if not trace.holds and trace.mode == RuleMode.SOFT and trace.role == "enabler"]

    def soft_penalty(self, ctx: Any, frame: dict) -> float:
        return sum(trace.penalty for trace in self.warnings(ctx, frame))
