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
