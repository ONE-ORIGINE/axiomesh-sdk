from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class Iteration15FeatureTests(unittest.TestCase):
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

    def test_mission_graph_and_execute(self) -> None:
        async def scenario():
            tasks = [
                {
                    "task_id": "mission-1",
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
                    "task_id": "mission-2",
                    "description": "reserve move",
                    "goal_dimension": "spatial",
                    "goal_meaning": "move",
                    "goal_magnitude": 0.9,
                    "required_roles": ["pilot"],
                    "preferred_contexts": ["Flight"],
                    "channel": "swarm",
                    "depends_on": ["mission-1"],
                    "payload": {"dx": 1.0, "action_type_hint": "drone.move"},
                    "preferred_environment_tags": ["reserve"],
                },
            ]
            graph = await self.server.handle(JsonRpcRequest(method="mep.federation.mission_graph", params={"tasks": tasks}, id=1), actor=self.drones[0], context=self.env.flight)
            payload = graph.to_dict()["result"]
            self.assertGreaterEqual(payload["stage_count"], 1)
            self.assertEqual(payload["task_count"], 2)
            self.assertGreaterEqual(len(payload["edges"]), 1)

            execute = await self.server.handle(JsonRpcRequest(method="mep.federation.execute_mission", params={"tasks": tasks, "rollback_policy": "layer"}, id=2), actor=self.drones[0], context=self.env.flight)
            exec_payload = execute.to_dict()["result"]
            self.assertIn("graph", exec_payload)
            self.assertEqual(exec_payload["rollback_policy"], "layer")
            self.assertGreaterEqual(len(exec_payload["stage_results"]), 1)
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
