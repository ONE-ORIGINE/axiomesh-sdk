from __future__ import annotations

import unittest

from savoir_core import Evidence, KnowledgeBase, KnowledgeConstraint, KnowledgePolicy


class KnowledgeTests(unittest.TestCase):
    def test_numeric_revision_requests_revalidation_on_spread(self) -> None:
        kb = KnowledgeBase()
        kb.register_policy(KnowledgePolicy(prefix="drone_", contradiction_threshold=0.2, source_bias={"gps": 1.0, "lidar": 1.0}))
        kb.revise_numeric(
            "drone_0.x",
            [
                Evidence(source="gps", value=0.0, weight=1.0),
                Evidence(source="lidar", value=3.0, weight=1.0),
            ],
        )
        queue = kb.revalidation_queue("drone_")
        self.assertTrue(queue)
        self.assertEqual(kb.all_facts("drone_")[0].status.value, "contradicted")

    def test_constraint_report_has_energy(self) -> None:
        kb = KnowledgeBase()
        kb.add_constraint(KnowledgeConstraint("battery", "drone_0.battery", ">=", 15.0, weight=0.1))
        kb.assert_known("drone_0.battery", 10.0)
        report = kb.constraint_report("drone_")
        self.assertEqual(len(report), 1)
        self.assertGreater(report[0]["energy"], 0.0)


if __name__ == "__main__":
    unittest.main()
