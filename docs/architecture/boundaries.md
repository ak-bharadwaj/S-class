# S-Class Architectural Boundaries: The 80/20 Adoption Rule

## 1. Core Architectural Principle
S-Class adopts the **80/20 OSS rule**:
- **~80% Reused Battle-Tested Infrastructure**: Wire protocols, state persistence, AST parsing, semantic protocols, policy evaluation engines, telemetry pipelines, sandbox primitives, and static analysis tools.
- **~20% Unique S-Class Trust Kernel**: Action authority, execution identity, independent observation, evidence provenance, claim adjudication, authoritative project truth, workspace invalidation, and cross-agent continuity.

We never spend years reproducing infrastructure that mature open-source projects have already spent decades perfecting.

---

## 2. Boundary Division Table

| Subsystem Dimension | What S-Class Borrows (~80% Reused) | What S-Class Strictly Owns (~20% Proprietary Core) |
| :--- | :--- | :--- |
| **Protocols (Agent / Tool)** | ACP v1 schemas, MCP 2026-07-28 JSON-RPC transport, SDK serialization, connection lifecycle | Capability permission mapping, actor identity binding, conversion to immutable `ActionRequest` |
| **Policy & Authorization** | OPA Rego evaluation engine, Cedar authorization schema validation | Canonical policy context generation, enforcement gate, interactive approval UX, fail-closed defaults |
| **Process Execution & Sandboxing**| OS subprocesses, Linux Bubblewrap namespaces, gVisor syscall filters | Policy-to-sandbox compilation, process lifecycle control, timeout enforcement, environment sanitization |
| **Observation & Identity** | OS kernel APIs (`/proc`, `CreateProcess`, Win32 API), SHA-256 primitives | `ExecutionIdentity` computation, parent process chain inspection, wrapper detection, immutable receipt sealing |
| **State Persistence** | SQLite B-tree storage, WAL mode, ACID transactions, relational indexing | Task and claim state machines, transition authority, receipt dependency graphs, recovery reconciliation |
| **Cryptographic Audit** | Standard SHA-256 hashing, HMAC, SQLite blob storage | Append-only ledger hash chain, state anchoring, tamper detection, proof verification |
| **Code Syntax & Structure** | Tree-sitter AST/CST generation, multi-language grammars | Mutation range calculation, symbol diff extraction, syntax invalidation triggers |
| **Semantic Intelligence** | SCIP protocol buffers, language indexers (Go, TS, Python) | Dependency impact matrix compilation, deterministic verification planning |
| **Verification & Evidence** | Test runners (pytest, Jest), analyzers (Semgrep, CodeQL, Schemathesis, Syft) | Multi-verifier confidence adjudication, claim verdict logic (`ACCEPTED`/`REJECTED`), workspace fingerprint invalidation |
| **Observability** | OpenTelemetry SDK, OTLP protocols, W3C trace context, Collector | S-Class semantic domain attributes (`sclass.*`), operational span lifecycle |
| **Agent Continuity & Memory** | Non-authoritative context embeddings (Mem0, OpenMemory references) | `HandoffPackage` assembly from verified SQLite truth; zero-drift context restoration |

---

## 3. Strict Boundary Rules

### Rule 1: Protocol adapters are thin and non-authoritative.
Protocol adapters (ACP, MCP, Claude, Codex, Cursor) MUST NOT contain authorization rules, verification logic, or state persistence. Their sole responsibility is parsing external messages into `ActionRequest` models and translating S-Class results into external protocol responses.

### Rule 2: Isolation primitives are not security policies.
Sandboxes (Bubblewrap, gVisor, Docker) provide execution isolation primitives. They do not possess contextual knowledge of developer projects, tasks, or permissions. S-Class owns the security policy and compiles policy constraints into sandbox arguments.

### Rule 3: External verifiers contribute evidence, never authority.
No third-party tool (pytest, Semgrep, CodeQL) can directly transition a task or claim into an `ACCEPTED` state. Verifiers emit observations. S-Class verifies:
1. Did the execution run with a trusted binary hash?
2. Did the pre- and post-observation workspace fingerprint match?
3. Did the observed receipt pass without tampering?
4. Are there any conflicting verifier findings?

### Rule 4: Storage provides persistence, S-Class provides semantics.
SQLite stores records reliably across power losses and crashes. SQLite does NOT decide if a state transition is legal. The S-Class state machine enforces invariants before any write is committed.

### Rule 5: Memory is contextual, never authoritative.
Vector stores, memory graphs, and LLM chat transcripts provide advisory context. They are strictly prohibited from altering or asserting project truth. Truth exists solely in the SQLite state store and cryptographic ledger.
