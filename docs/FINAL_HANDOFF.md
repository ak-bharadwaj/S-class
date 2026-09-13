# S-Class Final Core Hardening + Integration Handoff Specification

## Executive Summary

S-Class has completed its transition from **Architectural Scaffold** to **Real Trust Control Plane**. 

The fundamental security invariant now holds across all components:
> **An agent must not be able to manufacture the evidence S-Class uses to certify its own claims.**

- **Target Branch**: `survival-v0`
- **Total Test Count**: **438 Tests** (406 Original Baseline Tests + 32 Adversarial & Red Team Suites)
- **Pass Rate**: **100% Green (438 passed, 0 failed, 0 skipped)**
- **Supported Platforms**: Windows (Win32 API process inspection), Linux (`/proc` filesystem inspection), macOS

---

## 1. Non-Negotiable Invariants Enforced

1. **Agent input is never authoritative**: `ActionRequest` is a request, not an event. Receipts cannot be self-issued.
2. **Observation independent of the observed**: Exit codes, streams, runtimes, and file hashes are captured directly from OS processes.
3. **Execution identity verified, not declared**: Child PIDs, executable hashes, and execution chains are verified at the OS kernel layer.
4. **Trust state is tamper-evident and append-only**: Cryptographic hash-chained ledger (`LocalLedger`) with sealed in-memory receipts.
5. **Claims require mandatory minimum evidence**: Enforced by `ClaimAcceptanceMatrix` (`EXECUTION_VERIFIED != CLAIM_VERIFIED`).
6. **Caller cannot dictate verifier**: Verifier identity is detected by `StandardVerifierDetector` independently of agent claims.
7. **Scope binding prevents partial test exploits**: `ClaimScope` and `TestSelection` verify that executed tests cover claimed targets.
8. **Protected trust roots are inviolable**: `.sclass/`, `sclass.db`, and `trust_anchors.json` cannot be touched by agents or tools.
9. **Multi-agent handoff preserves proof**: Checkpoints bind workspace fingerprints and cryptographic ledger head hashes.
10. **Zero-drift parity**: Codebase mirrors `src/sclass` and root `sclass` identically across primary and secondary repositories.

---

## 2. Core Implementation Components

### Execution Layer (`sclass.execution`)
- `modes.py`: `ExecutionMode` (`HOST_ARGV`, `HOST_SHELL`, `CONTAINER`, `SANDBOX`), `PROTECTED_RESOURCE_PATTERNS`, `check_protected_resource_targeting`, `ExecutionPolicy`.
- `identity.py`: `ExecutionIdentity`, `ExecutionIdentityState`, `ExecutionChain`, Win32 `QueryFullProcessImageNameW`, Linux `/proc`, binary SHA-256 computation, WindowsApps fallback.
- `launcher.py`: `HostLauncher`, `SandboxLauncher`, `ContainerLauncher`, `detect_wrapper_executable`.
- `process.py`: `ProcessRunner` managing child process PID, IO capture, and policy enforcement.
- `provenance.py`: OpenTelemetry process semantic conventions with secret redaction.

### Authority & Control (`sclass.control`)
- `resources.py`: `AuthorityBoundary` (`AGENT_WRITABLE`, `SCLASS_WRITABLE`, `SCLASS_VERIFICATION_ONLY`, `SCLASS_TRUST_ROOT`).
- `capabilities.py`: `Capability` enum (`READ`, `WRITE`, `EXECUTE`, `DELETE`, `NETWORK`, `ADMIN`, `VERIFY`).
- `policy.py`: `DefaultPolicyEngine` gating actions and blocking trust-root tampering, shell chaining, and unauthorized access.

### Verification Layer (`sclass.verification`)
- `detector.py`: `StandardVerifierDetector` evaluating executable hashes, argv tokens, and detecting `-c` script spoofs.
- `result_parser.py`: Normalized test parsers for Pytest, Unittest, and Generic commands.
- `acceptance.py`: `ClaimAcceptanceMatrix` mapping claim types to required evidence levels and default verdicts.
- `verifiers/`: Structured verifiers for Pytest, Unittest, Jest, Vitest, Mocha, Playwright, Cargo, Go, and Npm.
- `engine.py`: Verification engine enforcing Invariant 3 and scope binding.

### Trust & Evidence (`sclass.trust`, `sclass.domain`)
- `evidence.py`: `EvidenceReceipt` with `_sealed = True` immutability.
- `ledger.py`: Append-only `LocalLedger` with hash-chain verification, snapshotting, and corruption repair.
- `anchors.py`: `TrustAnchor` managing cryptographic state roots across sessions.
- `integrity.py`: `LedgerIntegrityAuditor`.
- `observation/factory.py`: `ObservationFactory` / `TrustedObservationRuntime` ensuring atomic commit before receipt delivery.

### Integrations (`sclass.integrations`)
- `acp/adapter.py`: ACP normalizer converting agent events to `ActionRequest`.
- `mcp/adapter.py`: MCP tool inspection and protected resource shielding.
- Claude, Codex, Cursor, OpenCode, and Generic adapters.

### Storage & Product (`sclass.storage`, `sclass.product`)
- `migrations/`: Linear SQLite migrations (001-004) for execution identity, claim scope, and checkpoints.
- `product/`: Installation, compatibility, diagnostics, and onboarding modules.

---

## 3. Adversarial & Golden Test Suites

Implemented in `tests/adversarial/`:
1. `test_fake_receipt.py`: Rejects uncommitted agent-fabricated receipts (Attack A).
2. `test_interpreter_spoof.py`: Rejects `python -c` spoofing pytest (Attack B).
3. `test_path_hijack.py`: Detects binary substitution via executable SHA-256 (Attack C).
4. `test_wrapper_executable.py`: Unwraps shell scripts and batch wrappers (Attack D).
5. `test_receipt_mutation.py`: Blocks in-memory attribute mutation & hash recomputation (Attacks E, F).
6. `test_ledger_tampering.py`: Detects modified/deleted ledger lines (Attack G).
7. `test_workspace_mutation.py`: Detects post-verification file modifications (Attack H).
8. `test_protected_resource_escape.py`: Prevents direct or indirect writes to `.sclass/` (Attacks I, J).
9. `test_mcp_spoof.py`: Gating MCP tools targeting trust roots (Attack J).
10. `test_symlink_escape.py` & `test_junction_escape.py`: Prevents boundary escape via symlinks/junctions.
11. `test_shell_escape.py`: Prevents shell chaining in `HOST_ARGV` and blocks dangerous shell expansions.
12. `test_toctou.py`: Detects TOCTOU file modification between verification and claim.
13. `test_acp_spoof.py`: Enforces that ACP adapter produces requests, not receipts.
14. `test_claim_evidence_mismatch.py`: Enforces `EXECUTION_VERIFIED != CLAIM_VERIFIED` (Attack K).
15. `test_claim_scope_mismatch.py`: Rejects claims when test execution fails to cover claimed scope (Attack L).
16. `test_memory_poisoning.py`: Enforces that in-memory state cannot certify tasks without ledger backing.
17. `test_golden_scenarios.py`: Validates all 6 canonical golden scenarios.

---

## 4. Verification Record

- **Test Command**: `python -m pytest tests/`
- **Result**: **438 passed** in 73.12s
- **Coverage**: Execution identity, Policy Engine, Verifier Registry, Structured Parsers, Ledger Integrity, Adversarial Attacks.
