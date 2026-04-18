from __future__ import annotations

import asyncio
import unittest

from drone_sdk.model import Drone, DroneSwarmEnvironment, SwarmKnowledge
from mep_core import FederatedMEPHub, JsonRpcRequest, MEPGateway, MEPJsonRpcServer


class ArbitrationRollbackFederationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.drones = [Drone("ALPHA", "drone_0"), Drone("BETA", "drone_1")]
        self.env = DroneSwarmEnvironment(self.drones)
        self.swarm = SwarmKnowledge(self.drones)
        async def boot():
            for drone in self.drones:
                await self.env.admit(drone)
        asyncio.run(boot())
        for i, drone in enumerate(self.drones):
            drone.sensor_update(float(i * 3), 0.0, 3.0, 98.0, True, wind_speed=3.0)
            drone.physical.airborne = True
            drone.set_dynamic("airborne", True)
            drone.sync_physical_state()
        self.swarm.sync()
        self.swarm.connect_neighbors_by_distance(radius=8.0)
        self.gateway = MEPGateway(self.env, self.swarm.kb, mesh=self.swarm.mesh, coordinator=self.env.coordinator)
        self.hub = FederatedMEPHub()
        self.hub.register("swarm-a", self.gateway, tags=["drone"])
        self.server = MEPJsonRpcServer(self.gateway, hub=self.hub)

    def test_arbitration_and_provenance(self) -> None:
        async def scenario():
            bindings = [self.env.coordinator.binding_for(drone, 'Flight', channel='swarm') for drone in self.drones]
            task = {
                'task_id': 'tight-bid',
                'description': 'tight bid task',
                'goal_dimension': 'spatial',
                'goal_meaning': 'move',
                'goal_magnitude': 0.95,
                'required_roles': ['pilot'],
                'preferred_contexts': ['Flight'],
                'channel': 'swarm',
                'payload': {'dx': 1.0, 'action_type_hint': 'drone.move'},
            }
            neg = await self.server.handle(JsonRpcRequest(method='mep.multi.negotiate', params={'bindings': [b.to_dict() for b in bindings], 'task': task}, id=1), actor=self.drones[0], context=self.env.flight)
            payload = neg.to_dict()['result']
            self.assertIn('arbitration', payload)
            prov = await self.server.handle(JsonRpcRequest(method='mep.provenance.trace', params={'limit': 10}, id=2), actor=self.drones[0], context=self.env.flight)
            self.assertGreaterEqual(len(prov.to_dict()['result']['items']), 1)
        asyncio.run(scenario())

    def test_rollback_on_failure(self) -> None:
        async def scenario():
            bindings = [self.env.coordinator.binding_for(self.drones[0], 'Flight', channel='swarm'), self.env.coordinator.binding_for(self.drones[1], 'Flight', channel='swarm')]
            tasks = [
                {
                    'task_id': 'ok-move', 'description': 'first move', 'goal_dimension': 'spatial', 'goal_meaning': 'move', 'goal_magnitude': 0.95,
                    'required_roles': ['pilot'], 'preferred_contexts': ['Flight'], 'target_agent_ids': [self.drones[0].element_id], 'channel': 'swarm',
                    'payload': {'dx': 2.0, 'dy': 0.0, 'dz': 0.0, 'action_type_hint': 'drone.move'},
                },
                {
                    'task_id': 'fail-move', 'description': 'second move fails', 'goal_dimension': 'spatial', 'goal_meaning': 'move', 'goal_magnitude': 0.95,
                    'required_roles': ['pilot'], 'preferred_contexts': ['Flight'], 'target_agent_ids': [self.drones[1].element_id], 'depends_on': ['ok-move'], 'channel': 'swarm',
                    'payload': {'dx': 1.0, 'force_fail': True, 'action_type_hint': 'drone.move'},
                },
            ]
            # monkeypatch handler behavior via payload-aware failure on move
            original = self.env.flight.actions[0] if self.env.flight.actions else None
            exe = await self.server.handle(JsonRpcRequest(method='mep.multi.execute', params={'bindings': [b.to_dict() for b in bindings], 'tasks': tasks, 'initiator': 'test'}, id=3), actor=self.drones[0], context=self.env.flight)
            payload = exe.to_dict()['result']
            self.assertTrue(payload['rolled_back'])
            self.assertGreaterEqual(len(payload['compensations']), 1)
        asyncio.run(scenario())

    def test_federation_card(self) -> None:
        async def scenario():
            fed = await self.server.handle(JsonRpcRequest(method='mep.federation.card', params={}, id=4), actor=self.drones[0], context=self.env.flight)
            payload = fed.to_dict()['result']
            self.assertGreaterEqual(len(payload['environments']), 1)
        asyncio.run(scenario())


if __name__ == '__main__':
    unittest.main()
