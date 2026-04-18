from __future__ import annotations

import json
import unittest
from pathlib import Path

from mep_core import MEP_VERSION, SDK_VERSION, build_json_schema_catalog, build_protocol_spec


class FinalReleaseTests(unittest.TestCase):
    def test_final_versions(self) -> None:
        self.assertEqual(SDK_VERSION, '1.0.1')
        self.assertEqual(MEP_VERSION, '2.0.0')

    def test_generated_catalogs_are_in_sync(self) -> None:
        root = Path(__file__).resolve().parents[1]
        catalog = json.loads((root / 'MEP_METHOD_CATALOG.json').read_text())
        schema = json.loads((root / 'MEP_PROTOCOL_SCHEMA.json').read_text())
        self.assertEqual(catalog['version'], MEP_VERSION)
        self.assertEqual(catalog['sdk_version'], SDK_VERSION)
        self.assertEqual(schema['version'], MEP_VERSION)
        self.assertEqual(schema['sdk_version'], SDK_VERSION)
        self.assertEqual(catalog['method_count'], len(build_protocol_spec()['methods']))
        self.assertEqual(schema['method_count'], len(build_json_schema_catalog()['methods']))

    def test_release_docs_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in ['README.md', 'MEP_SPEC.md', 'CHANGELOG.md', 'RELEASE_NOTES.md']:
            self.assertTrue((root / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
