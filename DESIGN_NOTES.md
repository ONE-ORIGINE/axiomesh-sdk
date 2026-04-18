# Design Notes

## Core split

- `edp_core`: environment runtime and mathematical export
- `savoir_core`: certainty, evidence, constraints, and knowledge mesh
- `mep_core`: protocol, transport, federation, provenance, recovery
- `drone_sdk`: reference domain package

## Stability decisions

- the public protocol surface is versioned in `mep_core.registry`
- schema and markdown catalogs are generated from the same registry
- deprecated aliases are resolved centrally, not ad hoc inside handlers
- drone internals use explicit state partitions instead of a generic `state` field
- tests cover local, distributed, and federated flows
