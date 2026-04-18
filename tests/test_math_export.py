from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment


class MathExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_factor_graph_export(self) -> None:
        drone = Drone("ALPHA", "drone_0")
        env = DroneSwarmEnvironment([drone])
        await env.admit(drone)
        export = env.export_math().to_dict()
        self.assertIn("factor_graph", export)
        self.assertGreaterEqual(export["factor_graph"]["total_energy"], 0.0)
        self.assertTrue(export["factor_graph"]["variables"])


if __name__ == "__main__":
    unittest.main()
