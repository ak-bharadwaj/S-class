# S-Class v6.0.1 Product Formation Gap Analysis

**Normative Authority:** `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md`  
**Date:** 2026-10-03  
**Status:** Canonical v6.0.1 Component Classification  

---

## 1. Classification Methodology

To prevent false release claims (§22.8), every product component in the repository is rigorously categorized into one of three distinct maturity tiers:

1. **IMPLEMENTED (UNVERIFIED)**: Realized in code adhering strictly to frozen canonical specifications, tested by passing test suites (252 passing tests).
2. **SCAFFOLDED**: Product boundaries, public typed interfaces, contracts, fallbacks, and boundary tests implemented and passing; full downstream evaluation remains.
3. **MISSING / FUTURE**: Identified in the long-term product envelope (§14.6) or OSS expansion map (02-OSS) but not yet built.

---

## 2. Component Inventory: Scaffolded vs Implemented vs Evaluated

| Component / Subsystem | Location | Category | Verification Artifact | Notes |
|---|---|---|---|---|
| **Canonical Type Registry** | `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `10-CONFORMANCE/spec_integrity.py` | 260 canonical types, 100% frozen hash match |
| **Event Definitions** | `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `10-CONFORMANCE/spec_integrity.py` | 56 canonical event types |
| **C1 Canonical Serialization** | `10-CONFORMANCE/sclass_kernel_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_sclass_v6_0_1_conformance.py` | Deterministic ordering and formatting |
| **Reference State Reducer** | `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_sclass_v6_0_1_conformance.py` | Pure functional state transitions |
| **SQLite WAL EventStore** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_s1_exit.py`, `test_errata_regression.py` | WAL + FULL synchronous durability |
| **CrashHarness & Prefix Oracle** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_s1_exit.py` | Real subprocess termination (`os._exit(137)`) |
| **Ed25519 KeyDirectory** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_s2_exit.py`, `test_zv1_to_zv5.py` | Digital signatures & domain separation |
| **Atomic NonceStore** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_zv1_to_zv5.py` | Single-use consumption token |
| **14-Step ExecutionGate** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_s2_exit.py`, `test_worker_harness.py` | Zero-bypass mutation enforcement |
| **Linux ExecutionBoundary** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_s2_exit.py` | Sandboxed handles & quiescence |
| **MultiEngine Verification Plane** | `src/sclass/verification/engine.py` | IMPLEMENTED (UNVERIFIED) | `test_verification_engine.py` | Pytest, Ruff, Hypothesis with Ed25519 receipts |
| **Deterministic Recovery Engine** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_s4_exit.py`, `test_zv6_to_zv10.py` | K1–K12 crash recovery matrix |
| **Autonomous Control Plane** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_s5_exit.py`, `test_golden_vertical_slice.py` | Non-FSM operating loop |
| **IntentCompiler** | `src/sclass/intelligence/compiler.py` | IMPLEMENTED (UNVERIFIED) | `test_compiler_and_world_model.py` | Dynamic intent to CanonicalObjective |
| **WorldModelBuilder & ContextCompiler** | `src/sclass/intelligence/world_model.py` | IMPLEMENTED (UNVERIFIED) | `test_compiler_and_world_model.py` | Symbol AST indexing & context packaging |
| **PatchAgentWorker** | `src/sclass/workers/harness.py` | IMPLEMENTED (UNVERIFIED) | `test_worker_harness.py` | Sandboxed mutation applicator |
| **SubprocessToolWorker** | `src/sclass/workers/harness.py` | IMPLEMENTED (UNVERIFIED) | `test_worker_harness.py` | In-boundary tool execution |
| **SClassClient (SDK)** | `src/sclass/client.py` | IMPLEMENTED (UNVERIFIED) | `test_golden_vertical_slice.py` | High-level client API |
| **S-Class CLI** | `tools/cli/sclass.py` | IMPLEMENTED (UNVERIFIED) | `test_product_boundaries.py` | Terminal subcommands (init, status, run, verify) |
| **SClassMCPServer (IDE MCP)** | `tools/mcp/sclass_mcp_server.py` | IMPLEMENTED (UNVERIFIED) | `test_mcp_server.py` | JSON-RPC stdio MCP tools |
| **SecretScanner** | `src/sclass/security/secret_scanner.py` | IMPLEMENTED (UNVERIFIED) | `test_product_boundaries.py` | Regex credential leakage detection |
| **Release Certification** | `20-RUNTIME/sclass_runtime_v6_0_1.py` | IMPLEMENTED (UNVERIFIED) | `test_release_exit.py` | `evaluate_release()` signed certificates |
| **VS Code Adapter** | `src/sclass/adapters/vscode.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | `.vscode/settings.json` and `.mcp.json` generator |
| **Cursor Adapter** | `src/sclass/adapters/cursor.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | `.cursor/hooks.json` generator |
| **Windsurf Adapter** | `src/sclass/adapters/windsurf.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | `.windsurfrules` generator |
| **Claude Code Adapter** | `src/sclass/adapters/claude_code.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | `.claude/settings.local.json` generator |
| **VS Code Extension Client** | `editors/vscode/` | SCAFFOLDED | Integration manual check | `package.json`, `extension.js`, `README.md` |
| **Schemathesis Adapter** | `src/sclass/verification/adapters/schemathesis_adapter.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | OpenAPI property testing normalization |
| **Testcontainers Adapter** | `src/sclass/verification/adapters/testcontainers_adapter.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Docker integration testing normalization |
| **Playwright Adapter** | `src/sclass/verification/adapters/playwright_adapter.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Headless browser UI testing normalization |
| **Locust Adapter** | `src/sclass/verification/adapters/locust_adapter.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Performance & load testing normalization |
| **Cosmic Ray Adapter** | `src/sclass/verification/adapters/cosmic_ray_adapter.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Mutation testing normalization |
| **SCIP Indexer** | `src/sclass/integrations/scip_indexer.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | SCIP / AST symbol indexing |
| **SQLGlot Analyzer** | `src/sclass/integrations/sqlglot_analyzer.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | SQL AST schema extraction |
| **OpenTelemetry Bridge** | `src/sclass/integrations/opentelemetry_bridge.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Secret-redacted telemetry emission |
| **ACP Bridge** | `src/sclass/integrations/acp_bridge.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Agent Client Protocol JSON-RPC framing |
| **Workspace Preflight Scanner** | `src/sclass/workspace/preflight.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Git clean, test suites, file count discovery |
| **Git Worktree Manager** | `src/sclass/workspace/worktrees.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Isolated worktrees with fallback sandboxes |
| **Hierarchical Policy Loader** | `src/sclass/config/policy_loader.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Non-weakening §14.6 policy hierarchy check |
| **Plugin Registry & Manifest** | `src/sclass/plugins/manifest.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | Plugin discovery and capability parsing |
| **SClassDoctor Diagnostic Probe** | `tools/diagnostics/doctor.py` | SCAFFOLDED (UNVERIFIED) | `test_product_boundaries.py` | 5-point non-destructive diagnostic checks |
| **Packaging & Distribution** | `pyproject.toml` | IMPLEMENTED (UNVERIFIED) | Ruff & test suite | Entrypoints: `sclass`, `sclass-mcp`, `sclass-doctor` |

---

## 3. Product Formation Gaps & Roadmap to Release Readiness

The objective of this task was **breadth of product formation**, not final release signoff. The following table identifies what remains for full release:

### Gap 1: External Network Connectors (Zone C)
- **Current State:** Subprocess workers execute local tools and patch agents.
- **Missing Work:** Connectors for remote OpenHands Agent Servers, Docker socket control, and cloud-hosted container sandboxes.

### Gap 2: Marketplace Distribution
- **Current State:** VS Code extension is scaffolded in `editors/vscode/` with JSON-RPC hooks.
- **Missing Work:** Automated compilation (`vsce package`) and publishing to Visual Studio Marketplace and Open VSX.

### Gap 3: Multi-Language Client SDKs
- **Current State:** Python SDK (`SClassClient`) in `src/sclass/client.py`.
- **Missing Work:** TypeScript / JavaScript npm package and Rust crate client wrappers over MCP or gRPC.

### Gap 4: Active Docker Integration Testing for Verifiers
- **Current State:** `TestcontainersAdapter` and `PlaywrightAdapter` gracefully handle missing local browser/Docker daemons and emit valid signed records.
- **Missing Work:** Dedicated CI pipeline running against active Docker daemon and headless Chromium.
