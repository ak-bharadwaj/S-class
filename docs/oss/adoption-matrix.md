# S-Class OSS Adoption Matrix

The S-Class OSS Adoption Rule dictates:
> **For every subsystem, before implementing it ourselves, we ask:**
> *Does a mature open-source project already solve this?*
> If **YES** → Research deeply (maturity, security, testing, maintainers, performance, license) → **ADOPT / WRAP / EXTEND**.
> If **NO** → Design ourselves (define invariant, test model, build minimal core).
> Permanently maintain an escape hatch. Never architect ourselves into permanent dependency lock-in.

---

## Master Subsystem Matrix

| Subsystem Area | Candidate Project | Primary Role | Decision | Tier | License | Escape Hatch / Replacement Path |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Protocols (Agent)** | Official ACP SDK & Schemas | Wire format, session transport, lifecycle messages | `ADOPT` | Tier 1 | Apache-2.0 / MIT | Protocol Adapter abstraction (`ACPAdapter`); switch to alternate agent RPC without modifying S-Class core |
| **Protocols (Tools)** | Official MCP SDK (2026-07-28) | Tool discovery, JSON-RPC, transport, stateless routing | `ADOPT` | Tier 1 | MIT | Capability Gateway abstraction (`MCPGateway`); wraps tool discovery behind unified S-Class action interface |
| **State Persistence** | SQLite | Local relational storage, ACID transactions, WAL mode | `ADOPT` | Tier 1 | Public Domain | Abstract `StateRepository` / `LedgerStore` interfaces; can back with DuckDB or Postgres if multi-user remote emerges |
| **Policy Engine** | Open Policy Agent (OPA) / Rego | Declarative authorization decision making (ALLOW/DENY/APPROVAL) | `ADOPT` | Tier 1 | Apache-2.0 | `PolicyEngine` interface; can swap or dual-evaluate against AWS Cedar or internal CEL policy evaluator |
| **Fine-Grained Auth** | AWS Cedar | Authorization-specific schema validation and ABAC/RBAC | `EVALUATE` | Tier 2 | Apache-2.0 | Pluggable under `PolicyEngine` interface |
| **Observability** | OpenTelemetry (OTEL) | Vendor-neutral trace, metric, and log export pipeline | `ADOPT` | Tier 1 | Apache-2.0 | `TelemetryProvider` interface; maps internal S-Class span attributes (`sclass.*`) to any collector |
| **Syntax Parsing** | Tree-sitter | Incremental, error-tolerant AST parsing across 40+ languages | `ADOPT` | Tier 1 | MIT | `SyntaxParser` interface; can fall back to language-specific parsers or LSP AST trees |
| **Semantic Intelligence** | SCIP (Source Code Intelligence Protocol) | Language-agnostic index for definitions, references, implementations | `ADOPT` | Tier 1 | Apache-2.0 | `SemanticIndexer` interface; protocol-level decouple from indexers |
| **Execution Sandboxing (Linux)** | Bubblewrap (`bwrap`) | Unprivileged user/mount/network namespace isolation | `WRAP` | Tier 2 | LGPL-2.1+ | `ExecutionBackend` abstraction; compiled sandbox config executes via `BubblewrapBackend` or host fallback |
| **Strong Container Isolation** | gVisor (`runsc`) | Application kernel user-space virtualization | `WRAP` | Tier 2 | Apache-2.0 | Pluggable backend under `ExecutionBackend` for high-risk multi-tenant or untrusted workloads |
| **Programmable CI/Execution** | Dagger | Repeatable, observable containerized pipeline execution | `EXTEND` | Tier 2 | Apache-2.0 | Pluggable runner under `ExecutionBackend` for remote/cloud hermetic verification |
| **Static Code Analysis** | Semgrep | Multi-language lightweight pattern and security scanning | `WRAP` | Tier 2 | LGPL-2.1 / Commercial | `VerificationProvider` -> `SecurityVerifier`; contributes evidence, never dictates authority |
| **Deep Semantic Analysis** | GitHub CodeQL | Queryable semantic database across languages | `WRAP` | Tier 2 | Proprietary / Free for OSS | Pluggable `VerificationProvider`; produces external security evidence receipts |
| **API Property Testing** | Schemathesis | Property-based testing for OpenAPI/GraphQL contracts | `WRAP` | Tier 2 | MIT | Pluggable `VerificationProvider` -> `APIVerifier` |
| **Secret Detection** | Gitleaks | Fast regex/entropy-based secret detection | `WRAP` | Tier 2 | MIT | Pluggable `VerificationProvider`; feature-complete verification plugin |
| **Software Bill of Materials** | Syft + CycloneDX CLI | Automated SBOM generation, diffing, and in-toto attestations | `WRAP` | Tier 2 | Apache-2.0 | Pluggable `VerificationProvider` -> `SupplyChainVerifier` |
| **Artifact Provenance & Signing** | Sigstore / Cosign | Cryptographic signing and transparency logging of binaries | `ADOPT` | Tier 1 | Apache-2.0 | `ArtifactSigner` / trust verification boundary |
| **Agent Review Architecture** | OpenCodeReview | Reference architecture for deterministic engineering + LLM split | `REFERENCE` | Tier 3 | MIT | Design reference for deterministic rule selection, MCP provider aggregation, and benchmark methodology |
| **Agent Contextual Memory** | Mem0 | Long-term memory, temporal reasoning, entity linking | `REFERENCE` | Tier 3 | Apache-2.0 | Pluggable `MemoryProvider`; provides non-authoritative context only |
| **Session Portability** | OpenMemory | Cross-harness session migration (Claude Code, Codex, OpenCode) | `REFERENCE` | Tier 3 | MIT | Research reference for session checkpoint interchange formats |
| **Full Web IDE Framework** | Eclipse Theia | Extensible browser/desktop IDE application platform | `REJECT` | N/A | EPL-2.0 | Rejected: S-Class is an IDE-agnostic trust plane, not a full IDE application |
| **JS Bundler** | esbuild | High-speed JavaScript packaging and minification | `REJECT` | N/A | MIT | Rejected: Out of domain for S-Class core verification plane |

---

## Architectural Tiers Defined

1. **Tier 1: Foundational Infrastructure (`ADOPT`)**
   - We do not write custom implementations of protocols, databases, parsers, or telemetry pipelines.
   - We directly consume the official SDKs/libraries and anchor their outputs into S-Class immutable models.
   - Core examples: ACP SDK, MCP SDK, SQLite, OpenTelemetry, Tree-sitter, SCIP.

2. **Tier 2: Pluggable Providers (`WRAP` / `EXTEND`)**
   - Independent verification or execution engines that contribute evidence or isolate execution.
   - S-Class compiles policies into their input format and normalizes their outputs into `EvidenceReceipt` records.
   - They NEVER decide final claim acceptance; S-Class verification adjudication owns the verdict.
   - Core examples: Bubblewrap, gVisor, Dagger, Semgrep, CodeQL, Schemathesis, Syft.

3. **Tier 3: Design Reference (`REFERENCE` / `ADAPT`)**
   - Proven architectural paradigms and benchmark methodologies mined from high-maturity production systems.
   - We adapt design patterns (such as deterministic file bundling + LLM reflection, or benchmark suites) without pulling heavy direct dependencies.
   - Core examples: OpenCodeReview, Mem0, OpenMemory.

4. **Rejected Candidates (`REJECT`)**
   - Highly rated or battle-tested repositories whose architectural scope contradicts S-Class minimalism, IDE neutrality, or security invariants.
   - Core examples: Eclipse Theia (bloated IDE framework), esbuild (irrelevant bundling scope).
