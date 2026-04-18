from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class Iteration18FeatureTests(unittest.TestCase):
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
        self.primary_id = self.hub.register("primary", self.gateway, tags=["drone", "swarm"])
        self.reserve_id = self.hub.register("reserve", self.gateway2, tags=["reserve", "drone"])
        self.server = MEPJsonRpcServer(self.gateway, hub=self.hub)

    def test_fault_injection_and_retry_recovery(self) -> None:
        async def scenario() -> None:
            tasks = self.swarm.formation_tasks()
            await self.server.handle(JsonRpcRequest(method="mep.fault.inject", params={"scope": "task", "target": tasks[0].task_id, "count": 1, "message": "temporary thruster glitch"}, id=1))
            result = await self.server.handle(JsonRpcRequest(method="mep.multi.execute", params={
                "bindings": [binding.to_dict() for binding in self.env.mixed_bindings()],
                "tasks": [task.to_dict() for task in tasks],
                "recovery_policy": "retry_once",
            }, id=2), actor=self.drones[0], context=self.env.flight)
            payload = result.to_dict()["result"]
            self.assertEqual(payload["recovery_policy"], "retry_once")
            self.assertGreaterEqual(len(payload["retried_task_ids"]), 1)
            self.assertGreaterEqual(len(payload["recovered_task_ids"]), 1)
            status = await self.server.handle(JsonRpcRequest(method="mep.fault.status", params={}, id=3))
            stats = status.to_dict()["result"]["recovery_stats"]
            self.assertGreaterEqual(stats["triggered"], 1)
            self.assertGreaterEqual(stats["retried"], 1)
            self.assertGreaterEqual(stats["recovered"], 1)
        asyncio.run(scenario())

    def test_federated_reroute_after_route_fault(self) -> None:
        async def scenario() -> None:
            task = self.swarm.formation_tasks()[0]
            task.preferred_environment_tags = ["reserve"]
            self.gateway2.inject_fault("route", "mep.multi.execute", count=1, message="reserve route offline")
            result = await self.server.handle(JsonRpcRequest(method="mep.federation.execute_task", params={
                "task": task.to_dict(),
                "recovery_policy": "reroute",
                "rollback_policy": "layer",
            }, id=11), actor=self.drones[0], context=self.env.flight)
            payload = result.to_dict()["result"]
            self.assertGreaterEqual(len(payload["attempts"]), 2)
            self.assertEqual(payload["recovery_policy"], "reroute")
            status = await self.server.handle(JsonRpcRequest(method="mep.fault.status", params={}, id=12))
            self.assertGreaterEqual(status.to_dict()["result"]["recovery_stats"]["rerouted"], 1)
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
