from __future__ import annotations

import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class JsonRpcTests(unittest.IsolatedAsyncioTestCase):
    async def test_handshake_and_envelope(self) -> None:
        drone = Drone("ALPHA", "drone_0")
        env = DroneSwarmEnvironment([drone])
        swarm = SwarmKnowledge([drone])
        await env.admit(drone)
        drone.sensor_update(0.0, 0.0, 0.0, 100.0, True)
        swarm.sync()
        gateway = MEPGateway(env, swarm.kb)
        server = MEPJsonRpcServer(gateway)

        response = await server.handle(JsonRpcRequest(method="mep.handshake", params={"client_id": "test"}, id=1))
        self.assertIn("result", response.to_dict())
        session_id = response.to_dict()["result"]["body"]["session_id"]

        envelope = await server.handle(
            JsonRpcRequest(method="mep.envelope", params={"session_id": session_id, "knowledge_prefix": "drone_"}, id=2),
            actor=drone,
            context=env.preflight,
        )
        payload = envelope.to_dict()["result"]
        self.assertEqual(payload["protocol"], "MEP")
        self.assertIn("world", payload)


if __name__ == "__main__":
    unittest.main()
