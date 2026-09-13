# ADR 0003: OPA and Cedar for Declarative Policy Engine

## Status
Accepted

## Context
Authorizing agent actions (executing commands, modifying files, requesting network egress, accessing secrets) requires expressive, declarative security policies. Hardcoding policy checks in Python conditional statements violates separation of concerns, complicates auditing, and increases the risk of bypasses.

## Decision
1. Decouple policy decision-making from policy enforcement across S-Class.
2. Adopt Open Policy Agent (OPA) / Rego as the primary declarative policy engine, feeding structured JSON into the engine and receiving `ALLOW`, `DENY`, or `REQUIRE_APPROVAL` decisions.
3. Design a modular `PolicyEngine` interface that supports evaluating AWS Cedar for fine-grained authorization schemas.
4. S-Class retains sole ownership of enforcement, credential gating, interactive user prompts, and execution observation.

## Consequences
- **Positive**: Security policies become declarative, version-controlled bundles that can be audited and unit-tested in isolation without starting the full S-Class daemon.
- **Negative**: Adds dependency on embedded OPA Wasm or local evaluation runtime.
- **Invariants Upheld**: Invariant I8 (Unknown security state fails closed).
