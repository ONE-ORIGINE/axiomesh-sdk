from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class Iteration13FeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        self.env = DroneSwarmEnvironment(self.drones)
        self.swarm = SwarmKnowledge(self.drones)

        async def boot():
            for drone in self.drones:
                await self.env.admit(drone)
        asyncio.run(boot())
        for i, drone in enumerate(self.drones):
            drone.sensor_update(float(i * 2), 0.0, 3.0, 95.0 - i * 3, True, wind_speed=2.0)
            drone.physical.airborne = True
            drone.set_dynamic("airborne", True)
            drone.sync_physical_state()
        self.swarm.sync()
        self.gateway = MEPGateway(self.env, self.swarm.kb, mesh=self.swarm.mesh, coordinator=self.env.coordinator)
        self.hub = FederatedMEPHub()
        self.env_a = self.hub.register("primary", self.gateway, tags=["drone", "swarm"])

        reserve = [Drone("GAMMA", "drone_2")]
        self.env2 = DroneSwarmEnvironment(reserve)
        self.swarm2 = SwarmKnowledge(reserve)
        async def boot2():
            for drone in reserve:
                await self.env2.admit(drone)
        asyncio.run(boot2())
        reserve[0].sensor_update(8.0, 0.0, 3.0, 93.0, True, wind_speed=1.0)
        reserve[0].physical.airborne = True
        reserve[0].set_dynamic("airborne", True)
        reserve[0].sync_physical_state()
        self.swarm2.sync()
        self.gateway2 = MEPGateway(self.env2, self.swarm2.kb, mesh=self.swarm2.mesh, coordinator=self.env2.coordinator)
        self.env_b = self.hub.register("reserve", self.gateway2, tags=["reserve", "drone"])
        self.server = MEPJsonRpcServer(self.gateway, hub=self.hub)

    def test_mission_policy_changes_bid_penalty(self) -> None:
        async def scenario():
            self.drones[0].set_dynamic('task_load', 3.0)
            bindings = [self.env.coordinator.binding_for(d, 'Flight', channel='swarm') for d in self.drones]
            base_task = {
                'task_id': 't1', 'description': 'move', 'goal_dimension': 'spatial', 'goal_meaning': 'move', 'goal_magnitude': 0.9,
                'required_roles': ['pilot'], 'preferred_contexts': ['Flight'], 'channel': 'swarm',
                'payload': {'dx': 1.0, 'action_type_hint': 'drone.move'},
            }
            resp_default = await self.server.handle(JsonRpcRequest(method='mep.multi.negotiate', params={'bindings': [b.to_dict() for b in bindings], 'task': base_task}, id=1), actor=self.drones[0], context=self.env.flight)
            heavy = dict(base_task)
            heavy['mission_policy'] = {'load_weight': 4.0, 'risk_weight': 2.0}
            resp_heavy = await self.server.handle(JsonRpcRequest(method='mep.multi.negotiate', params={'bindings': [b.to_dict() for b in bindings], 'task': heavy}, id=2), actor=self.drones[0], context=self.env.flight)
            bids_default = {bid['agent_id']: bid for bid in resp_default.to_dict()['result']['bids']}
            bids_heavy = {bid['agent_id']: bid for bid in resp_heavy.to_dict()['result']['bids']}
            self.assertIn('risk_penalty', next(iter(bids_heavy.values()))['score_components'])
            self.assertLessEqual(bids_heavy[self.drones[0].element_id]['score_components']['load_penalty'], bids_default[self.drones[0].element_id]['score_components']['load_penalty'])
        asyncio.run(scenario())

    def test_federation_resolve_and_route_task(self) -> None:
        async def scenario():
            task = {
                'task_id': 'reserve-task',
                'description': 'reserve move',
                'goal_dimension': 'spatial',
                'goal_meaning': 'reserve move',
                'goal_magnitude': 0.9,
                'required_roles': ['pilot'],
                'preferred_contexts': ['Flight'],
                'channel': 'swarm',
                'payload': {'dx': 1.0, 'action_type_hint': 'drone.move'},
                'preferred_environment_tags': ['reserve'],
            }
            resolved = await self.server.handle(JsonRpcRequest(method='mep.federation.resolve_task', params={'task': task}, id=3), actor=self.drones[0], context=self.env.flight)
            resolved_result = resolved.to_dict()['result']
            self.assertEqual(resolved_result['selected']['environment_id'], self.env_b)
            routed = await self.server.handle(JsonRpcRequest(method='mep.federation.route_task', params={'task': task, 'required_method': 'mep.multi.negotiate'}, id=4), actor=self.drones[0], context=self.env.flight)
            routed_result = routed.to_dict()['result']
            self.assertEqual(routed_result['environment_id'], self.env_b)
            self.assertEqual(routed_result['response']['result']['task']['task_id'], 'reserve-task')
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
