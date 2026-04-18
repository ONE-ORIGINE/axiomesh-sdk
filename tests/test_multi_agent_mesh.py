from __future__ import annotations

import unittest

from drone_sdk.model import Drone, SwarmKnowledge


class MultiAgentMeshTests(unittest.TestCase):
    def test_local_and_shared_knowledge_are_both_available(self) -> None:
        drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        swarm = SwarmKnowledge(drones)
        drones[0].sensor_update(0.0, 0.0, 0.0, 100.0, True)
        drones[1].sensor_update(2.0, 0.0, 0.0, 90.0, True)
        swarm.sync()

        view = swarm.mesh.agent_view("drone_0", prefix="drone_")
        self.assertTrue(view.local_facts)
        self.assertTrue(view.shared_facts)
        snapshot = swarm.mesh.shared_snapshot("drone_")
        self.assertGreaterEqual(len(snapshot["facts"]), 4)


if __name__ == "__main__":
    unittest.main()
