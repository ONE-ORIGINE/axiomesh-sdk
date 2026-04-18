from __future__ import annotations

import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import JsonRpcRequest, MEPGateway, MEPJsonRpcServer, DEPRECATED_ALIASES


class Iteration19FeatureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.drone = Drone("ALPHA", "drone_0")
        self.env = DroneSwarmEnvironment([self.drone])
        self.swarm = SwarmKnowledge([self.drone])
        await self.env.admit(self.drone)
        self.drone.sensor_update(0.0, 0.0, 0.0, 100.0, True)
        self.swarm.sync()
        self.gateway = MEPGateway(self.env, self.swarm.kb, mesh=self.swarm.mesh, coordinator=self.env.coordinator)
        self.server = MEPJsonRpcServer(self.gateway)

    async def test_spec_schema_and_markdown_exports(self) -> None:
        schema = await self.server.handle(JsonRpcRequest(method="mep.spec.schema", params={}, id=1))
        payload = schema.to_dict()["result"]
        self.assertEqual(payload["protocol"], "MEP")
        self.assertIn("methods", payload)
        self.assertIn("mep.envelope", payload["methods"])
        self.assertIn("request_schema", payload["methods"]["mep.envelope"])
        self.assertIn("deprecated_aliases", payload)

        markdown = await self.server.handle(JsonRpcRequest(method="mep.spec.markdown", params={}, id=2))
        md = markdown.to_dict()["result"]["markdown"]
        self.assertIn("# MEP Method Catalog", md)
        self.assertIn("mep.spec.schema", md)

    async def test_method_describe_and_alias_resolution(self) -> None:
        alias = next(iter(DEPRECATED_ALIASES.keys()))
        desc = await self.server.handle(JsonRpcRequest(method="mep.method.describe", params={"method": alias}, id=3))
        payload = desc.to_dict()["result"]
        self.assertTrue(payload["known"])
        self.assertIsNotNone(payload["deprecated_alias"])
        self.assertEqual(payload["canonical_method"], DEPRECATED_ALIASES[alias])

        response = await self.server.handle(JsonRpcRequest(method="mep.capabilities", params={}, id=4))
        result = response.to_dict()["result"]
        self.assertEqual(result["protocol"], "MEP")
        self.assertTrue(result["method_aliases"])


if __name__ == "__main__":
    unittest.main()
