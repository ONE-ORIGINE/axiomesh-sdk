from __future__ import annotations

import unittest

import edp
import mep
import savoir


class CompatibilityTests(unittest.TestCase):
    def test_legacy_import_surface_exists(self) -> None:
        self.assertTrue(hasattr(edp, "Environment"))
        self.assertTrue(hasattr(mep, "MepGateway"))
        self.assertTrue(hasattr(savoir, "Savoir"))

    def test_environmental_state_matrix_compat(self) -> None:
        matrix = savoir.EnvironmentalStateMatrix(["d0"], ["x", "y"])
        matrix.set("d0", "x", 1.0, 1.0)
        matrix.set("d0", "y", 2.0, 0.5)
        flat = matrix.flatten()
        self.assertEqual(flat[:4], [1.0, 1.0, 2.0, 0.5])


if __name__ == "__main__":
    unittest.main()
