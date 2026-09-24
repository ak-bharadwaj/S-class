# S-Class Zero-Trust Security Invariants

This specification codifies the 19 critical security invariants established and verified during the H2 Extreme-Safety certification audit.

## Threat Assumptions
All inputs entering the S-Class control plane are considered untrusted:
1. **Agent output** is UNTRUSTED (claims, explanations, status strings).
2. **Runtime output** is UNTRUSTED (raw exit codes, tool results, simulated RPC responses).
3. **Caller `AuthorizationDecision`** is UNTRUSTED (in-memory objects, caller-supplied tokens).
4. **In-memory project state** is UNTRUSTED until anchored in the canonical assurance ledger.
5. **SQLite derived state** is UNTRUSTED (ephemeral index, subject to rebuild on drift).
6. **Caller timestamps** are UNTRUSTED (must not dictate mutation freshness boundaries).

---

## The 19 Certified Invariants (CF-01 – CF-19)

### 1. Cryptographic Sealing of Authorizations (CF-01)
Every `AuthorizationDecision` with outcome `ALLOW` must carry an authentic HMAC-SHA256 integrity token minted by S-Class. In-memory fabrication of decisions without valid tokens fails closed.

### 2. Task-ID and Session Isolation (CF-02)
`task_id` is an independent first-class field distinct from `session_id`. An authorization granted for Task A in Session S cannot verify, authorize, or execute an action for Task B in Session S.

### 3. Canonical Persistence Precondition (CF-03)
`CompletionEvaluator` requires authoritative on-disk ledger persistence. If `.sclass/trust/assurance_ledger.jsonl` is missing, task completion fails closed (`BLOCK` or `UNAVAILABLE`).

### 4. Timestamp Strictness and Skew Bounds (CF-04)
Authorization decisions enforce strict ISO 8601 UTC timestamps with mandatory timezone awareness. Naive timestamps, malformed formats, and clock skew exceeding 30 seconds are rejected fail-closed.

### 5. Missing Process Exit Code Strict Failure (CF-05)
A subprocess observation where `exit_code is None` strictly evaluates to `passed = False`. Ambiguous or interrupted child execution never converts into passing evidence.

### 6. Ledger Multi-Instance Split-Brain Resistance (CF-06)
`AssuranceLedger.append_entry` reloads on-disk state under file lock prior to assigning sequences and computing the SHA-256 hash chain, preventing concurrent split-brain mutations.

### 7. Authenticated Record Chain Reduction (CF-07)
`CanonicalStateReducer` validates that all historical records contain valid sequence numbers, record hashes, previous record hashes, and HMAC authenticators.

### 8. Derived Cache Integrity Verification (CF-08)
`CanonicalOperationStore` validates SQLite derived rows against canonical JSONL records upon retrieval, automatically triggering an index rebuild on discrepancy.

### 9. Production Strict-Mode Test Double Denial (CF-09)
When `SCLASS_STRICT_SECURITY=1` or `SCLASS_ENVIRONMENT=production`, test double harness execution is strictly blocked.

### 10. Upstream Tool Event Schema Normalization (CF-10)
RPC extensions inspect canonical `event.toolName` and `event.input` to ensure upstream protocol schema changes cannot evade parameter interception.

### 11. Child Process Environment Sanitization (CF-11)
Subprocess observers strip all sensitive secrets (`SCLASS_AUTH_SECRET`, `SCLASS_TOKEN`, `SCLASS_HMAC_SECRET`) before spawning unprivileged child tasks.

### 12. Reparse Point and Symlink Containment (CF-12)
Filesystem observation resolves absolute canonical realpaths via `os.path.realpath`, blocking directory junction, symlink, and hardlink workspace escapes.

### 13. Destructive Command and Inline Interpreter Defense (CF-13)
The command analyzer rejects destructive shell commands (`rm -rf /`), inline code interpreters (`python -c`, `powershell -EncodedCommand`), base64 decoding, UNC paths, and sensitive system file reads (`/etc/passwd`).

### 14. Non-Empty Capability Identifiers (CF-14)
Authorizations must be bound to non-empty capability IDs and authoritative capability schema hashes. Decisions with empty capability hashes fail closed.

### 15. Scope-Sealed HMAC Tokens (CF-15)
Integrity tokens cryptographically bind `workspace_id`, `task_id`, and `session_id`. Modifying workspace or task scope invalidates the token.

### 16. Anti-Sham Operation Recovery (CF-16)
`recover_operation()` transitions ambiguous or unobserved operations to `RECOVERY_REQUIRED`. It never synthesizes recovery success without physical observation.

### 17. Tamper-Proof Evidence Freshness (CF-17)
Freshness evaluation derives mutation boundaries directly from monotonic ledger mutation timestamps, rejecting caller-provided artificial timestamps.

### 18. Canonical Verifier Executable Pinning (CF-18)
Verifiers resolve and verify canonical absolute binary paths and binary digests against the trusted verifier registry, preventing `PATH` substitution attacks.

### 19. Content-Bound Action Hashes (CF-19)
Action hashes incorporate the SHA-256 digest of regular target files on disk, eliminating Time-of-Check to Time-of-Use (TOCTOU) parameter modification windows.
