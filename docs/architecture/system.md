# S-Class System Architecture

## 1. Executive Summary & Product Thesis
S-Class is an open-source trust infrastructure layer for AI-assisted software development.
Developers bring their chosen IDE (VS Code, Cursor, Zed), coding agents (Claude Code, OpenAI Codex, OpenCode), and local tools.
S-Class sits underneath as the authoritative control plane:
- It **authorizes** what agents may do via declarative policy.
- It **executes** actions in controlled, observable environments.
- It **independently observes** process lifecycles via OS primitives, computing cryptographic execution identities.
- It **gathers multi-source evidence** and **adjudicates verification claims**.
- It maintains an **immutable cryptographic ledger** and **persisted state store** (SQLite).
- It enables **zero-drift cross-agent continuity** via verified handoff packages.

---

## 2. High-Level Architecture Diagram

```
                                 DEVELOPER WORKSPACE
         ┌──────────────────────────────────────────────────────────────────┐
         │                                                                  │
         │   IDE / Client (VS Code / Cursor / Zed / CLI)                    │
         │                        │                                         │
         │   Coding Agent(s) (Claude Code / Codex / OpenCode / ACP Agent)   │
         │                        │                                         │
         └────────────────────────┼─────────────────────────────────────────┘
                                  │ JSON-RPC 2.0 / stdio / HTTP
                                  ▼
 ══════════════════════════════════════════════════════════════════════════════════
                            S-CLASS CONTROL PLANE
 ══════════════════════════════════════════════════════════════════════════════════
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 1. PROTOCOL ADAPTER LAYER                                              │
   │    ├── ACP Adapter (Official v1 Protocol, Lifecycle, Gateways)         │
   │    └── MCP Adapter (Official 2026-07-28 Spec, Headers, Routing)        │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       ▼ Normalizes to
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 2. UNIFIED ACTION & CAPABILITY PLANE                                   │
   │    ├── ActionRequest: (actor, capability, target, params, workspace)   │
   │    └── CapabilityRegistry: (terminal.execute, fs.read, fs.write, etc.) │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 3. DECLARATIVE POLICY ENGINE (OPA / Rego & Cedar)                      │
   │    ├── Canonical Policy Input Compilation                              │
   │    └── Policy Evaluation -> ALLOW | DENY | REQUIRE_APPROVAL            │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       ▼ (If Allowed)
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 4. EXECUTION & ISOLATION PLANE                                         │
   │    ├── HostExecutionBackend (Native direct execution)                  │
   │    ├── BubblewrapExecutionBackend (Linux unprivileged sandbox)         │
   │    └── gVisor / Dagger Backends (High-isolation & hermetic CI)         │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 5. INDEPENDENT OBSERVATION ENGINE                                      │
   │    ├── ExecutionIdentity (PID, binary hash, start_time, argv, cwd)     │
   │    ├── Process Ancestry & Wrapper Disambiguation                       │
   │    └── ObservedReceipt Sealing (stdout/stderr hashes, exit code)        │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 6. MULTI-PROVIDER VERIFICATION & ADJUDICATION                          │
   │    ├── TestVerifier (pytest, Jest, Vitest)                             │
   │    ├── StaticAnalysisVerifier (Semgrep, CodeQL)                        │
   │    ├── ContractVerifier (Schemathesis)                                 │
   │    ├── SupplyChainVerifier (Syft, CycloneDX)                           │
   │    └── Workspace Fingerprint Invalidation Engine                       │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 7. AUTHORITATIVE PERSISTENCE & RECOVERY (SQLite + Ledger)              │
   │    ├── SQLite State Repository (Projects, Tasks, Claims, Sessions)     │
   │    ├── Append-Only Local Ledger (SHA-256 Hash Chain of Receipts)       │
   │    └── Crash Recovery & State Reconciliation Engine                    │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ 8. CROSS-AGENT CONTINUITY & HANDOFF                                    │
   │    ├── HandoffAssembler: Assembles verified facts, not chat memory     │
   │    └── Zero-Drift Resumption for Downstream Agents                     │
   └────────────────────────────────────────────────────────────────────────┘
 ══════════════════════════════════════════════════════════════════════════════════
```

---

## 3. Core Subsystems

### 3.1 Trust Kernel
The Trust Kernel enforces the core epistemic invariants:
- Agent claims and receipts are strictly untrusted.
- Observations originate exclusively from S-Class execution monitoring.
- Binaries are validated against an explicit `VerifierTrustRegistry` (preventing PATH-hijacking or shell wrapper spoofing).
- Unknown binaries or ambiguous targets fail closed.

### 3.2 Action & Capability Plane
Every request from any source (ACP, MCP, CLI, agent) is normalized into an immutable `ActionRequest`:
```python
@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    actor: str
    capability: str
    target: str
    parameters: Dict[str, Any]
    workspace: str
    session_id: Optional[str]
    context: Dict[str, Any]
```

### 3.3 State Machine Lifecycle
A task proceeds through formal state transitions:
```
CLAIMED -> EVIDENCE_REQUIRED -> OBSERVED -> VERIFYING -> ACCEPTED / REJECTED / INVALIDATED
```
Any workspace modification after verification invalidates dependent receipts, immediately transitioning verified tasks to `INVALIDATED`.

### 3.4 Open-Source Infrastructure Foundation
S-Class reuses battle-tested open-source components for foundational mechanics:
- **ACP/MCP**: Official SDKs for wire compatibility.
- **SQLite**: 100% branch-tested storage engine.
- **OPA**: CNCF graduated policy evaluation.
- **OpenTelemetry**: Industry standard observability export.
- **Tree-sitter & SCIP**: AST parsing and semantic symbol resolution.
- **Bubblewrap**: Linux unprivileged containerization.
- **Semgrep & Syft**: Pluggable security and supply-chain verifiers.
