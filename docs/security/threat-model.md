# S-Class Threat Model & Red Team Attacks

## 1. Adversary Model

S-Class models the AI Coding Agent as an untrusted or semi-trusted actor that may:
1. Hallucinate success or attempt to cheat verification to satisfy task objectives.
2. Fabricate evidence receipts claiming tests passed.
3. Mutate evidence objects in memory or on disk.
4. Tamper with the cryptographic ledger or truncate event logs.
5. Spoof verifier identity using wrapper scripts, shell aliases, or `-c` arbitrary code commands.
6. Target internal S-Class configuration and state files (`.sclass/`, `sclass.config.json`).
7. Escape execution boundaries using directory traversal, symlinks, junctions, or shell chaining.
8. Perform Time-of-Check to Time-of-Use (TOCTOU) workspace modifications.

## 2. Attack Vectors & Mitigations

### Attack A: Fake Evidence Receipt
- **Attack**: Agent manufactures a JSON receipt claiming `exit_code: 0, failed_tests: 0`.
- **Mitigation**: Verification engine requires receipt presence in append-only cryptographic ledger committed by observation runtime. Uncommitted receipts are rejected.

### Attack B: Interpreter Spoofing
- **Attack**: Agent runs `python -c "import sys; sys.exit(0)"` and claims it was `pytest`.
- **Mitigation**: `StandardVerifierDetector` inspects actual `argv` and execution chain. `-c` / `-e` invocations are classified as `generic_command`, not test runners.

### Attack C: Path Hijack
- **Attack**: Agent places an executable named `pytest` or `npm` in a custom directory.
- **Mitigation**: `ExecutionIdentity` captures true executable binary path and SHA-256 binary hash.

### Attack D: Wrapper Executables
- **Attack**: Agent invokes a shell script or batch file that wraps the real runner.
- **Mitigation**: `detect_wrapper_executable` and `ExecutionChain` unwrap the caller chain to observe true child process identity and arguments.

### Attack E & F: Receipt Mutation
- **Attack**: Agent modifies fields of an `EvidenceReceipt` in memory or recalculates hash.
- **Mitigation**: Receipts are sealed (`_sealed = True`), raising `AttributeError` on post-creation mutation. Ledger hash chain verification detects any payload modification.

### Attack G: Ledger Tampering
- **Attack**: Agent modifies or deletes lines in `.sclass/ledger.jsonl`.
- **Mitigation**: `LocalLedger.verify()` evaluates the hash chain. Any broken hash triggers tamper detection and ledger repair/reset.

### Attack H & TOCTOU: Workspace Mutation
- **Attack**: Agent modifies files after tests pass but before checkpointing.
- **Mitigation**: Verification receipts capture `workspace_fingerprint`. Any file modification updates the fingerprint and invalidates prior verification.

### Attack I & J: Protected Resource Escape
- **Attack**: Agent or MCP tool attempts to overwrite `.sclass/ledger.jsonl` or `sclass.db`.
- **Mitigation**: `PolicyEngine` and `check_protected_resource_targeting` block any action targeting `SCLASS_TRUST_ROOT`.

### Attack K: In-Memory Authorization Forgery & Missing HMAC Token (H2)
- **Attack**: Agent creates an in-memory `AuthorizationDecision(outcome=ALLOW)` and invokes execution directly.
- **Mitigation**: `DualLayerAuthorizer` and `StepCodeRpcHarness` enforce mandatory HMAC-SHA256 signature verification over all decision fields, failing closed if unsigned or tampered.

### Attack L: Cross-Task Authorization Transplanting (H2)
- **Attack**: Authorization issued for Task A is replayed to execute actions under Task B.
- **Mitigation**: Independent `task_id` and `session_id` fields are sealed into the HMAC token and cross-checked against the active execution context.

### Attack M: Reparse Point and Directory Junction Workspace Escape (H2)
- **Attack**: Agent creates NTFS directory junctions or symlinks pointing outside the workspace root to access forbidden files.
- **Mitigation**: `IsolatedSubprocessObserver` resolves canonical targets using `os.path.realpath` before permitting read/write operations.

### Attack N: Derived Index SQLite Cache Poisoning (H2)
- **Attack**: Attacker modifies SQLite cache to alter apparent task/operation state.
- **Mitigation**: `CanonicalOperationStore` validates SQLite cache records against the canonical JSONL ledger, re-indexing automatically if discrepancies are detected.

### Attack O: Target File TOCTOU Modification (H2)
- **Attack**: Target file is altered between authorization issuance and physical tool execution.
- **Mitigation**: `compute_action_hash` incorporates the SHA-256 digest of regular target files on disk into the sealed action hash.

### Attack P: Subprocess Credential Exfiltration (H2)
- **Attack**: Untrusted build/test subprocess attempts to read `SCLASS_AUTH_SECRET` from environment variables.
- **Mitigation**: `IsolatedSubprocessObserver` sanitizes the child process environment, purging all S-Class secrets prior to spawning.

