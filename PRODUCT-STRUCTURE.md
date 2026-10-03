# S-Class v6.0.1 Product Structure & Architecture Blueprint

**Normative Authority:** `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md`  
**Date:** 2026-10-03  
**Status:** Canonical v6.0.1 Product Layout  

---

## 1. Architectural Zones & Authority Model

Per `01-ARCHITECTURE/S-CLASS-OSS-FIRST-ARCHITECTURE.md` and `00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md`, the S-Class system operates under four strictly segregated runtime zones:

```text
                            USER / IDE / API
                                   |
                                   v
                         [ ZONE A: CANONICAL KERNEL ]
                         - Objective / Requirements
                         - Obligations / Decisions
                         - Single Authority EventStore (SQLite WAL)
                         - ReferenceReducer -> EngineeringState
                         - 14-Step ExecutionGate + NonceStore
                         - Ed25519 KeyDirectory
                                   |
                                   | (Authorized Lease + Tokens)
                                   v
                      [ ZONE B: CAPABILITY BROKER & ADAPTERS ]
                      - SClassClient (High-Level SDK)
                      - SClassMCPServer (IDE Protocol)
                      - CLI (tools/cli/sclass.py)
                      - Editor Adapters (VS Code, Cursor, Windsurf, Claude Code)
                      - Verifier Adapters (Schemathesis, Testcontainers, Playwright)
                      - OSS Bridges (SCIP, SQLGlot, OpenTelemetry, ACP)
                                   |
                                   | (Contained Dispatch)
                                   v
                         [ ZONE C: EXTERNAL RUNTIMES ]
                         - Sandboxed Subprocesses (Compilers, linters)
                         - External Agent Workers (OpenHands, mini-SWE-agent)
                         - Verifier Tool Binaries (pytest, ruff, playwright)
                                   |
                                   | (Quiescence Proof + Execution Records)
                                   v
                         [ ZONE D: EVIDENCE INGESTION ]
                         - ObservationCollector (Before/After fs diffs)
                         - MultiEngineVerificationPlane
                         - SignedEvidencePayload Receipts (Ed25519)
                         - EvidenceClosure & AcceptanceSnapshot
                                   |
                                   +---> Commits to Zone A
```

### The Single Authority Invariant
1. **Zero Competing Stores:** `SQLiteEventStore` is the **only** persistent canonical store. Projections, caches, graph indexes, and worktrees are rebuildable disposable planes.
2. **Zero Bypass Paths:** No code mutation may touch disk outside the 14-step `ExecutionGate.execute()` lifecycle.
3. **No Learned Acceptance:** LLMs and coding agents are Zone C untrusted workers. Worker completion or transcripts are never Acceptance. Acceptance requires verifiable evidence receipts in Zone D.
4. **Hierarchical Policy:** SDK Floor $\to$ Baseline Policy $\to$ Org Policy $\to$ Project Policy $\to$ Task Constraints. Lower layers may tighten but cannot weaken higher safety floors.

---

## 2. Repository Directory Blueprint

```text
S-CLASS/
├── 00-SPEC/
│   └── S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md    # Normative design authority (§0–§25)
│
├── 10-CONFORMANCE/
│   ├── c1-vectors.v6.0.1.json                  # Canonical serialization test vectors
│   ├── coverage-map.v6.0.1.json                # Complete specification coverage map
│   ├── sclass_kernel_v6_0_1.py                 # Cryptographic primitives & c1 pack
│   ├── sclass_semantics_v6_0_1.py              # 260 canonical types, 56 events, reducer
│   ├── spec_integrity.py                       # Spec-to-code AST integrity verifier
│   ├── state-machines.v6.0.1.json              # State machine transition matrices
│   └── test_sclass_v6_0_1_conformance.py       # Conformance test suite (81 tests)
│
├── 20-RUNTIME/
│   ├── sclass_runtime_v6_0_1.py                # EventStore, ExecutionGate, KeyDirectory,
│   │                                           # Boundary, RecoveryEngine, ControlPlane
│   └── test_sclass_runtime_v6_0_1.py           # Core runtime unit tests (41 tests)
│
├── src/sclass/                                 # Standard Python Package
│   ├── __init__.py                             # Package exports and version metadata
│   ├── client.py                               # SClassClient (High-Level SDK API)
│   ├── runtime.py                              # Facade delegating to 20-RUNTIME
│   ├── semantics.py                            # Facade delegating to 10-CONFORMANCE
│   │
│   ├── adapters/                               # IDE & Editor Hook Adapters
│   │   ├── __init__.py                         # Adapter exports
│   │   ├── claude_code.py                      # Claude Code CLI settings adapter
│   │   ├── cursor.py                           # Cursor IDE hooks.json adapter
│   │   ├── vscode.py                           # VS Code settings and MCP registration
│   │   └── windsurf.py                         # Windsurf / Cascade rules adapter
│   │
│   ├── config/                                 # Configuration & Policy Engine
│   │   ├── __init__.py                         # Config exports
│   │   └── policy_loader.py                    # Hierarchical policy loader (§14.6)
│   │
│   ├── integrations/                           # Open-Source (OSS) Adapters (Zone B)
│   │   ├── __init__.py                         # Integrations exports
│   │   ├── acp_bridge.py                       # Agent Client Protocol JSON-RPC
│   │   ├── opentelemetry_bridge.py             # Diagnostic telemetry (secret-redacted)
│   │   ├── scip_indexer.py                     # Source Code Intelligence Protocol indexer
│   │   └── sqlglot_analyzer.py                 # SQLGlot AST schema extraction
│   │
│   ├── intelligence/                           # Engineering Intelligence (D8)
│   │   ├── compiler.py                         # IntentCompiler (Natural language -> S-Class)
│   │   └── world_model.py                      # WorldModelBuilder & ContextCompiler
│   │
│   ├── plugins/                                # Extension & Plugin Model
│   │   ├── __init__.py                         # Plugin exports
│   │   └── manifest.py                         # PluginManifest and PluginRegistry
│   │
│   ├── security/                               # Security & Secret Scanning
│   │   ├── __init__.py                         # Security exports
│   │   └── secret_scanner.py                   # Pre-execution regex secret scanner
│   │
│   ├── verification/                           # Verification & Evidence Plane (D4)
│   │   ├── __init__.py                         # Verification exports
│   │   ├── engine.py                           # MultiEngineVerificationPlane
│   │   └── adapters/                           # Domain Verification Adapters
│   │       ├── __init__.py                     # Adapter exports
│   │       ├── cosmic_ray_adapter.py           # Cosmic Ray mutation testing adapter
│   │       ├── locust_adapter.py               # Locust performance/load testing adapter
│   │       ├── playwright_adapter.py           # Playwright UI / browser testing adapter
│   │       ├── schemathesis_adapter.py         # Schemathesis OpenAPI testing adapter
│   │       └── testcontainers_adapter.py       # Testcontainers docker integration adapter
│   │
│   ├── workers/                                # Worker Harness & Sandbox (D7)
│   │   └── harness.py                          # WorkerHarness, PatchAgentWorker, Subprocess
│   │
│   └── workspace/                              # Project & Workspace Management
│       ├── __init__.py                         # Workspace exports
│       ├── preflight.py                        # WorkspacePreflightScanner
│       └── worktrees.py                        # Git WorktreeManager with fallback
│
├── editors/                                    # Editor Extension Artifacts
│   └── vscode/                                 # VS Code Extension
│       ├── extension.js                        # VS Code extension client implementation
│       ├── package.json                        # VS Code extension manifest
│       └── README.md                           # Extension documentation
│
├── tools/                                      # Developer & Operational Tooling
│   ├── cli/                                    # Command Line Interface
│   │   └── sclass.py                           # sclass CLI entrypoint
│   ├── diagnostics/                            # System Health & Probes
│   │   ├── __init__.py                         # Diagnostics exports
│   │   └── doctor.py                           # SClassDoctor 5-point diagnostic probe
│   ├── mcp/                                    # Model Context Protocol Server
│   │   ├── __init__.py                         # MCP exports
│   │   └── sclass_mcp_server.py                # Stdio JSON-RPC 2.0 MCP server
│   ├── promote_canonical.py                    # Branch promotion utility
│   ├── run_all_s0_partitions.py                # S0 conformance partition runner
│   └── run_cr.py                               # Cosmic Ray mutation runner
│
├── tests/                                      # Test Suites (245 Passing Tests)
│   ├── adversarial/                            # Property-based Zero-Violation Tests
│   │   ├── test_zv1_to_zv5.py                  # ZV1–ZV5 security properties
│   │   └── test_zv6_to_zv10.py                 # ZV6–ZV10 lifecycle properties
│   ├── benchmarks/                             # Performance Contracts
│   │   └── test_perf_contracts.py              # Performance threshold benchmarks
│   ├── boundaries/                             # Architectural Product Boundaries
│   │   └── test_product_boundaries.py          # 23 tests proving all scaffolded boundaries
│   ├── e2e/                                    # Golden Vertical Slice
│   │   ├── conftest.py                         # Test fixtures
│   │   ├── helpers.py                          # Minimal test state builders
│   │   ├── test_golden_vertical_slice.py       # Autonomous intent -> release cycle
│   │   └── test_helpers_sanity.py              # Test helper validation
│   ├── errata/                                 # Errata Regressions
│   │   └── test_errata_regression.py           # ERR-001 through ERR-010 regressions
│   ├── intelligence/                           # Intent & Context Tests
│   │   └── test_compiler_and_world_model.py    # AST indexing & compiler tests
│   ├── interfaces/                             # Protocol Tests
│   │   └── test_mcp_server.py                  # JSON-RPC 2.0 MCP server tests
│   ├── stage_exit/                             # Survival Stage Exit Gates
│   │   ├── test_s1_exit.py                     # S1 crash recovery & replay equivalence
│   │   ├── test_s2_exit.py                     # S2 authority & execution gate
│   │   ├── test_s3_exit.py                     # S3 observation & evidence receipts
│   │   ├── test_s4_exit.py                     # S4 complete K1–K12 crash recovery matrix
│   │   ├── test_s5_exit.py                     # S5 operating loop & scheduler
│   │   └── test_release_exit.py                # Signed release certificate evaluation
│   ├── verification/                           # Verifier Engine Tests
│   │   └── test_verification_engine.py         # Multi-engine execution tests
│   └── workers/                                # Worker Harness Tests
│       └── test_worker_harness.py              # Sandbox & patch application tests
│
├── policies.json                               # Baseline policy rules configuration
├── pyproject.toml                              # Build configuration & entrypoints
├── plugin.json                                 # Core plugin manifest
├── sclass.config.json                          # Workspace configuration
└── README.md                                   # Root documentation & branch taxonomy
```

---

## 3. Product Layer Invariants

| Layer | Responsibility | Allowed Dependencies | Authority State |
|---|---|---|---|
| **Core Kernel (`10-CONFORMANCE`, `20-RUNTIME`)** | Reducer, EventStore, KeyDirectory, ExecutionGate, Budgets | Python stdlib, `cryptography` | **SOLE CANONICAL AUTHORITY** |
| **Facade SDK (`src/sclass/client.py`)** | Programmatic client connecting to control plane | Core Kernel | Pure delegator; zero independent state |
| **Interfaces (`tools/mcp/`, `tools/cli/`)** | stdio JSON-RPC, terminal subcommands | SDK, Core Kernel | Input translation only; no bypass |
| **Editor Adapters (`src/sclass/adapters/`)** | Configuration of `.vscode/`, `.cursor/`, `.claude/` | SDK, MCP | Configuration generation only |
| **Verifier Adapters (`src/sclass/verification/adapters/`)** | Normalizing external tools (pytest, playwright) | External tool subprocesses | Normalizes to `SignedEvidencePayload` |
| **OSS Integrations (`src/sclass/integrations/`)** | AST parsing, code indexing, telemetry | `ast`, optional tools | Capability only; zero authority |
| **Workspace Management (`src/sclass/workspace/`)** | Preflight environment scan, isolated worktrees | `git`, `subprocess`, `shutil` | Sandbox provisioning |
| **Security (`src/sclass/security/`)** | Secret scanning in code / diffs | `re` | Fail-closed validation |
