# S-Class v6.0.1 Product Formation Matrix

**Normative Authority:** `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md`  
**Companion Authorities:** `01-ARCHITECTURE/S-CLASS-OSS-FIRST-ARCHITECTURE.md`, `02-OSS/S-CLASS-OSS-ADOPTION-AND-CAPABILITY-MAP.md`, `03-RUNTIME/S-CLASS-WORKER-RUNTIME-AND-HARNESS-CONTRACT.md`, `04-INTELLIGENCE/S-CLASS-ENGINEERING-INTELLIGENCE-SPEC.md`, `05-VERIFICATION/S-CLASS-VERIFICATION-AND-EVIDENCE-SPEC.md`, `06-VALIDATION/S-CLASS-VALIDATION-AND-RELEASE-GATES.md`  
**Date:** 2026-10-03  
**Integrity State:** Canonical v6.0.1 (Single Authority Architecture)

---

## 1. Executive Summary

This matrix represents the authoritative product formation audit for S-Class v6.0.1. Each of the 24 required product capabilities is cross-referenced against the normative frozen specification, its architectural responsibility domain (D0–D8), current codebase implementation, file paths, dependencies, test verification, status, and precise missing work.

Status Legend:
- **IMPLEMENTED & VERIFIED**: Fully written, conforming to canonical contracts, and verified by passing test suites.
- **SCAFFOLDED**: Public contracts, boundary shims, fallbacks, and typed adapters implemented and verified against boundary contracts; downstream production qualification remains.
- **PARTIAL / IN PROGRESS**: Core runtime present, secondary utilities or external network adapters pending.

---

## 2. Requirement-to-Product-Component Matrix (24 Capabilities)

### 1. S0–S5 Core
- **Design Requirement:** §0.2, §0.4, §22.2. Six sequential survival stages: S0 Foundation (c1, digests, EffectScope), S1 Canonical Kernel (events, reducer, commit), S2 Authority & Execution (policy, leases, nonces, gate), S3 Observation & Evidence (target snapshots, verifier plane, receipts, freshness), S4 Recovery & Continuity (reconciliation, repair, K1–K12 crash consistency), S5 Operating Loop (D8 scheduler, autonomous cycle, release evaluation).
- **Intended Responsibility:** D0 Contracts, D1 Domain Kernel, D2 History, D3 Policy, D4 Evidence, D5 Authorization, D6 Execution. Provide the single-truth semantic state engine.
- **Current Implementation:** Pure functional reducer `ReferenceReducer`, 260 canonical types, 56 event types, `SClassControlPlane`, `ExecutionGate`.
- **File/Module:** `10-CONFORMANCE/sclass_semantics_v6_0_1.py`, `10-CONFORMANCE/sclass_kernel_v6_0_1.py`, `20-RUNTIME/sclass_runtime_v6_0_1.py`, `src/sclass/semantics.py`, `src/sclass/runtime.py`.
- **Dependency:** Python 3.10+ stdlib, `cryptography`.
- **Tests:** `10-CONFORMANCE/test_sclass_v6_0_1_conformance.py` (81 passed), `tests/stage_exit/test_s1_exit.py` through `test_s5_exit.py`, `tests/stage_exit/test_release_exit.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** None for core survival stages. WP10 production qualification at enterprise scale.

---

### 2. Truth / Durability
- **Design Requirement:** §0.7, §12. `EventStore -> StateReducer -> EngineeringState` is the sole canonical state path. Atomic append, CAS protection against head divergence, SHA-256 hash chain continuity, replay equivalence (`canonical_state_after_commit = ReferenceReducer(previous, committed) = replay(genesis, history) = replay(checkpoint, suffix)`), real OS crash consistency.
- **Intended Responsibility:** D2 History. Prevent split-brain, uncommitted visibility, and data loss across process crashes or power interruptions.
- **Current Implementation:** `SQLiteEventStore` with WAL mode and `PRAGMA synchronous = FULL; PRAGMA foreign_keys = ON;`, `ReferenceReducer`, `CrashHarness` covering real process termination (`os._exit(137)`) across K1–K6.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`, `10-CONFORMANCE/sclass_semantics_v6_0_1.py`.
- **Dependency:** `sqlite3`, stdlib `hashlib`.
- **Tests:** `tests/stage_exit/test_s1_exit.py` (parameterized real-process crash tests), `tests/errata/test_errata_regression.py` (ERR-001 through ERR-010).
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Multi-region read replica streaming projections (non-survival, Zone C).

---

### 3. Authority / Admission
- **Design Requirement:** §4, §8, §0.6. Zero-bypass execution authority. Strict default-deny ordering: `fs -> process -> network -> env -> credential -> external -> budget`. Single-use atomic NonceStore, AuthorityEnvelope, ApprovalRecord/Set, StateBinding revalidation, AuthorizationLease verification.
- **Intended Responsibility:** D3 Policy, D5 Authorization. Ensure no action executes without cryptographic provenance, active budget, and unexpired lease.
- **Current Implementation:** `SQLiteKeyDirectory`, `SQLiteNonceStore`, `StateBinding`, `ExecutionGate` pre-dispatch validation.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`, `10-CONFORMANCE/sclass_semantics_v6_0_1.py`.
- **Dependency:** `cryptography.hazmat.primitives.asymmetric.ed25519`.
- **Tests:** `tests/adversarial/test_zv1_to_zv5.py`, `tests/stage_exit/test_s2_exit.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Hardware Security Module (HSM) / KMS key providers for enterprise cloud deployments.

---

### 4. Execution / Runtime
- **Design Requirement:** §8, §9, §0.5A. The complete 14-step `ExecutionGate.execute()` lifecycle. Descriptor-relative mutations (`WorkspaceSnapshotHandle`), real OS execution boundary (`LinuxExecutionBoundary` with `openat2(RESOLVE_BENEATH)` / cgroup v2; Windows development shim), quiescence proof requirement before capture_after, zero bypass.
- **Intended Responsibility:** D6 Execution. Confine mutations strictly to authorized paths; fail closed on path escapes or lingering processes.
- **Current Implementation:** `ExecutionGate`, `LinuxExecutionBoundary`, `LocalWorkspaceSnapshotHandle`, `PatchAgentWorker`.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`, `src/sclass/workers/harness.py`.
- **Dependency:** OS primitives (`openat2` on Linux, Win32 handle resolution on Windows), `subprocess`.
- **Tests:** `tests/adversarial/test_zv1_to_zv5.py`, `tests/stage_exit/test_s2_exit.py`, `tests/workers/test_worker_harness.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Linux production cgroup v2 controller daemon integration for multi-tenant microVMs.

---

### 5. Observation / Evidence / Verification
- **Design Requirement:** §11, §13, 05-VERIFICATION spec. `ObservationCollector`, before/after filesystem diff capture, process metrics, quiescence proof, `SignedEvidencePayload` with Ed25519 receipts, 9-dimension freshness tracking (`EVIDENCE_FRESHNESS_DIMENSIONS`), cascading evidence invalidation, `EvidenceClosure`, `AcceptanceSnapshot`.
- **Intended Responsibility:** D4 Evidence. Provide tamper-evident, reproducible proof that obligations are satisfied.
- **Current Implementation:** `ObservationCollector`, `EvidenceStore`, `MultiEngineVerificationPlane` coordinating pytest, ruff, and hypothesis verifiers with cryptographic receipt generation.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`, `src/sclass/verification/engine.py`.
- **Dependency:** `pytest`, `ruff`, `hypothesis`, `cryptography`.
- **Tests:** `tests/stage_exit/test_s3_exit.py`, `tests/verification/test_verification_engine.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Remote distributed verifier workers with signed attestation certificates.

---

### 6. Recovery / Continuity
- **Design Requirement:** §13, §14. Complete K1–K12 crash recovery matrix. `DeterministicRecoveryEngine`, `ExternalEffectReconciler` for side-effect compensation and `IN_DOUBT` state handling, `HandoffCompiler` for seamless worker replacement with zero lease/session leakage and preserved cumulative budget lineage.
- **Intended Responsibility:** D2 History, D6 Execution. Recover cleanly after any crash, guaranteeing atomic prefix consistency.
- **Current Implementation:** `DeterministicRecoveryEngine`, `ExternalEffectReconciler`, `HandoffCompiler`, `CrashHarness`.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`.
- **Dependency:** `sqlite3`, `subprocess`.
- **Tests:** `tests/stage_exit/test_s4_exit.py` (full K1–K12 automated kill matrix), `tests/adversarial/test_zv6_to_zv10.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Distributed consensus leader election for multi-node deployments.

---

### 7. Completion / Operating Loop
- **Design Requirement:** §1, §7, §15. Autonomous Dev Team loop: objective creation -> requirement decomposition -> obligation planning -> work node dispatch -> mutation -> verification -> acceptance evaluation -> release verdict. Deterministic scheduler `SchedulerPolicy.next_actions()`.
- **Intended Responsibility:** D8 Intelligence/Planning. Drive iterative progress toward objective completion without human intervention.
- **Current Implementation:** `SClassControlPlane.run_until_quiescent()`, `SchedulerPolicy`, `SClassClient.run_autonomous_cycle()`.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`, `src/sclass/client.py`.
- **Dependency:** None outside runtime and client.
- **Tests:** `tests/stage_exit/test_s5_exit.py`, `tests/e2e/test_golden_vertical_slice.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Multi-objective concurrent dependency scheduling across independent projects.

---

### 8. Intelligence / Intent / World Model
- **Design Requirement:** §1, §10, 04-INTELLIGENCE spec. `IntentCompiler` translating natural language into canonical `CanonicalObjective`, `ObligationGraph`, and `VerificationPlan`. `EngineeringWorldModelBuilder` indexing workspace AST symbols, classes, functions, and import graphs into `TargetSnapshot`. `ContextCompiler` compiling bounded `ContextPackage` with token-budgeted repo maps.
- **Intended Responsibility:** D8 Intelligence/Planning. Construct high-fidelity context packages and obligations to guide code generation without mutating canonical state.
- **Current Implementation:** Dynamic two-pass `IntentCompiler` with deterministic fallback, AST `EngineeringWorldModelBuilder`, and `ContextCompiler`.
- **File/Module:** `src/sclass/intelligence/compiler.py`, `src/sclass/intelligence/world_model.py`.
- **Dependency:** Python stdlib `ast`.
- **Tests:** `tests/intelligence/test_compiler_and_world_model.py` (6 tests passed).
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** LLM provider streaming API connectors (OpenAI, Anthropic, Gemini) for neural intent compilation pass.

---

### 9. Worker / Agent Model
- **Design Requirement:** §10, 03-RUNTIME spec. `WorkerHarness` abstract base class, `WorkerKind`, `PatchAgentWorker` applying verified mutations under the 14-step `ExecutionGate`, `SubprocessToolWorker` executing compilers/tools within boundary. External agent adapters (OpenHands, mini-SWE-agent, Goose) strictly as untrusted execution participants (Zone C) bounded by `ExecutionBoundary`.
- **Intended Responsibility:** D7 Worker Runtime. Execute discrete implementation tasks within tight containment.
- **Current Implementation:** `WorkerHarness`, `PatchAgentWorker` (path traversal hardened, sandbox handle relative), `SubprocessToolWorker`.
- **File/Module:** `src/sclass/workers/harness.py`.
- **Dependency:** `subprocess`, `os`, `pathlib`.
- **Tests:** `tests/workers/test_worker_harness.py` (7 tests passed).
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** External OpenHands Dockerized Agent Server network connector.

---

### 10. SDK
- **Design Requirement:** §16, §14.6. High-level programmatic API for embedding S-Class in Python environments or automation pipelines. Submits typed `Command` objects to `SClassControlPlane` with zero independent state or authority. Exposes workspace initialization, state querying, intent submission, autonomous cycles, verification, release evaluation, and audit.
- **Intended Responsibility:** Universal Client Surface. Provide type-safe programmatic access to S-Class control plane.
- **Current Implementation:** `SClassClient` with `connect()`, `compile_and_submit_intent()`, `run_autonomous_cycle()`, `verify_obligations()`, `evaluate_and_release()`, `verify_chain()`.
- **File/Module:** `src/sclass/client.py`.
- **Dependency:** `sclass_runtime_v6_0_1`, `sclass_semantics_v6_0_1`.
- **Tests:** `tests/e2e/test_golden_vertical_slice.py`, `tests/interfaces/test_mcp_server.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** TypeScript / JavaScript and Rust language SDK client bindings.

---

### 11. CLI
- **Design Requirement:** §16. Thin command-line wrapper around `SClassClient` / `SClassControlPlane`. Subcommands: `init`, `status`, `audit`, `run "<intent>"`, `verify`, `release`. Zero independent state.
- **Intended Responsibility:** Operator Surface. Local terminal interface for invoking control plane commands.
- **Current Implementation:** `tools/cli/sclass.py` with full subcommands delegating to `SClassClient`. Console script entrypoint registered in `pyproject.toml`.
- **File/Module:** `tools/cli/sclass.py`.
- **Dependency:** Python stdlib `argparse`.
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestCLIBoundary::test_cli_help`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Interactive TUI (`textual` or `curses`) dashboard for live streaming event logs.

---

### 12. MCP (Model Context Protocol)
- **Design Requirement:** §14.6, §16, 06-IDE spec. Model Context Protocol server exposing S-Class capabilities over standard stdio JSON-RPC 2.0. Tools: `sclass_guide_task`, `sclass_validate_patch`, `sclass_get_status`. Strict sandbox and gate enforcement.
- **Intended Responsibility:** IDE Agent Guidance Surface. Allow host IDE models (Claude, Cursor, Copilot) to discover obligations and validate patches without raw disk mutation bypass.
- **Current Implementation:** `SClassMCPServer` with JSON-RPC 2.0 stdio loop, tool dispatch, error code formatting, and strict execution gating.
- **File/Module:** `tools/mcp/sclass_mcp_server.py`.
- **Dependency:** Python stdlib `json`, `sys`.
- **Tests:** `tests/interfaces/test_mcp_server.py` (9 tests passed).
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Streamable HTTP / Server-Sent Events (SSE) remote transport for web-hosted IDEs.

---

### 13. IDE Integration
- **Design Requirement:** §14.6, 06-IDE spec. Direct integration with editors/IDEs: VS Code extension, Cursor hooks, Windsurf hooks, Claude Code settings, Antigravity integration. Must route IDE agent tool/prompt actions through MCP or SClassClient without creating duplicate state or alternate truth paths.
- **Intended Responsibility:** Developer Experience & IDE Boundary. Seamlessly bind popular developer environments to S-Class governance.
- **Current Implementation:** `VSCodeAdapter`, `CursorAdapter`, `WindsurfAdapter`, `ClaudeCodeAdapter`, and complete VS Code extension manifest and client.
- **File/Module:** `src/sclass/adapters/vscode.py`, `src/sclass/adapters/cursor.py`, `src/sclass/adapters/windsurf.py`, `src/sclass/adapters/claude_code.py`, `editors/vscode/package.json`, `editors/vscode/extension.js`.
- **Dependency:** None (generates standard editor JSON manifests and JS extension).
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestEditorAdapters`.
- **Status:** SCAFFOLDED & VERIFIED.
- **Missing Work:** Publish to Visual Studio Marketplace / Open VSX Registry.

---

### 14. Verification Providers
- **Design Requirement:** §11, 05-VERIFICATION spec, 02-OSS map. Extended verification engines beyond standard pytest/ruff:
  - Schemathesis (OpenAPI/REST API contract verification)
  - Testcontainers (Docker-backed database & services integration testing)
  - Playwright (End-to-end browser & UI verification)
  - Locust (Load/performance profiling & SLA verification)
  - Cosmic Ray (Mutation testing & test suite robustness verification)
  All normalizing output into canonical `SignedEvidencePayload`.
- **Intended Responsibility:** D4 Evidence. Provide specialized domain verification while preserving single evidence digest format.
- **Current Implementation:** `SchemathesisAdapter`, `TestcontainersAdapter`, `PlaywrightAdapter`, `LocustAdapter`, `CosmicRayAdapter` subclassing `VerifierEngine` and returning `VerifierExecutionRecord` with SHA-256 digests.
- **File/Module:** `src/sclass/verification/adapters/schemathesis_adapter.py`, `src/sclass/verification/adapters/testcontainers_adapter.py`, `src/sclass/verification/adapters/playwright_adapter.py`, `src/sclass/verification/adapters/locust_adapter.py`, `src/sclass/verification/adapters/cosmic_ray_adapter.py`.
- **Dependency:** `subprocess`, respective CLI binaries when installed in environment.
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestVerificationAdapters`.
- **Status:** SCAFFOLDED & VERIFIED.
- **Missing Work:** Live Docker daemon integration test fixtures in CI for testcontainers.

---

### 15. OSS Adapters
- **Design Requirement:** §0.5A, 01-ARCHITECTURE, 02-OSS map. Clean boundary adapters for external OSS tools:
  - SCIP (Source Code Intelligence Protocol code graph indexing)
  - SQLGlot (SQL parsing, schema extraction, query transpile/analysis)
  - OpenTelemetry (Diagnostics & trace emission without secrets)
  - Agent Client Protocol (ACP JSON-RPC interop)
  All strictly Zone B/C without canonical authority.
- **Intended Responsibility:** Zone B Capability Broker. Absorb external open-source capabilities without surrendering semantic authority.
- **Current Implementation:** `SCIPIndexer`, `SQLGlotAnalyzer`, `OpenTelemetryBridge`, `ACPBridge`.
- **File/Module:** `src/sclass/integrations/scip_indexer.py`, `src/sclass/integrations/sqlglot_analyzer.py`, `src/sclass/integrations/opentelemetry_bridge.py`, `src/sclass/integrations/acp_bridge.py`.
- **Dependency:** Stdlib `ast`, optional `sqlglot`, optional `scip`.
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestOSSIntegrations`.
- **Status:** SCAFFOLDED & VERIFIED.
- **Missing Work:** Remote SCIP index server gRPC client for large multi-million LOC codebases.

---

### 16. Configuration / Policy
- **Design Requirement:** §4, §14.6. Strict 5-tier configuration hierarchy (`SDK floor -> baseline -> org -> project -> task`). Parsing `sclass.config.json` and `policies.json`. Mandatory policy relation rules: lower layers can tighten but cannot loosen higher-tier controls without signed cryptographic approvals.
- **Intended Responsibility:** D3 Policy. Enforce safety floors across repositories and teams.
- **Current Implementation:** `ConfigPolicyLoader` enforcing `PolicyHierarchyViolation` whenever project policies attempt to disable gating or quiescence, `sclass.config.json`, `policies.json`.
- **File/Module:** `src/sclass/config/policy_loader.py`, `sclass.config.json`, `policies.json`.
- **Dependency:** Stdlib `json`, `dataclasses`.
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestConfigAndPolicyHierarchy`.
- **Status:** SCAFFOLDED & VERIFIED.
- **Missing Work:** Multi-tenant remote policy service with signed policy updates.

---

### 17. Project / Workspace Management
- **Design Requirement:** §9, §14.6. Workspace preflight discovery scanner (extracting git status, db schemas, routes, test suites), Git worktree isolation manager (`WorktreeManager` provisioning isolated branches/worktrees for subagents with dependency linking), descriptor-relative workspace handles.
- **Intended Responsibility:** D6 Execution / Workspace. Isolate worker changes and detect repo topology without race conditions.
- **Current Implementation:** `WorkspacePreflightScanner` returning structured `PreflightReport`, `WorktreeManager` managing isolated `agent/{task_id}` worktrees with junction/symlink caching and directory fallback.
- **File/Module:** `src/sclass/workspace/preflight.py`, `src/sclass/workspace/worktrees.py`.
- **Dependency:** `git`, `subprocess`, `shutil`.
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestWorkspaceManagement`.
- **Status:** SCAFFOLDED & VERIFIED.
- **Missing Work:** OverlayFS / Btrfs snapshotting integration for zero-copy Linux worktree isolation.

---

### 18. Persistence
- **Design Requirement:** §12, §14.6. SQLiteEventStore WAL + FULL synchronous durability, migration framework (`PRAGMA user_version`), corruption detection, checkpoint snapshots, restore to candidate state with integrity verification before promotion.
- **Intended Responsibility:** D2 History. Guarantee uncorrupted, durable long-term storage of all canonical transitions.
- **Current Implementation:** `SQLiteEventStore` with WAL mode, atomic CAS appends, checkpoint creation and restore, hash chain verification.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`.
- **Dependency:** `sqlite3`.
- **Tests:** `tests/stage_exit/test_s1_exit.py`, `tests/errata/test_errata_regression.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Automated WAL auto-checkpoint tuner and SQLite page backup replication.

---

### 19. Observability / Diagnostics
- **Design Requirement:** §14.6, 01-ARCHITECTURE. Bounded, redacted telemetry, health checks, diagnostic doctor tool (`sclass doctor`) inspecting event store integrity, Ed25519 key directory health, workspace clean status, verifier availability, and reporting actionable diagnostics without leaking secret bytes.
- **Intended Responsibility:** Diagnostics & Support. Allow operators to audit environment health and identify configuration failures.
- **Current Implementation:** `SClassDoctor` performing 5 discrete probes (`sqlite_pragmas`, `cryptography_ed25519`, `event_store_hash_chain`, `verification_toolchain`, `workspace_preflight`), returning structured JSON report. CLI entrypoint registered in `pyproject.toml`.
- **File/Module:** `tools/diagnostics/doctor.py`.
- **Dependency:** `sqlite3`, `cryptography`, `subprocess`.
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestDiagnosticsDoctor`.
- **Status:** SCAFFOLDED & VERIFIED.
- **Missing Work:** Automated remediation actions (e.g. `--repair` flag) for missing tools or corrupt indexes.

---

### 20. Extension / Plugin Model
- **Design Requirement:** §14.6, 01-ARCHITECTURE. Plugin manifest (`plugin.json`), capability declarations, effect scopes, skill discovery. Plugins declare capabilities but activation does not grant authority; all operations remain subject to D3/D5 authorization and ExecutionGate.
- **Intended Responsibility:** Extensibility Boundary. Allow third-party tools and custom skills to register capabilities cleanly.
- **Current Implementation:** `PluginManifest`, `PluginRegistry` discovering and validating plugins from `plugin.json` or subdirectories, root `plugin.json`.
- **File/Module:** `src/sclass/plugins/manifest.py`, `plugin.json`.
- **Dependency:** Stdlib `json`, `dataclasses`.
- **Tests:** `tests/boundaries/test_product_boundaries.py::TestPluginModel`.
- **Status:** SCAFFOLDED & VERIFIED.
- **Missing Work:** Signed plugin bundle verification (verifying author signature before plugin loading).

---

### 21. Security / Trust / Key Management
- **Design Requirement:** §0.3, §8, §14.6. `SQLiteKeyDirectory` Ed25519 signing/verification, key rotation (`ROTATED_OUT`), revocation, expiry check, secret scanning in workspace changes (regex for API keys/tokens), path traversal containment, default-deny effect scopes.
- **Intended Responsibility:** D5 Authorization / Security Perimeter. Ensure cryptographic provenance and protect against credential leakage or path escapes.
- **Current Implementation:** Real Ed25519 cryptographic key directory in runtime, `SecretScanner` with regex patterns for private keys, AWS tokens, GitHub tokens, API keys, and high-entropy secrets.
- **File/Module:** `20-RUNTIME/sclass_runtime_v6_0_1.py`, `src/sclass/security/secret_scanner.py`.
- **Dependency:** `cryptography`, stdlib `re`.
- **Tests:** `tests/adversarial/test_zv1_to_zv5.py`, `tests/boundaries/test_product_boundaries.py::TestSecurityBoundaries`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Dynamic secret masking in subprocess output streams before stdout/stderr ingestion.

---

### 22. Packaging / Distribution
- **Design Requirement:** §14.6, 00-START-HERE. Modern `pyproject.toml` configuration with proper metadata, build backend (setuptools), console script entrypoints (`sclass`, `sclass-mcp`, `sclass-doctor`), dependency specifications, and license declarations.
- **Intended Responsibility:** Packaging & Release. Standardized Python wheel and sdist distribution.
- **Current Implementation:** `pyproject.toml` with console scripts, classifiers, dependencies, optional dev dependencies, and pytest configuration.
- **File/Module:** `pyproject.toml`.
- **Dependency:** `setuptools>=61.0`, `wheel`.
- **Tests:** Package installation and entrypoint invocation tests.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Standalone binary compilation via PyInstaller or Nuitka for zero-Python host environments.

---

### 23. Documentation
- **Design Requirement:** §0, 00-START-HERE, README.md, specification documentation, branch taxonomy, architecture map.
- **Intended Responsibility:** Architecture & Developer Education. Provide comprehensive, unambiguous reference documentation.
- **Current Implementation:** `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md`, companion specifications in `scratch/zip_extract/`, top-level `README.md` with branch taxonomy and repository map, `PRODUCT-FORMATION-MATRIX.md`, `PRODUCT-STRUCTURE.md`, `PRODUCT-FORMATION-GAPS.md`.
- **File/Module:** `README.md`, `00-SPEC/`, `PRODUCT-FORMATION-MATRIX.md`, `PRODUCT-STRUCTURE.md`, `PRODUCT-FORMATION-GAPS.md`.
- **Dependency:** Markdown.
- **Tests:** `10-CONFORMANCE/spec_integrity.py` (`SPEC_INTEGRITY_OK registry=260 events=56`).
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Interactive documentation website (e.g. MkDocs Material or Starlight).

---

### 24. CI / Release / Deployment
- **Design Requirement:** §0.2, §15, §22. Stage-gated GitHub Actions CI workflows enforcing lint, spec integrity, conformance, runtime, stage exit tests, adversarial ZV1–ZV10, and signed release evaluation (`evaluate_release()`).
- **Intended Responsibility:** Quality Assurance & Automated Release Gate. Block any regression or invalid commit from entering canonical branches.
- **Current Implementation:** GitHub workflows in `.github/workflows/`, executable `evaluate_release()` in `20-RUNTIME/sclass_runtime_v6_0_1.py`.
- **File/Module:** `.github/workflows/`, `20-RUNTIME/sclass_runtime_v6_0_1.py`.
- **Dependency:** GitHub Actions runner.
- **Tests:** `tests/stage_exit/test_release_exit.py`.
- **Status:** IMPLEMENTED & VERIFIED.
- **Missing Work:** Automated PyPI / GitHub Releases deployment pipeline with cosign release provenance.
