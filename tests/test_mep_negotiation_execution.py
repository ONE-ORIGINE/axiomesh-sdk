from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class NegotiationExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        self.env = DroneSwarmEnvironment(self.drones)
        self.swarm = SwarmKnowledge(self.drones)
        async def boot():
            internal = []
            for drone in self.drones:
                await self.env.admit(drone)
                internal.extend(self.env.build_internal_agents(drone))
            for agent in internal:
                await self.env.admit(agent)
        asyncio.run(boot())
        self.drones[0].sensor_update(0.0, 0.0, 0.0, 100.0, True, wind_speed=3.0)
        self.drones[1].sensor_update(4.0, 0.0, 0.0, 97.0, True, wind_speed=4.0)
        for drone in self.drones:
            drone.physical.airborne = True
            drone.set_dynamic("airborne", True)
            drone.sync_physical_state()
        self.swarm.sync()
        self.swarm.connect_neighbors_by_distance(radius=8.0)
        self.gateway = MEPGateway(self.env, self.swarm.kb, mesh=self.swarm.mesh, coordinator=self.env.coordinator)
        self.server = MEPJsonRpcServer(self.gateway)

    def test_negotiate_and_execute_multi_tasks(self) -> None:
        async def scenario():
            bindings = self.env.mixed_bindings()
            task = self.swarm.formation_tasks()[0].to_dict()
            neg = await self.server.handle(JsonRpcRequest(method="mep.multi.negotiate", params={"bindings": [b.to_dict() for b in bindings], "task": task}, id=1), actor=self.drones[0], context=self.env.flight)
            result = neg.to_dict()["result"]
            self.assertGreaterEqual(len(result["bids"]), 1)
            self.assertIsNotNone(result["winner"])

            exe = await self.server.handle(JsonRpcRequest(method="mep.multi.execute", params={"bindings": [b.to_dict() for b in bindings], "tasks": [t.to_dict() for t in self.swarm.formation_tasks()], "initiator": "test-suite"}, id=2), actor=self.drones[0], context=self.env.flight)
            payload = exe.to_dict()["result"]
            self.assertGreaterEqual(len(payload["executed"]), 1)
            self.assertGreaterEqual(len(payload["causal_links"]), 1)

            trace = await self.server.handle(JsonRpcRequest(method="mep.causal.trace", params={"limit": 5}, id=3), actor=self.drones[0], context=self.env.flight)
            trace_payload = trace.to_dict()["result"]
            self.assertGreaterEqual(len(trace_payload["items"]), 1)
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
