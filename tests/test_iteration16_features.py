from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class Iteration16FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        self.env = DroneSwarmEnvironment(self.drones)
        self.swarm = SwarmKnowledge(self.drones)

        async def boot() -> None:
            for drone in self.drones:
                await self.env.admit(drone)
        asyncio.run(boot())

        for idx, drone in enumerate(self.drones):
            drone.sensor_update(float(idx * 3), 0.0, 2.0, 97.0 - idx, True, wind_speed=2.0)
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

    def test_named_mission_policy_changes_bid_scores(self) -> None:
        async def scenario() -> None:
            bindings = [binding.to_dict() for binding in self.env.mixed_bindings()]
            base_task = self.swarm.formation_tasks()[0].to_dict()
            balanced = dict(base_task)
            balanced["mission_policy"] = {"preset": "balanced"}
            certainty_first = dict(base_task)
            certainty_first["mission_policy"] = {"preset": "certainty_first"}

            result_balanced = await self.server.handle(JsonRpcRequest(method="mep.multi.negotiate", params={"bindings": bindings, "task": balanced}, id=1), actor=self.drones[0], context=self.env.flight)
            result_certainty = await self.server.handle(JsonRpcRequest(method="mep.multi.negotiate", params={"bindings": bindings, "task": certainty_first}, id=2), actor=self.drones[0], context=self.env.flight)
            payload_balanced = result_balanced.to_dict()["result"]
            payload_certainty = result_certainty.to_dict()["result"]
            self.assertEqual(payload_balanced["arbitration"]["mission_policy"], "balanced")
            self.assertEqual(payload_certainty["arbitration"]["mission_policy"], "certainty_first")
            self.assertNotEqual(payload_balanced["bids"][0]["bid_score"], payload_certainty["bids"][0]["bid_score"])
        asyncio.run(scenario())

    def test_provenance_chain_and_federated_verification(self) -> None:
        async def scenario() -> None:
            bindings = [binding.to_dict() for binding in self.env.mixed_bindings()]
            tasks = [task.to_dict() for task in self.swarm.formation_tasks()]
            await self.server.handle(JsonRpcRequest(method="mep.multi.execute", params={"bindings": bindings, "tasks": tasks}, id=3), actor=self.drones[0], context=self.env.flight)

            verify = await self.server.handle(JsonRpcRequest(method="mep.provenance.verify", params={}, id=4), actor=self.drones[0], context=self.env.flight)
            verify_payload = verify.to_dict()["result"]
            self.assertTrue(verify_payload["ok"])
            self.assertGreaterEqual(verify_payload["count"], 1)

            fed_verify = await self.server.handle(JsonRpcRequest(method="mep.federation.provenance.verify", params={}, id=5), actor=self.drones[0], context=self.env.flight)
            fed_payload = fed_verify.to_dict()["result"]
            self.assertTrue(fed_payload["ok"])
            self.assertEqual(len(fed_payload["reports"]), 2)

            # tamper with the local chain and verify detection
            self.gateway._provenance[0]["metadata"]["tampered"] = True
            self.assertFalse(self.gateway.verify_provenance()["ok"])
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
