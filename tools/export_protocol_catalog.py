from __future__ import annotations

import json
from pathlib import Path

from mep_core import build_json_schema_catalog, build_markdown_spec, build_protocol_spec

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    (ROOT / 'MEP_METHOD_CATALOG.json').write_text(json.dumps(build_protocol_spec(), indent=2) + '\n')
    (ROOT / 'MEP_METHOD_CATALOG.md').write_text(build_markdown_spec())
    (ROOT / 'MEP_PROTOCOL_SCHEMA.json').write_text(json.dumps(build_json_schema_catalog(), indent=2) + '\n')


if __name__ == '__main__':
    main()
