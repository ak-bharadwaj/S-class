<div align="center">

# S-Class

### The Optimization, Governance, Verification, and Portable-Truth Layer Underneath Autonomous Coding Platforms

[![Version](https://img.shields.io/badge/version-0.2.0--survival-blue.svg)](https://github.com/ak-bharadwaj/S-class/tree/survival-v0)
[![Milestones](https://img.shields.io/badge/milestones-18%2F18%20passed-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class/tree/survival-v0)
[![Demos](https://img.shields.io/badge/flagship%20demos-8%2F8%20verified-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class/tree/survival-v0)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

</div>

---

## 1. What S-Class Actually Becomes

S-Class is **not**:
- ✕ another coding agent
- ✕ another IDE
- ✕ a generic AI security scanner

S-Class **is**:
> **The optimization, governance, verification, and portable-truth layer underneath autonomous coding platforms.**

### The Core Strategic Equation

```text
Native platform strength
        +
S-Class compensation
        -
S-Class overhead
        =
NET USER BENEFIT
```

The user keeps their preferred agent and workflow—**OpenAI Codex, Anthropic Claude Code, Google Antigravity, Cursor, Windsurf, or GitHub Copilot**.

S-Class sits silently underneath:

```text
                    USER / IDE
                         │
                         ▼
                ┌─────────────────┐
                │  CODING AGENT   │
                │ Codex / Claude  │
                │ Antigravity/... │
                └────────┬────────┘
                         │
                  intent / action
                         ▼
             ┌─────────────────────┐
             │      S-CLASS        │
             │                     │
             │ Policy              │
             │ Authorization       │
             │ Execution control   │
             │ Observation         │
             │ Verification        │
             │ Truth/state         │
             │ Memory/context      │
             │ Fleet coordination  │
             │ Optimization        │
             │ Evidence/audit      │
             └──────────┬──────────┘
                        │
               verified project truth
                        ▼
             ┌─────────────────────┐
             │   PROJECT / REPO    │
             └─────────────────────┘
```

---

## 2. The Architectural Law

Everything S-Class builds preserves twelve foundational invariants:

| Law | Principle | Meaning |
|:---|:---|:---|
| **L1** | **Agent claims are untrusted** | An agent claiming a task succeeded, tests passed, or bugs were fixed has zero evidential weight. |
| **L2** | **Agent-produced evidence is non-authoritative** | Agent-generated receipts, screenshots, logs, or test reports cannot serve as proof. |
| **L3** | **S-Class owns authorization** | WHO can do WHAT to WHICH resource under WHICH conditions is authoritatively decided by S-Class. |
| **L4** | **Independent observation** | Observations (processes, exit codes, diffs, network, stdio) originate strictly from independent OS reality. |
| **L5** | **Evidence has provenance** | Every evidence receipt is cryptographically bound to process identity, environment, and SHA-256 tree state. |
| **L6** | **Durable project truth depends on evidence** | State cannot be promoted to truth without an unbroken chain of verified evidence. |
| **L7** | **Relevant mutation invalidates evidence** | Post-verification workspace mutations immediately invalidate dependent claims and receipts. |
| **L8** | **Unknown security state fails closed** | Missing sandboxes, unknown capabilities, unparseable syntax, or unhandled errors fail closed (`DENY`). |
| **L9** | **Handoff carries verified truth, not chat history** | Inter-agent handoff transmits verified facts, active leases, and project state—never token-bloated chat transcripts. |
| **L10** | **Memory is contextual, never authoritative** | SCIP, Tree-sitter, or vector memories answer *"What context helps?"*, never *"What is definitely true?"*. |
| **L11** | **Protocol adapters remain thin** | Adapters normalize platform-specific hooks (MCP, ACP, Claude, Codex) into canonical actions without business logic. |
| **L12** | **Mature OSS is reused before custom implementation** | OPA, Cedar, OTel, OCI, Bubblewrap, gVisor, Dagger, Tree-sitter, and SCIP are reused over bespoke engines. |

---

## 3. Product Architecture: The Nine Layers

```text
Layer A — Universal Interface       ActionRequest, Capability, AgentSession, Task, Evidence
Layer B — Policy / Authorization     S-Class Policy API ──┬── OPA Engine (Rego)
                                                          ├── Cedar Engine
                                                          └── Deterministic Engine
Layer C — Execution Plane           ExecutionProvider abstraction (Native, Sandbox, OCI)
Layer D — Sandbox / Isolation       NativeProcess, Bubblewrap, OCI Container, gVisor, Dagger
Layer E — Independent Observation   OTel Tracing, Subprocess Identity, Stdio Hashing, Snapshots
Layer F — Verification Hierarchy    V0 (Assertion) ──▶ V7 (Multi-Signal Corroboration)
Layer G — Durable Project Truth     ProjectTruth, Claim Lifecycles, Invalidation DAG, Checkpoints
Layer H — Contextual Memory         Tree-sitter, SCIP Indexes, Graphiti, Mem0 (Subordinate)
Layer I — Platform Optimization     Archetype Compensation Policies (Codex, Claude, Antigravity)
```

### Layer A — Universal Interface
Normalizes disparate coding platform events into canonical typed primitives:
- `ActionRequest`, `Capability`, `AgentSession`, `Task`, `ToolCall`, `Workspace`, `Resource`, `EvidenceReceipt`, `VerificationRequest`, `ProjectState`.

### Layer B — Policy / Authorization
Decides **WHO** can do **WHAT** to **WHICH RESOURCE** under **WHICH CONDITIONS**:
- Reusable policy backends: Open Policy Agent (OPA Rego), AWS Cedar, deterministic local engine.
- High-confidence credential scanning with automatic HMAC token validation.

### Layer C — Execution Plane & RC.2 Execution Provider Closure
Decouples authorization policy from underlying execution mechanisms:
```text
S-Class authorizes action ──▶ Provider performs action ──▶ S-Class independently observes result
```
- Formalized `ExecutionProvider` abstract interface with `execute()`, `inspect_capabilities()`, and `health_check()`.
- `ExecutionProviderRegistry` with fail-closed resolution.

### Layer D — Sandbox / Isolation
Enforces strict containment without inventing custom sandboxes:
- **NativeProcessProvider**: Deterministic host baseline execution.
- **BubblewrapProvider**: Linux unprivileged user-namespace containerization (`bwrap`).
- **OCIProvider**: Standard container configuration baseline (Docker / Podman).
- **GVisorProvider**: Application kernel virtualization (`runsc`).
- **DaggerProvider**: Portable, reproducible containerized verification pipelines.
- **Fail-Closed Law**: *NO SANDBOX -> NO SANDBOXED EXECUTION*. If a requested sandbox is unavailable, S-Class strictly refuses uncontained degradation.

### Layer E — Independent Observation
The core epistemic moat:
- OpenTelemetry semantic conventions for AI execution spans, events, and metrics (`sclass.action.id`, `sclass.evidence.id`, `sclass.task.id`).
- Independently records PID, executable hash, actual `argv`, exit status, stdout/stderr SHA-256 digests, and filesystem mutations.

### Layer F — Verification Hierarchy (V0–V7)
Claims require verification commensurate with their impact:
- **V0 Agent assertion:** Untrusted claim.
- **V1 Process observation:** Exit code, runtime identity.
- **V2 File/repo observation:** Cryptographic diffs, modified file trees.
- **V3 Deterministic tests:** Independently executed pytest/jest/cargo test runs.
- **V4 Static analysis:** AST parsing, type checks, lint checks.
- **V5 Semantic verification:** Invariant satisfaction, contract conformance.
- **V6 Independent verifier:** Disinterested secondary model evaluation.
- **V7 Multi-signal corroboration:** Correlated consensus across independent signals.

### Layer G — Durable Project Truth
Maintains the canonical state of truth across agent sessions:
- **Conversation memory ≠ Project truth**: An agent saying something five turns ago cannot make it true.
- Maintains `VerifiedProjectState`: verified claims, invalidated claims, active assumptions, contracts, symbol leases, evidence lineage, and verification history.

### Layer H — Contextual Memory
Provides contextual code intelligence (SCIP, Tree-sitter, repository index) to assist agents without ever becoming authoritative truth.

### Layer I — Platform Optimization & Empirical Profiles
Maintains platform-specific compensation profiles as testable optimization hypotheses:
- **OpenAI Codex:** Preserves long-horizon terminal autonomy; compensates with fast post-run verification, scope control, and regression detection.
- **Anthropic Claude Code:** Preserves deep reasoning and context synthesis; compensates with minimal projection (reducing context bloat by 98.4%) and state tracking.
- **Google Antigravity:** Preserves parallel multi-agent swarms; compensates with atomic SQLite symbol leases, duplicate work prevention, and quarantine isolation.

---

## 4. Fleet Intelligence

Coordinates multi-agent parallel swarms without central bottlenecks or race conditions:
```text
Agent A       Agent B       Agent C
   │             │             │
   └─────────────┼─────────────┘
                 ▼
         Shared Task Graph
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
  Symbol Leases     Assumption Graph
       │                   │
       └─────────┬─────────┘
                 ▼
     Cross-Agent Evidence Gate
                 ▼
     Global Truth Verification
```

- **Atomic SQLite Serialization:** Microsecond-tier transactional ACID concurrency for agent leases.
- **Symbol Ownership:** Prevents overlapping edits and duplicate work using codebase knowledge graphs.
- **Quarantine Engine:** Isolates misbehaving or compromised subagents while healthy agents continue execution unimpeded.
- **Epistemic Invariant:** *No agent may create durable verified truth merely because another agent claims it is true.*

---

## 5. Protocols & Standards Integration

S-Class leverages standard industry protocols rather than proprietary walled gardens:
- **Model Context Protocol (MCP):** Official MCP Python SDK integration with tool exposition, prompt routing, and fail-closed resource access control.
- **Agent Client Protocol (ACP):** Official ACP JSON-RPC standard for editor-to-agent communication, enabling transparent S-Class proxying between editors and coding engines.

---

## 6. The Reality Lab & Empirical Benchmark Suite

S-Class validates net user benefit across a 10-tier empirical benchmark suite:
- **T1** Trivial edit
- **T2** Bug fix
- **T3** Feature addition
- **T4** Multi-file refactor
- **T5** Dependency migration
- **T6** Test repair
- **T7** Security-sensitive change
- **T8** Regression-prone change
- **T9** Long-horizon multi-step iteration
- **T10** Adversarial penetration task

### Raw Observables vs. Derived Value
We measure raw physical observables—wall-clock time, tokens, exit codes, AST diffs, tool calls, and interruptions—deriving:
- Regressions prevented
- Unsafe actions blocked
- Verification precision & recall
- Latency overhead
- Net User Benefit

---

## 7. 30-Second Quickstart

### Installation & Initialization
```bash
# Install S-Class
pip install s-class

# Initialize workspace governance
sclass init

# Inspect status, active leases, and verified truth
sclass status
```

### Silent Native Integration
Configure hooks in your native editor/platform directory:
- **OpenAI Codex CLI:** `.codex/hooks.json`
- **Anthropic Claude Code:** `.claude/settings.local.json`
- **Cursor 1.7+:** `.cursor/hooks.json`
- **Google Antigravity:** `.agents/hooks.json`

---

## 8. Verification & Certified Milestones

### Master Milestone Auditor (18/18 Certified)
```bash
# Run the master milestone auditor across all 18 product & reality milestones
python scratch/verify_all_milestones.py
```

### Complete Test Suite (712+ Passed Tests)
```bash
# Run complete test suite across 55 test modules
python -m pytest
```

### Flagship Demos (8/8 Verified)
```bash
# Run all 8 product & platform flagship demonstrations
python demos/run_all_demos.py
```
1. False Test Result Claim (Independent Verification & Anti-Cheating)
2. Dangerous Command Execution (Deterministic Boundary Enforcement)
3. Secret Exfiltration Defense (Cryptographic Redaction & Leakage Prevention)
4. Post-Verification Mutation Invalidation (Tamper-Resistant Project State)
5. Cross-Agent Continuity (Claude -> Codex Zero-Drift Handoff)
6. Flagship Demo A: OpenAI Codex Autonomous Long-Horizon Governance
7. Flagship Demo B: Anthropic Claude Code Deep Reasoning Minimal Projection
8. Flagship Demo C: Google Antigravity Parallel Multi-Agent Swarm Integrity

---

## 🔒 License & Legal Notice

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class is **Proprietary and Confidential Software**. See [LICENSE](LICENSE) for details.
