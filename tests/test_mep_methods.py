from __future__ import annotations

import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class ProtocolMethodTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.drone = Drone("ALPHA", "drone_0")
        self.env = DroneSwarmEnvironment([self.drone])
        self.swarm = SwarmKnowledge([self.drone])
        await self.env.admit(self.drone)
        self.drone.sensor_update(0.0, 0.0, 0.0, 100.0, True)
        self.swarm.sync()
        self.gateway = MEPGateway(self.env, self.swarm.kb)
        self.server = MEPJsonRpcServer(self.gateway)
        handshake = await self.server.handle(JsonRpcRequest(method="mep.handshake", params={"client_id": "test"}, id=1))
        self.session_id = handshake.to_dict()["result"]["body"]["session_id"]

    async def test_why_and_why_not_methods(self) -> None:
        why = await self.server.handle(
            JsonRpcRequest(method="mep.why", params={"action_type": "drone.takeoff"}, id=2),
            actor=self.drone,
            context=self.env.preflight,
        )
        payload = why.to_dict()["result"]
        self.assertIn("trace", payload)
        self.assertTrue(payload["action"]["available"])

        why_not = await self.server.handle(
            JsonRpcRequest(method="mep.why_not", params={"action_type": "drone.goto"}, id=3),
            actor=self.drone,
            context=self.env.preflight,
        )
        result = why_not.to_dict()["result"]
        self.assertIn("blockers", result)
        self.assertFalse(result["available"])

    async def test_plan_and_mission_preview_methods(self) -> None:
        await self.env.dispatch(self.drone, "drone.takeoff", {"altitude": 8.0}, self.env.preflight)
        plan = await self.server.handle(
            JsonRpcRequest(method="mep.plan", params={"goal": {"dimension": "spatial", "meaning": "reach waypoint", "magnitude": 0.9}, "max_steps": 2}, id=4),
            actor=self.drone,
            context=self.env.navigation,
        )
        plan_payload = plan.to_dict()["result"]
        self.assertIn("steps", plan_payload)
        self.assertTrue(plan_payload["steps"])

        mission = self.swarm.mission_objectives("drone_0")
        mission_request = [
            {
                "objective_id": obj.objective_id,
                "description": obj.description,
                "priority": obj.priority,
                "success_threshold": obj.success_threshold,
                "preferred_contexts": obj.preferred_contexts,
                "target_sense": {
                    "dimension": obj.target_sense.dimension,
                    "meaning": obj.target_sense.meaning,
                    "magnitude": obj.target_sense.magnitude,
                },
            }
            for obj in mission
        ]
        preview = await self.server.handle(
            JsonRpcRequest(method="mep.mission.preview", params={"mission_objectives": mission_request}, id=5),
            actor=self.drone,
            context=self.env.navigation,
        )
        preview_payload = preview.to_dict()["result"]
        self.assertIn("stages", preview_payload)
        self.assertGreaterEqual(len(preview_payload["stages"]), 1)

    async def test_session_unsubscribe(self) -> None:
        sub = await self.server.handle(JsonRpcRequest(method="mep.session.subscribe", params={"session_id": self.session_id, "channel": "events"}, id=6))
        self.assertIn("subscribed", sub.to_dict()["result"])
        unsub = await self.server.handle(JsonRpcRequest(method="mep.session.unsubscribe", params={"session_id": self.session_id, "channel": "events"}, id=7))
        self.assertIn("unsubscribed", unsub.to_dict()["result"])


if __name__ == "__main__":
    unittest.main()
