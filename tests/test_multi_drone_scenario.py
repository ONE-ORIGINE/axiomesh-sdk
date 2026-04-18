from __future__ import annotations

import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import MEPGateway
from edp_core import SenseVector


class MultiDroneScenarioTests(unittest.IsolatedAsyncioTestCase):
    async def test_multi_drone_revalidation_and_planning(self) -> None:
        drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        env = DroneSwarmEnvironment(drones)
        swarm = SwarmKnowledge(drones)
        for drone in drones:
            await env.admit(drone)
        drones[0].sensor_update(0.0, 0.0, 0.0, 100.0, True)
        drones[1].sensor_update(5.0, 0.0, 0.0, 80.0, True)
        swarm.sync()

        await env.dispatch(drones[0], "drone.takeoff", {"altitude": 6.0}, env.preflight)
        await env.dispatch(drones[1], "drone.takeoff", {"altitude": 6.0}, env.preflight)
        swarm.revise_position("drone_0", gps_xyz=(0.0, 0.0, 6.0), lidar_xyz=(1.0, 0.8, 6.0))

        self.assertTrue(swarm.kb.revalidation_queue("drone_"))
        gateway = MEPGateway(env, swarm.kb)
        preview = gateway.preview_plan(drones[1], SenseVector.spatial("move safely", 0.8), max_steps=2)
        self.assertIn("steps", preview)

        export = env.export_math().to_dict()
        self.assertEqual(len(export["graph"]["nodes"]), 2)
        self.assertGreaterEqual(export["factor_energy"], 0.0)


if __name__ == "__main__":
    unittest.main()
