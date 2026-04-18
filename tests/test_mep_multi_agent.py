from __future__ import annotations

import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class MultiAgentProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_agents_and_shared_envelope(self) -> None:
        drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        env = DroneSwarmEnvironment(drones)
        swarm = SwarmKnowledge(drones)
        for drone in drones:
            await env.admit(drone)
            drone.sensor_update(0.0 if drone.drone_id == "drone_0" else 1.0, 0.0, 0.0, 100.0, True)
        swarm.sync()

        gateway = MEPGateway(env, swarm.kb, mesh=swarm.mesh, coordinator=env.coordinator)
        server = MEPJsonRpcServer(gateway)

        agents = await server.handle(JsonRpcRequest(method="mep.agents", id=1))
        payload = agents.to_dict()["result"]
        self.assertIn("agents", payload)
        self.assertEqual(len(payload["agents"]), 2)

        shared = await server.handle(
            JsonRpcRequest(method="mep.shared.envelope", params={"actor_ids": [d.element_id for d in drones], "knowledge_prefix": "drone_"}, id=2),
            context=env.navigation,
        )
        shared_payload = shared.to_dict()["result"]
        self.assertEqual(len(shared_payload["agent_ids"]), 2)
        self.assertIn("shared_knowledge", shared_payload)

        multi = await server.handle(
            JsonRpcRequest(method="mep.multi.plan", params={"actor_ids": [d.element_id for d in drones], "goal": {"dimension": "spatial", "meaning": "maintain formation", "magnitude": 0.8}}, id=3)
        )
        multi_payload = multi.to_dict()["result"]
        self.assertIn("items", multi_payload)
        self.assertEqual(len(multi_payload["items"]), 2)


if __name__ == "__main__":
    unittest.main()
