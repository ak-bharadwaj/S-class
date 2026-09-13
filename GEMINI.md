# S-Class Agent Operational Instructions (Gemini)

## 1. Immutable Architectural Laws
1. **The Agent is Never the Authority**: An agent can request work, but it can never certify its own work. All completions must be independently observed and verified by S-Class.
2. **Fail-Closed Security**: Any unknown binary, ambiguous path, or unhandled security state fails closed (UNKNOWN or DENY).
3. **No Direct State Upgrades**: Claims never jump directly from CLAIMED to ACCEPTED. They require observed receipts anchored into the immutable ledger.
4. **Zero-Drift Handoff**: Handoff packages are assembled from persisted SQLite state and cryptographic ledger receipts, not conversational memory.

## 2. Trust Invariants (I1 - I10)
Refer to [Architecture Invariants](docs/architecture/invariants.md) for full definitions:
- **I1**: Agent claims are untrusted.
- **I2**: Agent-supplied evidence is non-authoritative.
- **I3**: Observations originate from S-Class controlled execution.
- **I4**: Verification cannot be substituted by caller-selected verifier output.
- **I5**: Accepted state references immutable evidence.
- **I6**: Workspace mutation invalidates dependent evidence.
- **I7**: Handoff contains persisted truth, not chat memory.
- **I8**: Unknown security state fails closed.
- **I9**: Protocol adapters cannot directly certify execution.
- **I10**: Memory can provide context but cannot create truth.

## 3. Implementation Workflow
1. **TDD / Test-First**: Write or identify reproducing tests before implementing changes.
2. **Focused Diff**: Avoid unrelated refactorings or speculative generalizations.
3. **Single Source Tree**: All production code lives under src/sclass/. Never reintroduce a root sclass/ tree.
4. **Zero Secret Leaks**: Never commit .env or credential files. Maintain sanitized variable names in .env.example.

## 4. Test & Verification Requirements
1. **Full Test Suite**: All tests must pass cleanly:
   ```bash
   python -m pytest tests/
   ```
2. **Product Demos**: All 5 flagship demos must run 100% green:
   ```bash
   python demos/run_all_demos.py
   ```
3. **No Test Weakening**: Never weaken, disable, or delete existing tests to force a pass.

## 5. Architectural Reference Links
- **Architecture**:
  - [Authority Model](docs/architecture/authority-model.md)
  - [Architecture Invariants](docs/architecture/invariants.md)
  - [State Model](docs/architecture/state-model.md)
  - [Trust Model](docs/architecture/trust-model.md)
  - [Lifecycle & Execution](docs/architecture/lifecycle.md)
- **Security**:
  - [Threat Model](docs/security/threat-model.md)
  - [Protected Resources](docs/security/protected-resources.md)
- **Protocols & Integrations**:
  - [Protocol Overview](docs/protocols/overview.md)
  - [ACP Adapter](docs/integrations/acp.md)
  - [MCP Adapter](docs/integrations/mcp.md)
  - [Claude Adapter](docs/integrations/claude.md)
  - [Codex Adapter](docs/integrations/codex.md)
- **Implementation**:
  - [Implementation Guide](docs/implementation/overview.md)

## Active S-Class Playbooks

- **tdd-workflow**: Strict Test-Driven Development playbook for implementing new features or bugfixes
- **refactoring-patterns**: Safe behavior-preserving refactoring patterns and technical debt elimination
