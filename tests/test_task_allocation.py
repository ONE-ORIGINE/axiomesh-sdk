from __future__ import annotations

import unittest

from drone_sdk import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class TaskAllocationTests(unittest.IsolatedAsyncioTestCase):
    async def test_multi_agent_task_assignment_and_neighborhood(self) -> None:
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
        drones[1].sensor_update(5.0, 0.0, 0.0, 97.0, True)
        swarm.sync()
        swarm.connect_neighbors_by_distance(radius=10.0)
        swarm.publish_neighbors()

        gateway = MEPGateway(env, swarm.kb, mesh=swarm.mesh, coordinator=env.coordinator)
        server = MEPJsonRpcServer(gateway)

        bindings = env.mixed_bindings()
        tasks = [task.to_dict() for task in swarm.formation_tasks()]
        rpc = await server.handle(JsonRpcRequest(method="mep.multi.assign", params={
            "bindings": [binding.to_dict() for binding in bindings],
            "tasks": tasks,
            "neighborhood_radius": 10.0,
        }, id=1), actor=drones[0], context=env.flight)
        result = rpc.to_dict()["result"]
        self.assertGreaterEqual(len(result["assignments"]), 2)
        self.assertTrue(result["dependency_layers"])
        self.assertIn(drones[0].element_id, result["neighborhood_map"])

        hood = await server.handle(JsonRpcRequest(method="mep.neighborhood", params={"knowledge_prefix": "drone_"}, id=2), actor=drones[0], context=env.flight)
        hood_result = hood.to_dict()["result"]
        self.assertTrue(hood_result["neighbors"])
        self.assertTrue(any(item["neighbor_id"] == "drone_1" for item in hood_result["visible_facts"]))


if __name__ == "__main__":
    unittest.main()
