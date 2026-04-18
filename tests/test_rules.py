from __future__ import annotations

import asyncio
import unittest

from edp_core import Action, ActionCategory, ContextKind, Element, Environment, SenseVector, EnvironmentKind, RuleMode, ReactionRecord


class RuleRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_soft_rule_penalizes_but_does_not_block(self) -> None:
        env = Environment("test", EnvironmentKind.REACTIVE)
        ctx = env.create_context("Flight", ContextKind.SPATIAL, SenseVector.spatial("flight", 1.0))
        actor = Element("alpha", "drone", SenseVector.spatial("alpha", 0.8))
        actor.set_dynamic("airborne", True)
        actor.set_dynamic("wind_speed", 20)
        await env.admit(actor)
        ctx.when_expr("airborne", "airborne", "airborne == True", priority=1)
        ctx.when_expr("wind", "wind low", "wind_speed < 12", mode=RuleMode.SOFT, priority=2, penalty=0.2)

        async def hover(actor, request, ctx):
            return ReactionRecord("hover", ok=True, message="ok")

        ctx.add_action(Action("hover", ActionCategory.COMMAND, "Hold", SenseVector.spatial("hover", 0.8), handler=hover))
        assessment = ctx.assess_action(actor, ctx.actions[0])
        self.assertTrue(assessment.executable)
        self.assertGreater(assessment.soft_penalty, 0.0)
        reaction = await env.dispatch(actor, "hover", {}, ctx)
        self.assertTrue(reaction.ok)

    async def test_hard_rule_blocks(self) -> None:
        env = Environment("test", EnvironmentKind.REACTIVE)
        ctx = env.create_context("Flight", ContextKind.SPATIAL, SenseVector.spatial("flight", 1.0))
        actor = Element("alpha", "drone")
        actor.set_dynamic("battery", 10)
        await env.admit(actor)
        ctx.when_expr("battery", "battery safe", "battery > 15", priority=1)
        ctx.add_action(Action("move", ActionCategory.COMMAND, "Move", SenseVector.spatial("move", 0.9)))
        assessment = ctx.assess_action(actor, ctx.actions[0])
        self.assertFalse(assessment.executable)
        self.assertTrue(assessment.blocked_by)


if __name__ == "__main__":
    unittest.main()
