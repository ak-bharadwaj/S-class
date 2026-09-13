# S-Class Architecture Invariants

This document codifies the 10 immutable architectural invariants of S-Class.
Every subsystem, pull request, integration adapter, and verification component must uphold these invariants without exception.

---

### I1: Agent claims are untrusted.
- **Rule**: An agent's self-reported success or completion assertion is strictly untrusted input.
- **Enforcement**: Claims submitted by agents are placed in CLAIMED or EVIDENCE_REQUIRED states. No claim can transition directly to ACCEPTED based on agent statements or logs alone.
- **Failure Mode Prevented**: Agents declaring \"All tests pass!\" when subprocess execution failed, timed out, or was never run.

### I2: Agent-supplied evidence is non-authoritative.
- **Rule**: Agents cannot manufacture, sign, or certify evidence receipts.
- **Enforcement**: Receipts supplied directly in agent payloads are classified as ClaimedEvidence or ProposedEvidence and rejected by the VerificationEngine.
- **Failure Mode Prevented**: Agent spoofing receipts with forged test counts, fake hashes, or simulated exit codes.

### I3: Observations originate from S-Class controlled execution.
- **Rule**: Authoritative observations must be produced by the S-Class execution observer (ObservationFactory / ProcessRunner).
- **Enforcement**: Process execution is observed via platform-native process inspection (ExecutionIdentity), computing actual binary paths, binary SHA-256 hashes, process start times, and exit codes, sealed with an append-only token.
- **Failure Mode Prevented**: Bypassing observation via shell wrapper tricks, symlink spoofing, or hijacked PATH binaries.

### I4: Verification cannot be substituted by caller-selected verifier output.
- **Rule**: The caller cannot dictate or mock the verifier's internal evaluation logic.
- **Enforcement**: The VerifierTrustRegistry evaluates execution identity against registered, allowlisted verifiers. If an agent requests pytest but executes an unverified script or generic wrapper, the verification engine rejects the claim with a verifier mismatch verdict.
- **Failure Mode Prevented**: Agent executing cho all tests passed while claiming it was a legitimate pytest run.

### I5: Accepted state references immutable evidence.
- **Rule**: Any task or claim in ACCEPTED or VERIFIED state must reference an immutable, cryptographically anchored evidence receipt.
- **Enforcement**: Every accepted claim records the eceipt_id, eceipt_hash, and is anchored into the append-only LocalLedger hash chain.
- **Failure Mode Prevented**: Ghost verifications, unbacked state changes, and unverifiable claims.

### I6: Workspace mutation invalidates dependent evidence.
- **Rule**: Any mutation to relevant workspace files or repository state after observation invalidates all dependent evidence receipts.
- **Enforcement**: Pre- and post-observation workspace snapshots compute SHA-256 tree fingerprints. Subsequent workspace file modifications cause staleness checks to fail, immediately transitioning verified claims to INVALIDATED.
- **Failure Mode Prevented**: Time-of-check to time-of-use (TOCTOU) bugs, post-verification tampering, and committing untested mutations.

### I7: Handoff contains persisted truth, not chat memory.
- **Rule**: Cross-agent handoff packages derive purely from persisted SQLite state, immutable receipts, and the cryptographic ledger—never from agent transcripts, prompt summaries, or LLM memory.
- **Enforcement**: HandoffAssembler queries the authoritative state store (StateRepository) and ledger (LocalLedger). If state is corrupted or unavailable, handoff fails closed (HandoffIntegrityError).
- **Failure Mode Prevented**: Hallucinated progress, lost failure context, and conversational drift across agent transitions.

### I8: Unknown security state fails closed.
- **Rule**: When security classification, binary path authority, or permission state cannot be authoritatively resolved, the system defaults to denial.
- **Enforcement**: Unknown binaries classify as UNKNOWN (never SYSTEM_TRUSTED). Unrecognized paths or ambiguous policy requests result in DENY decisions.
- **Failure Mode Prevented**: Accidental privilege escalation, running malicious binaries placed in PATH, or executing destructive actions on ambiguous targets.

### I9: Protocol adapters cannot directly certify execution.
- **Rule**: External protocol adapters (ACP, MCP, Claude, Codex, Cursor, OpenCode) are transport and control surfaces only; they cannot bypass or certify execution.
- **Enforcement**: All adapter actions are converted into universal ActionRequest objects evaluated by policy, observed by the execution plane, and verified by the verification plane.
- **Failure Mode Prevented**: Vulnerabilities in protocol libraries leading to unauthorized bypass of trust gates.

### I10: Memory can provide context but cannot create truth.
- **Rule**: Semantic memory, vector stores, graph databases, and context compressors provide advisory candidate context, but cannot assert or mutate verified state.
- **Enforcement**: The state repository and ledger remain the sole source of truth. If memory recalls that a task was completed, but no accepted verification receipt exists in state, the task remains unverified.
- **Failure Mode Prevented**: Memory poisoning attacks, stale context reviving rejected claims, and hallucinations masquerading as verified facts.
