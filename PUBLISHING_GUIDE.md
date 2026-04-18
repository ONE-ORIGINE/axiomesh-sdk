# Publishing Guide

## Release baseline

This repository is structured as a public release baseline.
Before publishing:

1. Confirm the final repository URL fields in `pyproject.toml`.
2. Confirm the copyright holder in `NOTICE`.
3. Regenerate protocol artifacts:
   ```bash
   python tools/export_protocol_catalog.py
   ```
4. Run tests:
   ```bash
   PYTHONPATH=src python -m unittest discover -s tests -v
   ```
5. Run the demo:
   ```bash
   PYTHONPATH=src python -m drone_sdk.demo
   ```
6. Build distributions:
   ```bash
   python -m build
   ```
7. Tag the release and publish.

## Suggested public positioning

AxiomMesh SDK is a runtime and protocol stack for agents that operate inside structured environments with explicit certainty, constrained action spaces, and federated multi-agent execution.


## GitHub-first release flow

Use GitHub as the source of truth first, then publish from a tagged commit with Trusted Publishing. See `GITHUB_PUBLICATION_GUIDE.md`.
