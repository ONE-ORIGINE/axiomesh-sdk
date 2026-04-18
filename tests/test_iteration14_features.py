from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class Iteration14FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        self.env = DroneSwarmEnvironment(self.drones)
        self.swarm = SwarmKnowledge(self.drones)

        async def boot():
            for drone in self.drones:
                await self.env.admit(drone)
        asyncio.run(boot())
        for i, drone in enumerate(self.drones):
            drone.sensor_update(float(i * 2), 0.0, 3.0, 96.0 - i, True, wind_speed=2.0)
            drone.physical.airborne = True
            drone.set_dynamic("airborne", True)
            drone.sync_physical_state()
        self.swarm.sync()
        self.gateway = MEPGateway(self.env, self.swarm.kb, mesh=self.swarm.mesh, coordinator=self.env.coordinator)

        reserve = [Drone("GAMMA", "drone_2")]
        self.env2 = DroneSwarmEnvironment(reserve)
        self.swarm2 = SwarmKnowledge(reserve)
        async def boot2():
            for drone in reserve:
                await self.env2.admit(drone)
        asyncio.run(boot2())
        reserve[0].sensor_update(8.0, 0.0, 3.0, 94.0, True, wind_speed=1.0)
        reserve[0].physical.airborne = True
        reserve[0].set_dynamic("airborne", True)
        reserve[0].sync_physical_state()
        self.swarm2.sync()
        self.gateway2 = MEPGateway(self.env2, self.swarm2.kb, mesh=self.swarm2.mesh, coordinator=self.env2.coordinator)

        self.hub = FederatedMEPHub()
        self.env_a = self.hub.register("primary", self.gateway, tags=["drone", "swarm"])
        self.env_b = self.hub.register("reserve", self.gateway2, tags=["reserve", "drone"])
        self.server = MEPJsonRpcServer(self.gateway, hub=self.hub)

    def test_resolve_plan_groups_tasks_by_environment(self) -> None:
        async def scenario():
            tasks = [
                {
                    "task_id": "primary-task",
                    "description": "primary move",
                    "goal_dimension": "spatial",
                    "goal_meaning": "move",
                    "goal_magnitude": 0.9,
                    "required_roles": ["pilot"],
                    "preferred_contexts": ["Flight"],
                    "channel": "swarm",
                    "payload": {"dx": 1.0, "action_type_hint": "drone.move"},
                    "preferred_environment_tags": ["drone"],
                },
                {
                    "task_id": "reserve-task",
                    "description": "reserve move",
                    "goal_dimension": "spatial",
                    "goal_meaning": "move",
                    "goal_magnitude": 0.9,
                    "required_roles": ["pilot"],
                    "preferred_contexts": ["Flight"],
                    "channel": "swarm",
                    "payload": {"dx": 1.0, "action_type_hint": "drone.move"},
                    "preferred_environment_tags": ["reserve"],
                },
            ]
            resp = await self.server.handle(JsonRpcRequest(method="mep.federation.resolve_plan", params={"tasks": tasks}, id=1), actor=self.drones[0], context=self.env.flight)
            payload = resp.to_dict()["result"]
            self.assertGreaterEqual(len(payload["groups"]), 1)
            self.assertEqual(payload["candidate_count"], 2)
        asyncio.run(scenario())

    def test_federated_execute_task_and_plan(self) -> None:
        async def scenario():
            task = {
                "task_id": "reserve-task",
                "description": "reserve move",
                "goal_dimension": "spatial",
                "goal_meaning": "move",
                "goal_magnitude": 0.9,
                "required_roles": ["pilot"],
                "preferred_contexts": ["Flight"],
                "channel": "swarm",
                "payload": {"dx": 1.0, "action_type_hint": "drone.move"},
                "preferred_environment_tags": ["reserve"],
            }
            single = await self.server.handle(JsonRpcRequest(method="mep.federation.execute_task", params={"task": task, "rollback_policy": "layer"}, id=2), actor=self.drones[0], context=self.env.flight)
            single_payload = single.to_dict()["result"]
            self.assertEqual(single_payload["environment_id"], self.env_b)
            self.assertEqual(single_payload["response"]["result"]["rollback_policy"], "layer")

            tasks = [task, {**task, "task_id": "reserve-task-2"}]
            plan = await self.server.handle(JsonRpcRequest(method="mep.federation.execute_plan", params={"tasks": tasks, "rollback_policy": "layer"}, id=3), actor=self.drones[0], context=self.env.flight)
            plan_payload = plan.to_dict()["result"]
            self.assertGreaterEqual(len(plan_payload["executions"]), 1)
            self.assertEqual(plan_payload["rollback_policy"], "layer")
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
