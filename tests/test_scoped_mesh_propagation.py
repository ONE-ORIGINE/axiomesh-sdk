from __future__ import annotations

import unittest

from savoir_core import SharedKnowledgeMesh


class ScopedMeshPropagationTests(unittest.TestCase):
    def test_channel_and_hops_limit_visibility(self) -> None:
        mesh = SharedKnowledgeMesh()
        mesh.observe('a', 'drone_0.x', 1.0, share=False)
        mesh.connect('a', 'b', channel='proximity')
        mesh.connect('b', 'c', channel='proximity')
        mesh.connect('a', 'd', channel='internal')

        mesh.publish_scoped('a', 'drone_0.x', channels=['proximity'], max_hops=1)
        self.assertIsNotNone(mesh.local('b').know('drone_0.x'))
        self.assertIsNone(mesh.local('c').know('drone_0.x'))
        self.assertIsNone(mesh.local('d').know('drone_0.x'))

        snap = mesh.neighborhood_snapshot('a', prefix='drone_', channels=['proximity'], max_hops=2)
        self.assertIn('b', snap['neighbors'])
        self.assertGreaterEqual(len(snap['visible_facts']), 1)


if __name__ == '__main__':
    unittest.main()
