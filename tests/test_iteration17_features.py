from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer, MEP_VERSION


class Iteration17FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        self.env = DroneSwarmEnvironment(self.drones)
        self.swarm = SwarmKnowledge(self.drones)

        async def boot() -> None:
            for drone in self.drones:
                await self.env.admit(drone)
        asyncio.run(boot())

        for idx, drone in enumerate(self.drones):
            drone.sensor_update(float(idx * 4), 0.0, 2.0, 98.0 - idx, True, wind_speed=2.0)
            drone.physical.airborne = True
            drone.set_dynamic("airborne", True)
            drone.sync_physical_state()
        self.swarm.sync()
        self.gateway = MEPGateway(self.env, self.swarm.kb, mesh=self.swarm.mesh, coordinator=self.env.coordinator)

        reserve = [Drone("GAMMA", "drone_2")]
        self.env2 = DroneSwarmEnvironment(reserve)
        self.swarm2 = SwarmKnowledge(reserve)

        async def boot2() -> None:
            for drone in reserve:
                await self.env2.admit(drone)
        asyncio.run(boot2())
        reserve[0].sensor_update(12.0, 0.0, 2.0, 91.0, True, wind_speed=1.0)
        reserve[0].physical.airborne = True
        reserve[0].set_dynamic("airborne", True)
        reserve[0].sync_physical_state()
        self.swarm2.sync()
        self.gateway2 = MEPGateway(self.env2, self.swarm2.kb, mesh=self.swarm2.mesh, coordinator=self.env2.coordinator)

        self.hub = FederatedMEPHub()
        self.hub.register("primary", self.gateway, tags=["drone", "swarm"])
        self.hub.register("reserve", self.gateway2, tags=["reserve", "drone"])
        self.server = MEPJsonRpcServer(self.gateway, hub=self.hub)

    def test_spec_surface_and_health(self) -> None:
        async def scenario() -> None:
            spec = await self.server.handle(JsonRpcRequest(method="mep.spec", params={}, id=1))
            payload = spec.to_dict()["result"]
            self.assertEqual(payload["version"], MEP_VERSION)
            self.assertGreaterEqual(payload["method_count"], 30)
            self.assertIn("mep.health", {m["method"] for m in payload["methods"]})

            health = await self.server.handle(JsonRpcRequest(method="mep.health", params={}, id=2))
            report = health.to_dict()["result"]
            self.assertEqual(report["version"], MEP_VERSION)
            self.assertTrue(report["provenance"]["ok"])
            self.assertEqual(report["counts"]["elements"], len(self.env.elements))
        asyncio.run(scenario())

    def test_soak_repeated_federated_mission_execution(self) -> None:
        async def scenario() -> None:
            for idx in range(5):
                tasks = [
                    {**self.swarm.formation_tasks()[0].to_dict(), "task_id": f"mission-{idx}-1"},
                    {**self.swarm.formation_tasks()[1].to_dict(), "task_id": f"mission-{idx}-2", "depends_on": [f"mission-{idx}-1"], "preferred_environment_tags": ["reserve"]},
                ]
                result = await self.server.handle(JsonRpcRequest(method="mep.federation.execute_mission", params={"tasks": tasks, "rollback_policy": "layer"}, id=100 + idx), actor=self.drones[0], context=self.env.flight)
                payload = result.to_dict()["result"]
                self.assertGreaterEqual(len(payload["stage_results"]), 1)
            health = await self.server.handle(JsonRpcRequest(method="mep.health", params={}, id=99))
            report = health.to_dict()["result"]
            self.assertGreaterEqual(report["counts"]["provenance_records"], 5)
            self.assertTrue(report["provenance"]["ok"])
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
