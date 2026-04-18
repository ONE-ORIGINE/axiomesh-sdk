from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class Iteration12FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        self.env = DroneSwarmEnvironment(self.drones)
        self.swarm = SwarmKnowledge(self.drones)

        async def boot():
            for drone in self.drones:
                await self.env.admit(drone)
        asyncio.run(boot())
        for i, drone in enumerate(self.drones):
            drone.sensor_update(float(i * 2), 0.0, 3.0, 95.0 - i * 5, True, wind_speed=2.0)
            drone.physical.airborne = True
            drone.set_dynamic("airborne", True)
            drone.sync_physical_state()
        self.swarm.sync()
        self.gateway = MEPGateway(self.env, self.swarm.kb, mesh=self.swarm.mesh, coordinator=self.env.coordinator)
        self.hub = FederatedMEPHub()
        self.env_a = self.hub.register("a", self.gateway, tags=["a"])
        reserve = [Drone("GAMMA", "drone_2")]
        self.env2 = DroneSwarmEnvironment(reserve)
        self.swarm2 = SwarmKnowledge(reserve)
        async def boot2():
            for drone in reserve:
                await self.env2.admit(drone)
        asyncio.run(boot2())
        reserve[0].sensor_update(8.0, 0.0, 3.0, 90.0, True, wind_speed=1.0)
        reserve[0].physical.airborne = True
        reserve[0].set_dynamic("airborne", True)
        reserve[0].sync_physical_state()
        self.swarm2.sync()
        self.gateway2 = MEPGateway(self.env2, self.swarm2.kb, mesh=self.swarm2.mesh, coordinator=self.env2.coordinator)
        self.env_b = self.hub.register("b", self.gateway2, tags=["b"])
        self.server = MEPJsonRpcServer(self.gateway, hub=self.hub)

    def test_multicriteria_negotiation_exposes_scoring(self) -> None:
        async def scenario():
            self.drones[0].set_dynamic('task_load', 2.0)
            self.drones[1].set_dynamic('task_load', 0.0)
            bindings = [self.env.coordinator.binding_for(drone, 'Flight', channel='swarm') for drone in self.drones]
            task = {
                'task_id': 't1', 'description': 'move', 'goal_dimension': 'spatial', 'goal_meaning': 'move', 'goal_magnitude': 0.9,
                'required_roles': ['pilot'], 'preferred_contexts': ['Flight'], 'channel': 'swarm',
                'payload': {'dx': 1.0, 'action_type_hint': 'drone.move', 'target_position': [2.0, 0.0, 3.0]},
            }
            resp = await self.server.handle(JsonRpcRequest(method='mep.multi.negotiate', params={'bindings': [b.to_dict() for b in bindings], 'task': task}, id=1), actor=self.drones[0], context=self.env.flight)
            result = resp.to_dict()['result']
            self.assertEqual(result['scoring']['mode'], 'multi_criteria')
            self.assertTrue(all('score_components' in bid for bid in result['bids']))
        asyncio.run(scenario())

    def test_layer_rollback_policy(self) -> None:
        async def scenario():
            bindings = [self.env.coordinator.binding_for(d, 'Flight', channel='swarm') for d in self.drones]
            tasks = [
                {'task_id': 'a', 'description': 'ok', 'goal_dimension': 'spatial', 'goal_meaning': 'move', 'goal_magnitude': 0.95, 'required_roles': ['pilot'], 'preferred_contexts': ['Flight'], 'target_agent_ids': [self.drones[0].element_id], 'channel': 'swarm', 'payload': {'dx': 1.0, 'action_type_hint': 'drone.move'}},
                {'task_id': 'b', 'description': 'ok2', 'goal_dimension': 'spatial', 'goal_meaning': 'move', 'goal_magnitude': 0.95, 'required_roles': ['pilot'], 'preferred_contexts': ['Flight'], 'target_agent_ids': [self.drones[1].element_id], 'channel': 'swarm', 'payload': {'dx': 1.0, 'action_type_hint': 'drone.move'}},
                {'task_id': 'c', 'description': 'fail', 'goal_dimension': 'spatial', 'goal_meaning': 'move', 'goal_magnitude': 0.95, 'required_roles': ['pilot'], 'preferred_contexts': ['Flight'], 'depends_on': ['a','b'], 'target_agent_ids': [self.drones[1].element_id], 'channel': 'swarm', 'payload': {'dx': 1.0, 'force_fail': True, 'action_type_hint': 'drone.move'}},
            ]
            resp = await self.server.handle(JsonRpcRequest(method='mep.multi.execute', params={'bindings': [b.to_dict() for b in bindings], 'tasks': tasks, 'rollback_policy': 'layer'}, id=2), actor=self.drones[0], context=self.env.flight)
            result = resp.to_dict()['result']
            self.assertEqual(result['rollback_policy'], 'layer')
            self.assertTrue(isinstance(result['compensations'], list))
        asyncio.run(scenario())

    def test_federation_route(self) -> None:
        async def scenario():
            resp = await self.server.handle(JsonRpcRequest(method='mep.federation.route', params={'environment_id': self.env_b, 'forward_method': 'mep.environment.card', 'forward_params': {}}, id=3), actor=self.drones[0], context=self.env.flight)
            result = resp.to_dict()['result']
            self.assertEqual(result['environment_id'], self.env_b)
            self.assertEqual(result['response']['result']['environment_kind'], 'living')
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
