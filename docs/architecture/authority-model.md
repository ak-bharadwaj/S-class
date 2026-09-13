# S-Class Authority & Boundary Model

## 1. Resource Boundaries

S-Class classifies all system, workspace, and internal state paths into four distinct authority boundaries (`AuthorityBoundary`):

1. `AGENT_WRITABLE`: General application source code, tests, documentation, and agent scratchpads. Agents have write capabilities subject to security policies.
2. `SCLASS_WRITABLE`: Internal S-Class operational directories (checkpoints, metrics, logs, run cache). Agents cannot directly modify; only S-Class runtime operations can write.
3. `SCLASS_VERIFICATION_ONLY`: Immutable snapshots and verification artifacts. Read-only during verification cycles.
4. `SCLASS_TRUST_ROOT`: Protected cryptographic trust roots, including:
   - `.sclass/ledger.jsonl`
   - `.sclass/trust_anchors.json`
   - `.sclass/sclass.db`
   - `sclass.config.json`
   - Verification policy definitions.
   Strictly protected: any agent action or MCP tool call attempting to write, delete, or modify these resources is immediately DENIED with an authorization policy violation.

## 2. Capability System

Actions declare explicit required capabilities:
- `READ`
- `WRITE`
- `EXECUTE`
- `DELETE`
- `NETWORK`
- `ADMIN`
- `VERIFY`

The `PolicyEngine` evaluates the principal (agent/tool), action context, target resource boundary, and required capabilities before authorizing execution.
