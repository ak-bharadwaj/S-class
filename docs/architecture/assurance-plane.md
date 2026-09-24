# S-Class Assurance Plane Architecture

The S-Class Assurance Plane provides an independent, tamper-proof authority over project truth, evidence, and verification. It operates concurrently with external execution harnesses (such as Step-Code, Claude Code, or OpenAI Codex) while maintaining an uncompromised epistemic boundary.

## Core Architectural Components

### 1. Dual-Ledger Architecture
The assurance plane maintains two synchronized, append-only cryptographic journals:
- **Canonical Assurance Ledger (`.sclass/trust/assurance_ledger.jsonl`)**:
  The authoritative source of project truth. Records technical obligations, verified claims, evidence receipts, and state transitions with sequential integers, SHA-256 hash chains, and HMAC signatures.
- **Operational Activity Journal (`.sclass/ledger.jsonl`)**:
  High-frequency action and tool invocation receipts, capturing runtime effects, command outputs, and parameter bindings.

### 2. Canonical State Reducer
The `CanonicalStateReducer` deterministically reconstructs the `VerifiedProjectState` directly from the append-only ledger entries:
- Rejects out-of-order, unsequenced, or unauthenticated records fail-closed.
- Re-verifies hash chain continuity (`previous_record_hash == sha256(...)`).
- Prevents split-brain by locking the ledger on write and refreshing state prior to sequencing.

### 3. Dual-Layer Authorization Gate
Before any state-modifying action executes:
1. **Layer 1 (S-Class Governance)**:
   Policy evaluation verifies actor permissions, capability bindings, risk limits, and seals the request with an HMAC-SHA256 integrity token.
2. **Layer 2 (Step-Code Runtime Guardrails)**:
   Command analysis checks for destructive patterns, shell chaining, and privilege escalation.
3. **Conjunction Rule**:
   Execution requires both layers to permit (`can_execute = sclass_allowed and runtime_allowed`). A denial by either layer immediately halts execution.

### 4. Independent Observation & Verification
Observations are produced exclusively by S-Class observers (`IsolatedSubprocessObserver`), not from self-reported agent narratives:
- Direct capture of process exit code, stdout/stderr hashes, and environment fingerprints.
- Realpath resolution prevents filesystem containment escapes.
- Any subsequent workspace mutation invalidates dependent evidence receipts.
