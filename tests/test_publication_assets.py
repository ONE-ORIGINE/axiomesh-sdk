import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class TestPublicationAssets(unittest.TestCase):
    def test_publication_files_exist(self):
        expected = [
            'LICENSE',
            'NOTICE',
            'CONTRIBUTING.md',
            'SECURITY.md',
            'CODE_OF_CONDUCT.md',
            'CITATION.cff',
            'PUBLISHING_GUIDE.md',
            'MEP_PROTOCOL_SCHEMA.json',
            'MEP_METHOD_CATALOG.json',
            'MEP_METHOD_CATALOG.md',
        ]
        for rel in expected:
            self.assertTrue((ROOT / rel).exists(), rel)

if __name__ == '__main__':
    unittest.main()
