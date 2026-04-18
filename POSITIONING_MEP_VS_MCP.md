# MEP vs MCP

## Short statement

MEP is not a surcouche over MCP.
MEP is an independent protocol for structured environments, constrained actions, certainty-aware state, causal explanation, and federated multi-agent execution.

## Design difference

### MCP
MCP is shaped around model-facing access to resources, prompts, and tools.

### MEP
MEP is shaped around environment-facing operation:
- who is acting
- in which context
- with which role limits
- on which validated state
- under which mission policy
- across which agents and environments
- with which causal and provenance trace

## Consequence

If an MCP bridge exists, it should be treated as a compatibility adapter.
It must not define the ontology of MEP.

## Practical rule

- If the question is "how does the model call a capability?" the design pressure is MCP-like.
- If the question is "how does an agent operate inside an evolving world with constraints, certainty, and coordination?" the design pressure is MEP-like.

## Final position

MEP should be presented publicly as:

> a protocol for environment-aware, certainty-aware, causal, federated, multi-agent execution

not as:

> a richer wrapper around tool calling
