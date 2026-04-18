from __future__ import annotations

import unittest

from edp_core import ContextBinding
from drone_sdk import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class MultiContextProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_multi_context_envelope_supports_mixed_agents(self) -> None:
        drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        env = DroneSwarmEnvironment(drones)
        swarm = SwarmKnowledge(drones)
        internal = []
        for drone in drones:
            await env.admit(drone)
            internal.extend(env.build_internal_agents(drone))
        for agent in internal:
            await env.admit(agent)
        drones[0].sensor_update(0.0, 0.0, 0.0, 100.0, True)
        drones[1].sensor_update(5.0, 0.0, 0.0, 90.0, True)
        swarm.sync()

        gateway = MEPGateway(env, swarm.kb, mesh=swarm.mesh, coordinator=env.coordinator)
        server = MEPJsonRpcServer(gateway)

        navigator = next(a for a in internal if a.static_properties.get("role") == "navigator" and a.static_properties.get("drone_id") == "drone_0")
        safety = next(a for a in internal if a.static_properties.get("role") == "safety" and a.static_properties.get("drone_id") == "drone_1")
        bindings = [
            ContextBinding(agent_id=drones[0].element_id, context_name="Flight", role="pilot", channel="swarm"),
            ContextBinding(agent_id=drones[1].element_id, context_name="Navigation", role="pilot", channel="swarm"),
            ContextBinding(agent_id=navigator.element_id, context_name="InnerNavigation", role="navigator", parent_agent_id=drones[0].element_id, channel="internal"),
            ContextBinding(agent_id=safety.element_id, context_name="InnerSafety", role="safety", parent_agent_id=drones[1].element_id, channel="internal"),
        ]

        envelope = gateway.build_multi_context_envelope(bindings, knowledge_prefix="drone_")
        payload = envelope.to_dict()
        self.assertEqual(len(payload["bindings"]), 4)
        self.assertEqual(len(payload["agent_views"]), 4)
        self.assertEqual(len(payload["worlds"]), 4)
        self.assertIn("shared_knowledge", payload)
        self.assertEqual(payload["agent_views"][2]["role"], "navigator")

        rpc = await server.handle(JsonRpcRequest(method="mep.multi.context.plan", params={
            "goal": {"dimension": "technical", "meaning": "coordinated mission", "magnitude": 0.82},
            "bindings": [binding.to_dict() for binding in bindings],
        }, id=1))
        result = rpc.to_dict()["result"]
        self.assertIn("items", result)
        self.assertEqual(len(result["items"]), 4)
        self.assertTrue(any(item["context_name"] == "InnerNavigation" for item in result["items"]))


if __name__ == "__main__":
    unittest.main()
