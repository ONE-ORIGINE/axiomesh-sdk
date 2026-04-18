# Contributing

## Workflow

1. Fork the repository.
2. Create a feature branch.
3. Keep changes scoped and test-backed.
4. Run the test suite before opening a pull request.
5. Update protocol artifacts if the MEP surface changes.

## Development commands

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
PYTHONPATH=src python -m drone_sdk.demo
python tools/export_protocol_catalog.py
```

## Contribution rules

- Do not break protocol compatibility without documenting the change.
- Prefer additive changes to MEP over silent semantic drift.
- Keep EDP, MEP, and SAVOIR responsibilities separated.
- For new protocol methods, update:
  - `src/mep_core/registry.py`
  - `MEP_PROTOCOL_SCHEMA.json`
  - `MEP_METHOD_CATALOG.json`
  - `MEP_METHOD_CATALOG.md`
  - `MEP_SPEC.md`

## Pull request checklist

- tests pass
- demo still runs
- docs updated
- protocol artifacts regenerated when needed
- changelog entry added
