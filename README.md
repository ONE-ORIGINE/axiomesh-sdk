# AxiomMesh SDK

**EDP + MEP + SAVOIR for context-aware, certainty-aware, federated multi-agent systems.**

AxiomMesh is a release-ready SDK for building agents that operate inside structured environments rather than free-form prompt loops.
It combines:

- **EDP** — an environment design runtime with contexts, rules, actions, reactions, mission planning, and mathematical world export
- **MEP** — the **Model Environment Protocol**, a JSON-RPC-based protocol surface for envelopes, explanation, planning, execution, federation, provenance, health, and resilience
- **SAVOIR** — a certainty layer that separates what is observed, verified, derived, stale, contradicted, or shared
- **Drone SDK** — a reference implementation for drones, swarms, internal sub-agents, and federated mission execution

## Positioning

This SDK is designed for systems where the world matters:

- drones and swarms
- embodied AI
- robotics middleware
- multi-agent coordination
- internal subsystem orchestration inside one machine
- federated execution across environments

The core idea is simple:

> the agent should not guess the world from scratch every turn.
> it should receive a structured environment, a constrained action surface, and a certainty-aware state.

## What makes this stack different

### EDP

EDP turns the environment into an executable decision surface:

- contexts deform the available action space
- rules can be hard or soft
- roles and situation can limit action visibility
- plans can be built locally, cooperatively, or across environments
- the environment can be exported as matrices, graphs, adjacency structures, and factor-like constraints

### MEP

MEP is not a prompt wrapper.
It is not an MCP overlay either.
It is the protocol layer between agents and structured environments.
Its scope is broader than tool invocation:

- world state and certainty transport
- constrained action surfaces
- explanation and why-not semantics
- multi-agent and multi-context coordination
- federated execution across environments
- provenance, replay, resilience, and recovery

It exposes:

- context envelopes
- WHY / WHY-NOT explanations
- health and protocol introspection
- planning and mission preview
- multi-agent bindings and shared envelopes
- negotiation, execution, rollback, recovery, and rerouting
- federation across multiple environments
- chained provenance

### SAVOIR

SAVOIR is the certainty engine.
It distinguishes between:

- observed
- verified
- derived
- stale
- contradicted
- shared

This lets the runtime reason on a validated operational state instead of collapsing every fact into probability.

## Repository layout

```text
src/
  edp_core/      # semantic layer, contracts, rules, runtime, missions, multi-agent coordination
  savoir_core/   # certainty, evidence, local/shared knowledge, mesh propagation
  mep_core/      # protocol surface, gateway, federation, JSON-RPC, registry/spec
  drone_sdk/     # drone/swarm reference implementation
  edp/           # compatibility imports
  mep/           # compatibility imports
  savoir/        # compatibility imports
```

## Install

Local development:

```bash
pip install -e .
```

## Quickstart

Run the drone demo:

```bash
PYTHONPATH=src python -m drone_sdk.demo
```

Run the full test suite:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

## MEP vs MCP

MEP is **not** implemented as a thin layer over MCP.

The difference in design intent is structural:

- **MCP** is centered on exposing resources, prompts, and tools to language-model applications
- **MEP** is centered on exposing **environments, contexts, action surfaces, certainty states, causal traces, and federated multi-agent execution**

In other words:

- MCP helps an application call capabilities
- MEP helps an agent operate inside a constrained, evolving world

MEP can be bridged to other ecosystems later, including MCP-style surfaces, but its native model is **environmental**, **causal**, and **multi-agent** rather than merely tool-oriented.

## Protocol surface

The runtime can expose its protocol shape directly:

- `mep.spec`
- `mep.spec.schema`
- `mep.spec.markdown`
- `mep.method.describe`
- `mep.health`

Generated protocol artifacts are included in this repository:

- `MEP_SPEC.md`
- `MEP_PROTOCOL_SCHEMA.json`
- `MEP_METHOD_CATALOG.json`
- `MEP_METHOD_CATALOG.md`

## Current status

- **SDK version:** `1.0.1`
- **MEP version:** `2.0.0`
- **Status:** release-ready public baseline

## Publication assets included

- `LICENSE`
- `NOTICE`
- `CHANGELOG.md`
- `RELEASE_NOTES.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `CITATION.cff`
- `MEP_SPEC.md`
- `MEP_PROTOCOL_SCHEMA.json`
- `MEP_METHOD_CATALOG.json`
- `tools/export_protocol_catalog.py`

## License

Apache-2.0.
See `LICENSE` and `NOTICE`.


## Publishing

The repository includes GitHub Actions workflows for CI and tagged publishing.

- `.github/workflows/ci.yml` runs the test suite on pushes and pull requests
- `.github/workflows/publish.yml` builds and publishes on tags like `v1.0.1`


