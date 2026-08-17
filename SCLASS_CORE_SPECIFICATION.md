# S-Class — Core Specification (D0 Contract Freeze)
### Version: 1.0.0 (Canonical D0 Specification)
### Authority: Master Plan Directive (`SCLASS_MASTER_SYSTEM_DESIGN_AND_BUILD_PLAN.md`)
### Status: 🟢 FROZEN CONTRACT

> **Notice**: This document is the canonical, immutable specification of the S-Class D0 Core. It formalizes all domain schemas, state machines, event models, policy grammars, evidence contracts, claim contracts, planner/controller contracts, plan-as-artifact contracts, adapter contracts, concurrency semantics, staleness propagation algorithms, security boundaries, core invariants, and test architecture. No code in subsequent layers (D1–D12) may deviate from or weaken these contracts.

---

## 1. Document Control & Authority Directive

### 1.1 Operating Hierarchy

Development and execution in S-Class follow a strict unidirectional hierarchy:

```text
MASTER PLAN (SCLASS_MASTER_SYSTEM_DESIGN_AND_BUILD_PLAN.md)
    ↓
D0 — CORE SPECIFICATION (SCLASS_CORE_SPECIFICATION.md - This Document)
    ↓
DOMAIN CONTRACTS (D1 Domain Kernel)
    ↓
STATE & EVENT ENGINE (D2 Reducer & Event Log)
    ↓
POLICY & CLAIM ENGINES (D3 Policy / D4 Claim & Evidence)
    ↓
CONTROLLER & ADAPTERS (D5 Controller / D6 Provider Fabric)
    ↓
AGENT INTEGRATION & PLANNER (D7 Agent / D8 Planner + Self-Planning)
    ↓
RECOVERY & REGRESSION (D9 Failure Recovery & Regression)
    ↓
PROTOTYPE & ADVERSARIAL VERIFICATION (D10 Prototype / D11 Red Team)
```

### 1.2 The Central Model

All software engineering operations governed by S-Class flow through this epistemic pipeline:

$$\text{TASK} \xrightarrow{\text{extract}} \text{OBLIGATIONS} \xrightarrow{\text{compile}} \text{CLAIMS} \xrightarrow{\text{bind}} \text{POLICY} \xrightarrow{\text{propose}} \text{ACTIONS} \xrightarrow{\text{execute}} \text{EVIDENCE} \xrightarrow{\text{reduce}} \text{ASSESSMENT} \xrightarrow{\text{decide}} \begin{cases} \text{ACCEPT} \\ \text{RECOVER} \to \text{PLANNER} \end{cases}$$

Underlying all transitions:
$$\text{APPEND-ONLY EVENT LOG} + \text{CRYPTOGRAPHIC PROVENANCE} + \text{DEPENDENCY GRAPH}$$

### 1.3 Ownership Boundary Matrix

| Component / Responsibility | S-Class Core Owns? | External Provider / Worker Owns? | Specification Section |
| :--- | :---: | :---: | :--- |
| Requirement Interpretation & Deconstruction | **YES** | No | §3.1, §3.2 |
| Obligation Graph & Lifecycle | **YES** | No | §3.2, §4.1 |
| Claim Formal Semantics & Epistemics | **YES** | No | §3.3, §4.2, §7 |
| Acceptance Policy & Invariant Enforcement | **YES** | No | §3.4, §6 |
| Action Proposal Planning (incl. Self-Planning) | **YES** | No | §3.5, §8, §9 |
| Action Authorization & Control (Disposal) | **YES** | No | §3.6, §4.5, §8 |
| Evidence Normalization & Schema Verification | **YES** | No | §3.7, §7, §10 |
| Evidence Provenance, HMAC & SHA Binding | **YES** | No | §3.7, §7.4, §10.2 |
| Claim/Evidence Reduction & Contradiction Detection | **YES** | No | §4.2, §5.4, §7.3 |
| Staleness Invalidation Cascade | **YES** | No | §4.3, §11.3 |
| Audit Trail & Evaluation Receipts | **YES** | No | §3.9, §7.5 |
| Code Generation & Patch Synthesis | **NO** | AI Worker (LLM) | §8.1 |
| Static Analysis Engine Execution | **NO** | Ruff / Pyright / Semgrep | §10.5 |
| Property-Based Test Generation | **NO** | Hypothesis / CleanRoom | §10.5 |
| API Contract Fuzzing | **NO** | Schemathesis | §10.5 |
| Dependency Vulnerability DB Lookup | **NO** | OSV-Scanner | §10.5 |
| Process & OS Sandbox Containment | **NO** | OS Container / Child Worker | §10.2 |

---

## 2. Existing Codebase Audit & Architectural Disposition

An exhaustive audit of all 73 source files and test suites in `ak-bharadwaj/S-class` against the Master Plan produces the following disposition matrix:

### 2.1 Summary Disposition Table

| Disposition | Count | Criteria | Target Architectural Layer |
| :--- | :---: | :--- | :--- |
| 🟢 **REUSE** | 6 modules | Conforms directly to S-Class provenance, HMAC verification, process isolation, and clean-room testing contracts. | D0 Provider Infrastructure, D6 Adapter Fabric |
| 🟡 **ADAPT** | 8 modules | Contains valid algorithms (topological sorting, AST visitors, file lock management) that must be refactored into decoupled D0 contracts. | D1 Domain Kernel, D6 Adapters, D11 Dependency Engine |
| 🔴 **REWRITE** | 12 modules | Built on old V11.2 mutable state, God methods, bare exceptions, or ungrounded debate squads. Must be cleanly written from scratch according to D0 schemas. | D1 Kernel, D2 Reducer, D3 Policy, D4 Claim/Evidence, D5 Controller, D8 Planner |
| 🗑️ **DISCARD** | 14 modules | Legacy V11.2 tech debt: massive static dictionaries (>2000 lines), heuristic regex matching, fake screenshot generators, and ungrounded prompt simulators. | Deleted / Replaced by D0 Schemas & Real Providers |

### 2.2 Component-by-Component Disposition

#### 2.2.1 Core Kernel & Runtime Layer
- `evidence_provider.py` $\to$ 🟢 **REUSE (Provider Base)**: Base provider classes, HMAC verification, and child-process worker protocol from Gate 3 work.
- `benchmark/providers/schemathesis/*` $\to$ 🟢 **REUSE**: Certified Schemathesis 4.24.3 integration, process isolation, SHA binding.
- `property_verifier.py` $\to$ 🟢 **REUSE**: Clean-Room Hypothesis execution engine.
- `file_lock.py` $\to$ 🟢 **REUSE**: Portalocker backend, cross-platform POSIX/Windows byte-range locking.
- `execution_dependency_resolver.py` $\to$ 🟡 **ADAPT**: Kahn's topological sort algorithm adapts directly into D11 Obligation DAG Scheduler.
- `ast_dependency_resolver.py` $\to$ 🟡 **ADAPT**: Refactor to use Python `ast` and `libcst` cleanly for import graph extraction without regex fallbacks.
- `config_gc.py` $\to$ 🟡 **ADAPT**: Hardened garbage collection logic for runtime workspace artifacts.
- `static_analysis_provider.py` $\to$ 🟡 **ADAPT**: Ruff/Semgrep subprocess runner adapts to D6 provider interface.
- `type_verification_provider.py` $\to$ 🟡 **ADAPT**: Pyright runner adapts to D6 provider interface.
- `event_store.py` $\to$ 🔴 **REWRITE**: Replace ad-hoc JSONL appender with D2 strict append-only typed event log with digest chains.
- `sclass_kernel.py` $\to$ 🔴 **REWRITE**: Eliminate V11 monolithic orchestration in favor of D5 Controller + D2 Reducer.
- `runtime.py` $\to$ 🔴 **REWRITE**: Split 1229-line God file into distinct modular subsystems (Execution Fabric, Sandbox, Tool Runner).
- `context_compressor.py` $\to$ 🗑️ **DISCARD**: Heuristic string compressor that stealthily triggered DB writes.
- `zero_infra_db.py` $\to$ 🗑️ **DISCARD**: Unsafe flat JSON KV store replaced by D2 Event Store & Projections.
- `error_recovery.py` $\to$ 🗑️ **DISCARD**: Brittle regex-based error recovery patterns replaced by D9 Bounded Recovery Engine.

#### 2.2.2 Domain Representation & IR Pipeline Layer
- `evidence_ir.py` $\to$ 🟡 **ADAPT**: Upgrade dataclasses to strict D0 Pydantic v2 `Evidence` schemas.
- `changeset_ir.py` $\to$ 🟡 **ADAPT**: Refactor git diff tracking into D1 Changeset representation.
- `domain_primitives.py` $\to$ 🔴 **REWRITE**: Replaced by canonical D0 Domain Models (`Task`, `Obligation`, `Claim`, `Policy`, `Evidence`).
- `requirement_ir.py` $\to$ 🔴 **REWRITE**: Replaced by canonical D0 `Obligation` and `Claim` schemas.
- `execution_ir.py` $\to$ 🔴 **REWRITE**: Replaced by canonical D0 `ActionProposal` and `ControllerDecision` schemas.
- `spec_synthesis.py` (137KB) $\to$ 🗑️ **DISCARD**: Monolithic 2200-line heuristic synthesis with massive hardcoded domain dictionaries.
- `shadow_semantic_synthesis.py` $\to$ 🗑️ **DISCARD**: Duplicate heuristic synthesizer.
- `semantic_decomposer.py` $\to$ 🗑️ **DISCARD**: Static word lists and fragile pluralization heuristics.
- `behavior_graph.py` $\to$ 🗑️ **DISCARD**: Unstructured graph parser producing empty ghost nodes.

#### 2.2.3 Planning, Governance & Verification Layer
- `artifact_governor.py` (119KB) $\to$ 🔴 **REWRITE**: Replace 1858-line rule spaghetti with clean D3 Policy Engine & D5 Controller.
- `verifier.py` (64KB) $\to$ 🔴 **REWRITE**: Replace God-methods and screenshot mocks with D4 Claim/Evidence Reducer & D6 Provider Fabric.
- `sclass_planner.py` / `planner.py` $\to$ 🔴 **REWRITE**: Implement D8 Planner with Plan-as-Artifact recursive self-planning model.
- `strategy.py` $\to$ 🔴 **REWRITE**: Heuristic strategy replaced by deterministic D3 policy compilation.
- `security_shield.py` $\to$ 🗑️ **DISCARD**: Naive regexes flagging valid configs as secrets.
- `architecture_debate.py` (59KB) $\to$ 🗑️ **DISCARD**: Ungrounded multi-agent debate scripts replaced by deterministic claim verification.
- `sclass_grill.py` $\to$ 🗑️ **DISCARD**: Heuristic prompt griller replaced by formal obligation compiler.
- `sclass_doctor.py` / `doctor.py` $\to$ 🗑️ **DISCARD**: Brittle hardcoded doc audit scripts replaced by D0 audit receipts.

---

## 3. Canonical Domain Schemas & Data Structures

All S-Class domain models are strictly typed, serializable, and validated via JSON Schema Draft 2020-12 and Pydantic v2 models.

### 3.1 Task Schema (`Task`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "Task"
type: "object"
required:
  - "task_id"
  - "raw_prompt"
  - "repository_context"
  - "created_at"
properties:
  task_id:
    type: "string"
    pattern: "^TASK-[A-Za-z0-9_-]+$"
  raw_prompt:
    type: "string"
    minLength: 1
  repository_context:
    type: "object"
    required:
      - "repository_id"
      - "base_commit_sha"
      - "branch"
    properties:
      repository_id:
        type: "string"
      base_commit_sha:
        type: "string"
        pattern: "^[a-f0-9]{40}$"
      branch:
        type: "string"
      dirty_working_tree:
        type: "boolean"
        default: false
  constraints:
    type: "object"
    properties:
      languages:
        type: "array"
        items: { type: "string" }
      frameworks:
        type: "array"
        items: { type: "string" }
      max_budget_usd:
        type: "number"
        minimum: 0.0
      timeout_seconds:
        type: "integer"
        minimum: 1
  environment:
    type: "object"
    additionalProperties: { type: "string" }
  created_at:
    type: "string"
    format: "date-time"
```

### 3.2 Obligation Schema (`Obligation`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "Obligation"
type: "object"
required:
  - "obligation_id"
  - "task_id"
  - "title"
  - "category"
  - "criticality"
  - "status"
  - "depends_on"
properties:
  obligation_id:
    type: "string"
    pattern: "^OBL-[A-Za-z0-9_-]+$"
  task_id:
    type: "string"
    pattern: "^TASK-[A-Za-z0-9_-]+$"
  parent_obligation_id:
    type: ["string", "null"]
    pattern: "^OBL-[A-Za-z0-9_-]+$"
  title:
    type: "string"
  description:
    type: "string"
  category:
    type: "string"
    enum:
      - "FUNCTIONAL_BEHAVIOR"
      - "SECURITY_INTEGRITY"
      - "REGRESSION_SAFETY"
      - "BACKWARD_COMPATIBILITY"
      - "PERFORMANCE_RESOURCE"
      - "ARCHITECTURE_CONFORMANCE"
      - "REPAIR_RECOVERY"
  criticality:
    type: "string"
    enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
  status:
    type: "string"
    enum:
      - "OPEN"
      - "READY"
      - "IN_PROGRESS"
      - "SATISFIED"
      - "BLOCKED"
      - "CONDITIONAL"
      - "REQUIRES_REASSESSMENT"
  depends_on:
    type: "array"
    items:
      type: "string"
      pattern: "^OBL-[A-Za-z0-9_-]+$"
  claim_ids:
    type: "array"
    items:
      type: "string"
      pattern: "^CLM-[A-Za-z0-9_-]+$"
  policy_id:
    type: "string"
    pattern: "^POL-[A-Za-z0-9_-]+$"
```

### 3.3 Claim Schema (`Claim`) & 5-Tier Taxonomy

Every claim is a machine-checkable proposition decomposed into Subject, Predicate, Context, and Expected Outcome.

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "Claim"
type: "object"
required:
  - "claim_id"
  - "obligation_id"
  - "tier"
  - "subject"
  - "predicate"
  - "context"
  - "expected"
  - "criticality"
  - "status"
properties:
  claim_id:
    type: "string"
    pattern: "^CLM-[A-Za-z0-9_-]+$"
  obligation_id:
    type: "string"
    pattern: "^OBL-[A-Za-z0-9_-]+$"
  tier:
    type: "string"
    enum:
      - "V0_OBSERVABLE"    # HTTP status, return value, exit code, file existence
      - "V1_STRUCTURAL"    # AST node, schema syntax, typing, dependency rule
      - "V2_BEHAVIORAL"    # Invariant, idempotency, concurrency, exception behavior
      - "V3_SYSTEM_LEVEL"  # Backward compatibility, end-to-end workflow, data integrity
      - "V4_JUDGMENT"      # Maintainability, ergonomics, visual polish (NON-PROVING)
  subject:
    type: "object"
    required: ["target_type", "identifier"]
    properties:
      target_type:
        type: "string"
        enum: ["ENDPOINT", "FUNCTION", "CLASS", "FILE", "SCHEMA", "ARCHITECTURE_COMPONENT"]
      identifier:
        type: "string"
  predicate:
    type: "string"
    enum:
      - "RETURNS_STATUS_CODE"
      - "REJECTS_UNAUTHORIZED_REQUEST"
      - "PRESERVES_IDEMPOTENCY"
      - "PREVENTS_RACE_CONDITION"
      - "MATCHES_SCHEMA"
      - "CONFORMS_TO_AST_CONSTRAINT"
      - "SATISFIES_PROPERTY_INVARIANT"
      - "PRESERVES_BACKWARD_COMPATIBILITY"
      - "TERMINATES_WITHIN_BOUNDS"
  context:
    type: "object"
    additionalProperties: true
  expected:
    type: "object"
    additionalProperties: true
  criticality:
    type: "string"
    enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
  status:
    type: "string"
    enum:
      - "UNSUPPORTED"
      - "SUPPORTED"
      - "CONTRADICTED"
      - "CONFLICTED"
      - "STALE"
  required_provider_capabilities:
    type: "array"
    items: { type: "string" }
```

> **Mandatory Rule for V4 (Judgment)**: Evidence for Tier $V_4$ claims can **never** satisfy a mandatory obligation on its own. It requires corroborating $V_0$–$V_3$ deterministic evidence or an explicit, cryptographically signed human exception record (§3.4.2).

### 3.4 Policy Schema (`Policy`) & Exception Model

#### 3.4.1 Policy Rule Schema

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "Policy"
type: "object"
required:
  - "policy_id"
  - "scope_level"
  - "expression"
  - "version"
properties:
  policy_id:
    type: "string"
    pattern: "^POL-[A-Za-z0-9_-]+$"
  scope_level:
    type: "string"
    enum:
      - "SYSTEM_INVARIANT"   # S-Class immutable core rules (Tier 0)
      - "ORGANIZATION"       # Enterprise / Org level rules (Tier 1)
      - "PROJECT"            # Repository / Project rules (Tier 2)
      - "OBLIGATION"         # Specific obligation constraints (Tier 3)
  version:
    type: "integer"
    minimum: 1
  expression:
    type: "object"
    required: ["combinator", "rules"]
    properties:
      combinator:
        type: "string"
        enum: ["ALL", "ANY", "AT_LEAST", "CONDITIONAL"]
      min_count:
        type: "integer"
        minimum: 1
      independent_by:
        type: "string"
        enum: ["PROVIDER_TYPE", "EXECUTION_PROCESS", "AUTHOR"]
      rules:
        type: "array"
        items: { type: "object" }
      condition:
        type: "object"
```

#### 3.4.2 Policy Exception Record Schema

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "PolicyException"
type: "object"
required:
  - "exception_id"
  - "obligation_id"
  - "policy_id"
  - "justification"
  - "authorized_by"
  - "compensating_controls"
  - "expiry"
  - "hmac_signature"
properties:
  exception_id:
    type: "string"
    pattern: "^EXC-[A-Za-z0-9_-]+$"
  obligation_id:
    type: "string"
  policy_id:
    type: "string"
  justification:
    type: "string"
    minLength: 20
  authorized_by:
    type: "object"
    required: ["actor_id", "actor_role", "public_key_fingerprint"]
    properties:
      actor_id: { type: "string" }
      actor_role: { type: "string" }
      public_key_fingerprint: { type: "string" }
  compensating_controls:
    type: "array"
    minItems: 1
    items: { type: "string" }
  expiry:
    type: "string"
    format: "date-time"
  hmac_signature:
    type: "string"
    pattern: "^[a-f0-9]{64}$"
```

### 3.5 Action Proposal Schema (`ActionProposal`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "ActionProposal"
type: "object"
required:
  - "proposal_id"
  - "task_id"
  - "action_type"
  - "target"
  - "purpose"
  - "prerequisites"
  - "resource_limits"
properties:
  proposal_id:
    type: "string"
    pattern: "^PROP-[A-Za-z0-9_-]+$"
  task_id:
    type: "string"
  action_type:
    type: "string"
    enum:
      - "RUN_VERIFICATION_TOOL"
      - "EXECUTE_AGENT_CODE_PATCH"
      - "DECOMPOSE_OBLIGATION"
      - "RUN_REGRESSION_SUITE"
      - "REQUEST_HUMAN_EVIDENCE"
      - "PROPOSE_ARCHITECTURE_PLAN"
  target:
    type: "object"
    required: ["target_identifier", "target_kind"]
    properties:
      target_identifier: { type: "string" }
      target_kind: { type: "string" }
  purpose:
    type: "object"
    required: ["rationale", "target_claim_ids"]
    properties:
      rationale: { type: "string" }
      target_claim_ids:
        type: "array"
        items: { type: "string" }
  prerequisites:
    type: "array"
    items: { type: "string" }
  resource_limits:
    type: "object"
    required: ["timeout_ms", "max_memory_mb"]
    properties:
      timeout_ms: { type: "integer", maximum: 600000 }
      max_memory_mb: { type: "integer", maximum: 8192 }
      max_cost_usd: { type: "number", default: 1.0 }
```

### 3.6 Controller Decision Schema (`ControllerDecision`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "ControllerDecision"
type: "object"
required:
  - "decision_id"
  - "proposal_id"
  - "verdict"
  - "decided_at"
properties:
  decision_id:
    type: "string"
    pattern: "^DEC-[A-Za-z0-9_-]+$"
  proposal_id:
    type: "string"
  verdict:
    type: "string"
    enum: ["APPROVED", "REJECTED", "DEFERRED"]
  rejection_reasons:
    type: "array"
    items: { type: "string" }
  execution_token:
    type: ["string", "null"]
  decided_at:
    type: "string"
    format: "date-time"
```

### 3.7 Evidence Schema (`Evidence`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "Evidence"
type: "object"
required:
  - "evidence_id"
  - "claim_id"
  - "provider_id"
  - "capability"
  - "execution_id"
  - "source_sha"
  - "scope"
  - "observation"
  - "polarity"
  - "validity"
  - "provenance"
  - "signature"
properties:
  evidence_id:
    type: "string"
    pattern: "^EV-[A-Za-z0-9_-]+$"
  claim_id:
    type: "string"
    pattern: "^CLM-[A-Za-z0-9_-]+$"
  provider_id:
    type: "string"
  capability:
    type: "string"
    enum:
      - "PROPERTY_TESTING"
      - "API_CONTRACT_FUZZING"
      - "STATIC_AST_ANALYSIS"
      - "TYPE_CHECK"
      - "UNIT_TEST_EXECUTION"
      - "DEPENDENCY_SECURITY_SCAN"
      - "PROVENANCE_BEARING_HUMAN_REVIEW"
  execution_id:
    type: "string"
  source_sha:
    type: "string"
    pattern: "^[a-f0-9]{40}$"
  scope:
    type: "object"
    required: ["targets_evaluated"]
    properties:
      targets_evaluated:
        type: "array"
        items: { type: "string" }
      aspects_covered:
        type: "array"
        items: { type: "string" }
  observation:
    type: "object"
    required: ["raw_status", "diagnostics"]
    properties:
      raw_status:
        type: "string"
        enum: ["PASS", "FAIL", "ERROR", "TIMEOUT", "INCONCLUSIVE"]
      diagnostics:
        type: "array"
        items: { type: "object" }
      counterexample:
        type: ["object", "null"]
  polarity:
    type: "string"
    enum: ["SUPPORTS", "REFUTES", "NEUTRAL"]
  validity:
    type: "string"
    enum: ["VALID", "STALE", "INVALID", "SUPERSEDED"]
  independence_group:
    type: "string"
  provenance:
    type: "object"
    required: ["engine_name", "engine_version", "environment_hash", "timestamp"]
    properties:
      engine_name: { type: "string" }
      engine_version: { type: "string" }
      environment_hash: { type: "string" }
      timestamp: { type: "string", format: "date-time" }
  signature:
    type: "object"
    required: ["algorithm", "digest", "hmac"]
    properties:
      algorithm: { type: "string", enum: ["HMAC-SHA256", "ED25519"] }
      digest: { type: "string", pattern: "^[a-f0-9]{64}$" }
      hmac: { type: "string", pattern: "^[a-f0-9]{64}$" }
```

### 3.8 Plan-as-Artifact Schema (`Plan`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "Plan"
type: "object"
required:
  - "plan_id"
  - "origin"
  - "source_prompt"
  - "status"
  - "architecture_claims"
  - "dependency_graph"
  - "milestone_sequence"
  - "open_risks"
  - "contradictions"
  - "revision"
properties:
  plan_id:
    type: "string"
    pattern: "^PLAN-[A-Za-z0-9_-]+$"
  origin:
    type: "string"
    enum: ["TASK_DECOMPOSITION", "SELF_PLANNING", "HUMAN_DIRECTIVE"]
  source_prompt:
    type: "string"
  status:
    type: "string"
    enum: ["DRAFT", "UNDER_REVIEW", "VALIDATED", "REJECTED", "SUPERSEDED"]
  revision:
    type: "integer"
    minimum: 1
  revision_of:
    type: ["string", "null"]
  architecture_claims:
    type: "array"
    items:
      type: "object"
      required: ["claim_id", "subject", "predicate", "criticality", "evidence_required"]
      properties:
        claim_id: { type: "string" }
        subject: { type: "string" }
        predicate: { type: "string" }
        criticality: { type: "string", enum: ["LOW", "MEDIUM", "HIGH", "CRITICAL"] }
        evidence_required:
          type: "array"
          items:
            type: "object"
            required: ["capability", "tier"]
            properties:
              capability: { type: "string" }
              tier: { type: "string" }
  dependency_graph:
    type: "object"
    additionalProperties:
      type: "array"
      items: { type: "string" }
  milestone_sequence:
    type: "array"
    items:
      type: "object"
      required: ["milestone_id", "title", "obligation_ids"]
      properties:
        milestone_id: { type: "string" }
        title: { type: "string" }
        obligation_ids: { type: "array", items: { type: "string" } }
  open_risks:
    type: "array"
    items: { type: "string" }
  contradictions:
    type: "array"
    items: { type: "string" }
```

### 3.9 Assessment Receipt Schema (`AssessmentReceipt`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "AssessmentReceipt"
type: "object"
required:
  - "receipt_id"
  - "obligation_id"
  - "policy_version"
  - "repository_sha"
  - "verdict"
  - "claim_assessments"
  - "conflicts"
  - "stale_evidence"
  - "evaluated_at"
  - "signer_digest"
properties:
  receipt_id:
    type: "string"
    pattern: "^RCPT-[A-Za-z0-9_-]+$"
  obligation_id:
    type: "string"
  policy_version:
    type: "integer"
  repository_sha:
    type: "string"
    pattern: "^[a-f0-9]{40}$"
  verdict:
    type: "string"
    enum: ["SATISFIED", "UNSATISFIED", "CONFLICTED", "BLOCKED"]
  claim_assessments:
    type: "array"
    items:
      type: "object"
      required: ["claim_id", "status", "supporting_evidence_ids", "refuting_evidence_ids"]
      properties:
        claim_id: { type: "string" }
        status: { type: "string" }
        supporting_evidence_ids: { type: "array", items: { type: "string" } }
        refuting_evidence_ids: { type: "array", items: { type: "string" } }
  conflicts:
    type: "array"
    items: { type: "string" }
  stale_evidence:
    type: "array"
    items: { type: "string" }
  evaluated_at:
    type: "string"
    format: "date-time"
  signer_digest:
    type: "string"
    pattern: "^[a-f0-9]{64}$"
```

### 3.10 Event Envelope Schema (`EventEnvelope`)

```yaml
$schema: "https://json-schema.org/draft/2020-12/schema"
title: "EventEnvelope"
type: "object"
required:
  - "event_id"
  - "event_type"
  - "sequence_number"
  - "aggregate_id"
  - "timestamp"
  - "payload"
  - "parent_digest"
  - "digest"
properties:
  event_id:
    type: "string"
    pattern: "^EVT-[A-Za-z0-9_-]+$"
  event_type:
    type: "string"
  sequence_number:
    type: "integer"
    minimum: 1
  aggregate_id:
    type: "string"
  timestamp:
    type: "string"
    format: "date-time"
  payload:
    type: "object"
  parent_digest:
    type: "string"
    pattern: "^[a-f0-9]{64}$"
  digest:
    type: "string"
    pattern: "^[a-f0-9]{64}$"
```

---

## 4. State Machines & Formal Transition Tables

### 4.1 Obligation Lifecycle State Machine

$$\mathcal{S}_{\text{OBL}} = \{\text{OPEN}, \text{READY}, \text{IN\_PROGRESS}, \text{SATISFIED}, \text{BLOCKED}, \text{CONDITIONAL}, \text{REQUIRES\_REASSESSMENT}\}$$

```text
       ┌──────────┐
       │   OPEN   │ ◄────────────────────────────────────────┐
       └────┬─────┘                                          │
            │ dependencies satisfied                         │
            ▼                                                │
       ┌──────────┐                                          │
       │  READY   │                                          │
       └────┬─────┘                                          │
            │ action initiated                               │
            ▼                                                │
       ┌──────────────┐                                      │
       │ IN_PROGRESS  │ ──► [Resource Exceeded / Error] ──► ┌─────────┐
       └────┬─────────┘                                     │ BLOCKED │
            │                                               └─────────┘
            ├──► [Policy Satisfied + All Claims Supported] ──► ┌───────────┐
            │                                                  │ SATISFIED │
            ├──► [Approved Exception Record] ─────────────────► ┌───────────┐
            │                                                  │CONDITIONAL│
            └──► [Source Mutated / Claim Stale] ───────────────► ┌──────────────────────┐
                                                               │REQUIRES_REASSESSMENT │
                                                               └──────────┬───────────┘
                                                                          │ reassess
                                                                          ▼
                                                                     (to READY/IN_PROGRESS)
```

| Source State | Event Trigger | Guard Conditions | Target State | State Action |
| :--- | :--- | :--- | :--- | :--- |
| `OPEN` | `DEPENDENCY_SATISFIED` | $\forall d \in \text{depends\_on}: \text{State}(d) \in \{\text{SATISFIED}, \text{CONDITIONAL}\}$ | `READY` | Emit `OBLIGATION_READY` |
| `READY` | `ACTION_AUTHORIZED` | Controller issues valid execution token | `IN_PROGRESS` | Lock execution slot |
| `IN_PROGRESS` | `EVALUATION_COMPLETED` | Policy Engine evaluates: `SATISFIED` $\land \text{Conflicts} = \emptyset$ | `SATISFIED` | Emit `OBLIGATION_CLOSED` + Receipt |
| `IN_PROGRESS` | `RESOURCE_EXHAUSTED` | Retries $\ge \text{max\_attempts} \lor \text{Timeout}$ | `BLOCKED` | Trigger Escalation / Diagnostics |
| `IN_PROGRESS` | `EXCEPTION_GRANTED` | Valid cryptographically signed Exception Record (§3.4.2) | `CONDITIONAL` | Mint conditional receipt |
| `SATISFIED` | `SOURCE_MUTATED` | Repository SHA changed $\land \text{Impact}(C) = \text{TRUE}$ | `REQUIRES_REASSESSMENT` | Invalidate evidence, mark claims stale |
| `CONDITIONAL` | `SOURCE_MUTATED` | Repository SHA changed | `REQUIRES_REASSESSMENT` | Invalidate evidence |
| `REQUIRES_REASSESSMENT` | `REASSESSMENT_DISPATCHED` | Re-evaluation job enqueued | `READY` | Re-queue for verification |

### 4.2 Claim Epistemic State Machine

$$\mathcal{S}_{\text{CLM}} = \{\text{UNSUPPORTED}, \text{SUPPORTED}, \text{CONTRADICTED}, \text{CONFLICTED}, \text{STALE}\}$$

| Source State | Event Trigger | Guard Conditions | Target State | Epistemic Rule |
| :--- | :--- | :--- | :--- | :--- |
| `UNSUPPORTED` | `EVIDENCE_ADDED` | $\text{Valid}(E) \land \text{Polarity}(E) = \text{SUPPORTS} \land \text{Coverage}(E) = \text{FULL}$ | `SUPPORTED` | Provenance verified |
| `UNSUPPORTED` | `EVIDENCE_REFUTES` | $\text{Valid}(E) \land \text{Polarity}(E) = \text{REFUTES}$ | `CONTRADICTED` | Counterexample logged |
| `SUPPORTED` | `EVIDENCE_REFUTES` | New valid evidence refutes an already supported claim | `CONFLICTED` | **NO OVERWRITE / NO MAJORITY VOTE** |
| `CONTRADICTED` | `EVIDENCE_ADDED` | New valid evidence supports a contradicted claim | `CONFLICTED` | **NO OVERWRITE / NO MAJORITY VOTE** |
| Any State | `SOURCE_MUTATED` | Dependent AST/File modified at repository HEAD | `STALE` | Invalidate previous assurance |
| `STALE` | `EVIDENCE_ADDED` | Fresh evidence matching current `HEAD` SHA | $\text{Reduce}(\text{NewEvidence})$ | Re-evaluate fresh evidence |

### 4.3 Evidence Validity State Machine

$$\mathcal{S}_{\text{EV}} = \{\text{VALID}, \text{STALE}, \text{INVALID}, \text{SUPERSEDED}\}$$

- `VALID` $\xrightarrow{\text{SOURCE\_MUTATED}}$ `STALE`: The underlying code changed.
- `VALID` $\xrightarrow{\text{SIGNATURE\_FAILED} \lor \text{PROVENANCE\_FORGED}}$ `INVALID`: Cryptographic check failed.
- `VALID` $\xrightarrow{\text{NEWER\_EXECUTION\_RECORDED}}$ `SUPERSEDED`: Replaced by a more comprehensive test run on the same commit.

### 4.4 Plan-as-Artifact State Machine

$$\mathcal{S}_{\text{PLAN}} = \{\text{DRAFT}, \text{UNDER\_REVIEW}, \text{VALIDATED}, \text{REJECTED}, \text{SUPERSEDED}\}$$

```text
[Planner Proposes] ──► DRAFT ──► [Submit for Review] ──► UNDER_REVIEW
                                                               │
                           ┌───────────────────────────────────┼───────────────────────────────────┐
                           ▼                                   ▼                                   ▼
                      VALIDATED                             REJECTED                          UNDER_REVIEW
                           │                                                            (Gathering Evidence)
                           ▼ (Replaced by new revision)
                      SUPERSEDED
```

- **Validation Invariant**: A plan moves to `VALIDATED` if and only if:
  $$\forall c \in \text{architecture\_claims}: (\text{Criticality}(c) \in \{\text{HIGH}, \text{CRITICAL}\} \implies \text{Status}(c) = \text{SUPPORTED}) \land \text{Conflicts}(\text{Plan}) = \emptyset$$

### 4.5 Controller Action Lifecycle State Machine

$$\mathcal{S}_{\text{CTRL}} = \{\text{PROPOSED}, \text{EVALUATING}, \text{AUTHORIZED}, \text{REJECTED}, \text{DEFERRED}\}$$

- `PROPOSED` $\to$ `EVALUATING`: Controller inspects preconditions, rate limits, permissions.
- `EVALUATING` $\to$ `AUTHORIZED`: All preconditions met $\to$ issue execution token.
- `EVALUATING` $\to$ `REJECTED`: Unauthorized, invariant violation, or invalid state.
- `EVALUATING` $\to$ `DEFERRED`: Dependencies pending or concurrency lock held.

---

## 5. Event Model & Deterministic Reduction Engine

### 5.1 Append-Only Event Log Specification

1. **Immutability**: Once appended, an event cannot be modified, deleted, or reordered.
2. **Digest Hash Chaining**: Every event envelope contains `parent_digest = SHA256(Event_{n-1})` and `digest = SHA256(Event_n)`.
3. **Total Ordering**: Sequence numbers are strictly monotonically increasing integers ($1, 2, 3, \dots$).

### 5.2 Canonical Event Catalog

| Event Name | Aggregate Type | Payload Content Summary |
| :--- | :--- | :--- |
| `TASK_CREATED` | Task | Task ID, raw prompt, repo commit SHA, constraints, environment. |
| `OBLIGATION_EXTRACTED` | Obligation | Obligation ID, parent ID, title, category, criticality, policy ID. |
| `OBLIGATION_DEPENDENCY_LINKED`| Obligation | Obligation ID, prerequisite Obligation ID. |
| `CLAIM_COMPILED` | Claim | Claim ID, Obligation ID, tier, subject, predicate, expected, criticality. |
| `ACTION_PROPOSED` | Plan/Action | Proposal ID, task ID, action type, target, purpose, resource limits. |
| `ACTION_AUTHORIZED` | Controller | Proposal ID, decision ID, execution token, timeout. |
| `ACTION_REJECTED` | Controller | Proposal ID, decision ID, rejection reason list. |
| `EVIDENCE_INGESTED` | Evidence | Evidence ID, claim ID, provider ID, observation, polarity, HMAC signature. |
| `CLAIM_REDUCED` | Claim | Claim ID, updated epistemic state (`SUPPORTED`, `CONTRADICTED`, `CONFLICTED`). |
| `OBLIGATION_ASSESSED` | Obligation | Obligation ID, assessment receipt, verdict (`SATISFIED`, `UNSATISFIED`). |
| `OBLIGATION_REOPENED` | Obligation | Obligation ID, mutation reason, invalidated claim IDs. |
| `PLAN_PROPOSED` | Plan | Plan ID, prompt, architecture claims, dependency graph. |
| `PLAN_VALIDATED` | Plan | Plan ID, validation receipt, timestamp. |
| `PLAN_REJECTED` | Plan | Plan ID, refuting evidence IDs, contradiction list. |

### 5.3 Deterministic Reduction Function

The system state $\mathcal{S}_t$ at sequence $t$ is a deterministic fold over the event log:

$$\mathcal{S}_0 = \emptyset$$
$$\mathcal{S}_{t+1} = \text{Reduce}(\mathcal{S}_t, \mathcal{E}_{t+1})$$

```python
def reduce_event(state: SystemState, event: EventEnvelope) -> SystemState:
    """
    Pure deterministic state reduction function.
    Must have zero side-effects, zero I/O, and zero non-deterministic calls.
    """
    event_type = event.event_type
    payload = event.payload
    
    if event_type == "CLAIM_COMPILED":
        claim_id = payload["claim_id"]
        state.claims[claim_id] = ClaimState(
            claim_id=claim_id,
            obligation_id=payload["obligation_id"],
            tier=payload["tier"],
            status=EpistemicStatus.UNSUPPORTED,
            evidence_refs=[]
        )
    elif event_type == "EVIDENCE_INGESTED":
        ev_id = payload["evidence_id"]
        claim_id = payload["claim_id"]
        state.evidence[ev_id] = payload
        
        claim = state.claims[claim_id]
        claim.evidence_refs.append(ev_id)
        
        # Deterministic Epistemic Reduction
        active_evidence = [state.evidence[eid] for eid in claim.evidence_refs if state.evidence[eid]["validity"] == "VALID"]
        has_supports = any(e["polarity"] == "SUPPORTS" for e in active_evidence)
        has_refutes = any(e["polarity"] == "REFUTES" for e in active_evidence)
        
        if has_supports and has_refutes:
            claim.status = EpistemicStatus.CONFLICTED
        elif has_refutes:
            claim.status = EpistemicStatus.CONTRADICTED
        elif has_supports:
            claim.status = EpistemicStatus.SUPPORTED
        else:
            claim.status = EpistemicStatus.UNSUPPORTED
            
    elif event_type == "OBLIGATION_REOPENED":
        obl_id = payload["obligation_id"]
        state.obligations[obl_id].status = ObligationStatus.REQUIRES_REASSESSMENT
        for cid in payload.get("invalidated_claim_ids", []):
            if cid in state.claims:
                state.claims[cid].status = EpistemicStatus.STALE

    return state
```

### 5.4 Contradictory Concurrent Writes Calculus

When concurrent workers submit opposing observations on the same claim $C$:
$$\text{Worker}_A \implies \text{Evidence}(\text{SUPPORTS}, C)$$
$$\text{Worker}_B \implies \text{Evidence}(\text{REFUTES}, C)$$

The Reducer reduces the state of $C$ to:
$$\text{Status}(C) = \text{CONFLICTED}$$

**Invariants**:
1. Neither write is dropped or overwritten.
2. The claim remains `CONFLICTED` until a formal diagnostic action resolves the dispute or identifies test flake / invalid assumptions.
3. No obligation depending on $C$ may transition to `SATISFIED` while $C$ is `CONFLICTED`.

---

## 6. Policy Grammar & Acceptance Calculus

### 6.1 Policy Hierarchy

Policies resolve in a non-weakening cascade:

$$\text{SYSTEM INVARIANTS} \xrightarrow{\text{bind}} \text{ORG POLICY} \xrightarrow{\text{bind}} \text{PROJECT POLICY} \xrightarrow{\text{bind}} \text{OBLIGATION POLICY}$$

$$\text{EffectivePolicy} = \text{SystemInvariants} \sqcap \text{OrgPolicy} \sqcap \text{ProjectPolicy} \sqcap \text{ObligationPolicy}$$

Where $\sqcap$ denotes rule intersection (strengthening). Lower levels may **add** requirements; they can **never waive or weaken** higher-level requirements.

### 6.2 Combinator Expressions

```text
<Expression> ::= ALL ( <Rule>+ )
               | ANY ( <Rule>+ )
               | AT_LEAST <Integer> INDEPENDENT_BY <GroupKey> ( <Rule>+ )
               | CONDITIONAL ( IF <Condition> THEN <Expression> ELSE <Expression> )

<Rule>       ::= REQUIRE_CAPABILITY ( <CapabilityName> )
               | REQUIRE_TIER ( <TierName> )
               | REQUIRE_EVIDENCE_COUNT ( <Integer> )
               | NO_CONFLICTS
               | NO_STALE_EVIDENCE
```

### 6.3 Universal Confidence Score Ban

> **CORE-08 Specification**: No floating-point metric (e.g., `confidence = 0.94`, `pass_ratio > 0.8`) may gate acceptance. Acceptance is strictly a discrete boolean evaluation over explicit policy predicates.

---

## 7. Claim & Evidence Epistemic Contract

### 7.1 Provider Capability Taxonomy & Registry

| Capability Name | Engine Providers | Supported Claim Tiers | Epistemic Scope |
| :--- | :--- | :--- | :--- |
| `PROPERTY_TESTING` | Hypothesis, SClassCleanRoom | $V_2$ Behavioral | Mathematical invariants, boundary shrinking |
| `API_CONTRACT_FUZZING` | Schemathesis | $V_0, V_2, V_3$ | OpenAPI / HTTP status / payload fuzzing |
| `STATIC_AST_ANALYSIS` | Ruff, Semgrep, LibCST | $V_1$ Structural | AST nodes, forbidden patterns, syntax |
| `TYPE_CHECK` | Pyright, Mypy | $V_1$ Structural | Strict typing, signature compatibility |
| `UNIT_TEST_EXECUTION`| Pytest | $V_0, V_2$ | Specific input/output examples, assertions |
| `SECURITY_SCAN` | OSV-Scanner, Semgrep | $V_1, V_3$ | CVE database lookups, security rules |
| `HUMAN_PROVENANCE` | S-Class Authorized Human | $V_4$ Judgment (only) | Cryptographically signed UX/Design approval |

### 7.2 Relevance Derivation Function

Relevance is evaluated deterministically by S-Class:

$$\mathcal{R}(C, E) = \mathbf{1}_{\text{CapabilityMatch}}(C, E) \times \mathbf{1}_{\text{ScopeMatch}}(C, E) \times \mathbf{1}_{\text{CommitMatch}}(E.\text{sha}, \text{HEAD}.\text{sha}) \times \mathbf{1}_{\text{SignatureValid}}(E)$$

If $\mathcal{R}(C, E) = 0$, the evidence is discarded as `IRRELEVANT` during claim assessment, regardless of whether its observation was `PASS`.

### 7.3 Multi-Dimensional Coverage Calculus

A claim $C$ specifies target aspects $\mathcal{A}(C) = \{a_1, a_2, \dots, a_n\}$. Evidence $E$ covers aspects $\mathcal{A}(E)$.

$$\text{Coverage}(C, \{E_1, \dots, E_k\}) = \begin{cases} \text{FULL} & \text{if } \mathcal{A}(C) \subseteq \bigcup_{i=1}^k \mathcal{A}(E_i) \\ \text{PARTIAL} & \text{if } \emptyset \subset \left( \mathcal{A}(C) \cap \bigcup_{i=1}^k \mathcal{A}(E_i) \right) \subset \mathcal{A}(C) \\ \text{NONE} & \text{if } \mathcal{A}(C) \cap \bigcup_{i=1}^k \mathcal{A}(E_i) = \emptyset \end{cases}$$

An obligation requiring full coverage **cannot close** if $\text{Coverage}(C) \ne \text{FULL}$.

### 7.4 Independence & Provenance Envelope

To satisfy `AT_LEAST k INDEPENDENT_BY group`, evidence items must have distinct group identifiers:
$$\text{DistinctSources}(\{E_1, \dots, E_m\}) = \left| \{ E_i.\text{provenance}.\text{group\_key} \}_{i=1}^m \right| \ge k$$

Two pytest runs on the same execution instance belong to the same group and count as $1$ independent source.

---

## 8. Planner / Controller Separation Contract

### 8.1 Core Axiom

> **"Planner proposes. Controller disposes."**
> No LLM, planner, or external agent may authorize or execute its own proposed actions.

```text
┌─────────────────┐       ActionProposal        ┌─────────────────┐
│     PLANNER     │ ──────────────────────────► │   CONTROLLER    │
│ (LLM / Reasoner)│                             │ (Deterministic) │
└─────────────────┘                             └────────┬────────┘
                                                         │
                                        ┌────────────────┴────────────────┐
                                        │ Checks:                         │
                                        │ 1. Obligation state == READY?   │
                                        │ 2. Preconditions met?           │
                                        │ 3. Within resource budget?      │
                                        │ 4. Permissions valid?           │
                                        │ 5. Action type authorized?      │
                                        └────────────────┬────────────────┘
                                                         │
                                        ┌────────────────┴────────────────┐
                                        ▼                                 ▼
                                   [REJECTED]                        [AUTHORIZED]
                                                                          │ (Issue Token)
                                                                          ▼
                                                                  [EXECUTION FABRIC]
```

### 8.2 Controller Verification Preconditions

1. **State Legality**: Target obligation must be in `READY` or `IN_PROGRESS`.
2. **Permission Check**: Action type must be permitted under the current active security profile.
3. **Resource Bound**: Estimated cost and timeout must not exceed remaining budget.
4. **Dependency Check**: All prerequisites listed in the proposal must be in `SATISFIED` state.

---

## 9. Plan-as-Artifact Contract (Recursive Self-Planning)

### 9.1 Self-Planning Epistemic Model

When S-Class is tasked with designing a new system or subsystem from scratch:
1. The Planner uses LLM reasoning to draft a candidate `Plan` artifact.
2. S-Class decomposes the candidate plan into structured **Architecture Claims** ($AC_1, AC_2, \dots, AC_m$).
3. The generated plan is placed in `DRAFT` state.
4. Evidence must be collected against every high-criticality architecture claim (structural reviews, boundary tests, dependency consistency checks).
5. The Assessment Engine evaluates the claims against policy.
6. The plan transitions to `VALIDATED` only when all architecture claims are proven and zero contradictions exist.

### 9.2 Plan Rejection & Revision Loop

```text
[Candidate Plan Proposed] ──► Claims Decomposed ──► Verification Run
                                                            │
                                  ┌─────────────────────────┴─────────────────────────┐
                                  ▼                                                   ▼
                            [Contradiction Found]                             [All Claims Supported]
                                  │                                                   │
                                  ▼                                                   ▼
                        PLAN = REJECTED / REVISE                              PLAN = VALIDATED
                                  │                                                   │
                                  ▼                                                   ▼
                        New Revision Emitted                                    Execution Unlocked
```

---

## 10. Provider Adapter Contract & Isolation Protocol

### 10.1 Abstract Base Provider Interface

```python
class EvidenceProvider(ABC):
    @abstractmethod
    def provider_id(self) -> str:
        """Unique provider identifier."""
        pass

    @abstractmethod
    def supported_capabilities(self) -> List[str]:
        """List of supported S-Class capabilities."""
        pass

    @abstractmethod
    def execute_and_collect(
        self,
        target: TargetSpec,
        claim: ClaimSpec,
        context: ExecutionContext
    ) -> NormalizedEvidence:
        """
        Execute tool in isolated child process and return normalized S-Class evidence.
        Must NEVER throw unhandled exceptions.
        """
        pass
```

### 10.2 Child Process Worker Isolation & HMAC Handshake

1. **Process Isolation**: All provider executions run in separate child processes with hard memory, CPU, and wall-clock timeout limits.
2. **HMAC-SHA256 Handshake**:
   - Parent generates ephemeral 32-byte secret $K$.
   - Child process executes tool and calculates observation digest: $D = \text{SHA256}(\text{RawOutput})$.
   - Child signs receipt: $\text{HMAC} = \text{HMAC-SHA256}(K, D \parallel \text{ExecutionID} \parallel \text{SourceSHA})$.
   - Parent verifies signature before accepting evidence into the event log.
3. **Rogue Child Protection**: Any child process output with invalid HMAC, mismatched SHA, or unhandled exit is mapped to `TOOL_EXECUTION_FAILED` with `NEUTRAL` polarity.

---

## 11. Dependency Graph, Concurrency & Staleness Engine

### 11.1 Directed Acyclic Graph (DAG) Model

Tasks and obligations form a strict DAG: $\mathcal{G} = (\mathcal{V}, \mathcal{E})$ where $\mathcal{V} = \text{Obligations}$ and $\mathcal{E} = \{ (u, v) \mid u \text{ depends on } v \}$.

- **Cycle Detection**: Attempting to insert an edge that creates a cycle triggers an immediate `CYCLIC_DEPENDENCY_ERROR` rejection.
- **Parallel Scheduling**: All obligations in in-degree 0 (relative to unsatisfied dependencies) can execute concurrently.

### 11.2 Kahn's Topological Sort & Parallel Scheduler

```python
def get_schedulable_obligations(dag: ObligationDAG, state: SystemState) -> List[Obligation]:
    schedulable = []
    for obl in dag.nodes:
        if state.obligations[obl.id].status == ObligationStatus.OPEN:
            dependencies_met = all(
                state.obligations[dep_id].status in (ObligationStatus.SATISFIED, ObligationStatus.CONDITIONAL)
                for dep_id in obl.depends_on
            )
            if dependencies_met:
                schedulable.append(obl)
    return schedulable
```

### 11.3 Staleness Propagation Algorithm

When a file or AST node $X$ is modified at commit $SHA_{new}$:

```text
Modified Code Artifact X
       ↓
Identify all Evidence E where X in E.scope.targets_evaluated
       ↓
Mark Evidence E as STALE
       ↓
Identify all Claims C referencing Evidence E
       ↓
Reduce state of Claim C -> STALE
       ↓
Identify all Obligations O containing Claim C
       ↓
Transition Obligation O -> REQUIRES_REASSESSMENT
       ↓
Emit Event OBLIGATION_REOPENED
```

---

## 12. Failure, Bounded Recovery & Regression Engine

### 12.1 Failure Classification & Root Cause Diagnosis

When evidence yields `REFUTES` on claim $C$:
1. Determine defect classification:
   - `SYNTAX_ERROR`: Code cannot be parsed.
   - `CONTRACT_VIOLATION`: Input/output expectation failed.
   - `INVARIANT_BREAK`: Property fuzzer found counterexample.
   - `REGRESSION_DEFECT`: Previously working behavior broken by recent edit.
2. Mint a **Repair Obligation** ($O_{\text{repair}}$) with `depends_on = [OriginalObligation]`.

### 12.2 Bounded Recovery Loop

To prevent infinite autonomous repair loops:

$$\text{AttemptCount}(O) \le \text{MAX\_REPAIR\_ATTEMPTS} \quad (\text{default: } 3)$$
$$\text{CostAccumulated}(O) \le \text{MAX\_REPAIR\_BUDGET\_USD} \quad (\text{default: } \$2.00)$$
$$\text{RecursionDepth}(O) \le \text{MAX\_REPAIR\_DEPTH} \quad (\text{default: } 2)$$

If any bound is exceeded:
$$\text{ObligationState} \to \text{BLOCKED} \implies \text{Trigger Human Escalation (§12.4)}$$

### 12.3 Mandatory Regression Loop

After a successful repair patch is applied:
1. The target claim $C_{\text{target}}$ is re-verified.
2. The Dependency Engine identifies all related claims $\mathcal{N}(C_{\text{target}})$ across the repository.
3. The Regression Suite for $\mathcal{N}(C_{\text{target}})$ is executed.
4. The repair obligation can close if and only if:
   $$\text{Status}(C_{\text{target}}) = \text{SUPPORTED} \land \forall c \in \mathcal{N}(C_{\text{target}}): \text{Status}(c) \ne \text{CONTRADICTED}$$

### 12.4 Controlled Human Escalation Protocol

Humans are registered in S-Class as **controlled, provenance-bearing evidence actors**.
- Human actions must be cryptographically signed with the human's authorized key.
- Human decisions cannot waive Tier $V_0$–$V_3$ deterministic failures without an explicit Policy Exception Record (§3.4.2).

---

## 13. Security Boundaries & Core Invariants

The following 21 Core Invariants are mathematically formalized and enforced across all layers:

| ID | Invariant Name | Mathematical / Formal Specification | Verification Checkpoint |
| :--- | :--- | :--- | :--- |
| **CORE-01** | Obligation Centricity | $\forall \text{Action } a: \exists \text{Obligation } o \text{ s.t. } a \in \text{Plan}(o)$ | Controller Precondition |
| **CORE-02** | Claim Formalism | $\forall \text{Claim } c: c = \langle \text{Subject}, \text{Predicate}, \text{Context}, \text{Expected}, \text{Tier} \rangle$ | Claim Compiler Validator |
| **CORE-03** | Evidence as 1st-Class | $\forall \text{Evidence } e: \text{SchemaValid}(e) \land \text{DigestValid}(e)$ | Evidence Ingestion Gate |
| **CORE-04** | Policy Gated Acceptance| $\text{ObligationClosed}(o) \iff \text{PolicyEvaluate}(\text{Policy}(o), \text{State}) = \text{SATISFIED}$ | Assessment Reducer |
| **CORE-05** | Planner Proposes / Controller Disposes | $\text{ExecutionAllowed}(a) \iff \text{ControllerVerdict}(a) = \text{APPROVED}$ | Execution Dispatcher |
| **CORE-06** | Explicit Provenance | $\forall e \in \text{Evidence}: e.\text{signature}.\text{hmac} = \text{HMAC}(K, e.\text{digest} \parallel e.\text{sha})$ | Provider Adapter Ingestion |
| **CORE-07** | Relevance & Coverage | $\text{Supports}(e, c) \implies \mathcal{R}(c, e) = 1 \land \text{Coverage}(c, e) > 0$ | Epistemic Reducer |
| **CORE-08** | No Confidence Score | $\forall p \in \text{Policies}: \text{Formula}(p) \text{ uses only } \{\text{ALL}, \text{ANY}, \text{AT\_LEAST}, \text{CONDITIONAL}\}$ | Policy Parser Linter |
| **CORE-09** | Immutable Event History| $\forall t: \text{Digest}(\mathcal{E}_t) = \text{SHA256}(\mathcal{E}_t \parallel \text{Digest}(\mathcal{E}_{t-1}))$ | Event Log Hash Chain |
| **CORE-10** | Deterministic Reducer | $\text{Reduce}(S, E) \text{ is a pure mathematical function with zero I/O}$ | Cleanroom Replay Suite |
| **CORE-11** | Explicit Contradiction | $(\text{Supports}(e_1, c) \land \text{Refutes}(e_2, c)) \implies \text{Status}(c) = \text{CONFLICTED}$ | Epistemic Reducer |
| **CORE-12** | Dependency Staleness | $\text{Mutated}(X) \implies \forall e \in \text{Scope}(X): e.\text{validity} = \text{STALE}$ | Staleness Engine |
| **CORE-13** | Parallel Obligation DAG| $\text{IsDAG}(\mathcal{G}) \land \forall (u, v) \in \mathcal{E}: \text{Schedule}(u) \text{ after } \text{Satisfied}(v)$ | DAG Scheduler |
| **CORE-14** | External Tool Adapters | All external OSS tools interact strictly through normalized adapter interfaces | Adapter Sandbox Gate |
| **CORE-15** | Fail-Closed Acceptance | $\text{EvaluationUnknown}(c) \implies \text{ObligationStatus} \ne \text{SATISFIED}$ | Assessment Engine |
| **CORE-16** | Bounded Recovery | $\text{RepairLoopCount}(o) \le \text{MAX\_RETRIES} \implies \text{Terminates or Blocks}$ | Recovery Controller |
| **CORE-17** | Mandatory Regression | $\text{RepairApplied}(X) \implies \text{ExecuteRegressionSuite}(\text{Dependents}(X))$ | Recovery Engine |
| **CORE-18** | Human Provenance | $\text{HumanOverride} \implies \text{ValidSignature} \land \text{SignedExceptionRecord}$ | Policy Exception Gate |
| **CORE-19** | Non-Weakening Policy | $\text{EffectivePolicy} = \text{System} \sqcap \text{Org} \sqcap \text{Project} \sqcap \text{Obligation}$ | Policy Compiler |
| **CORE-20** | Unknown Stays Unknown | Absence of evidence yields `UNSUPPORTED`, never `SUPPORTED` | Epistemic Reducer |
| **CORE-21** | Governed Self-Planning | $\forall \text{Plan } P: P \text{ is governed by Architecture Claims before validation}$ | Self-Planning Module |

---

## 14. Test Architecture & Adversarial Verification Matrix

### 14.1 Test Hierarchy

```text
Tier 1: Schema & Contract Tests (Pydantic / JSONSchema strict validation)
Tier 2: Clean-Room Deterministic Reducer Tests (Property & Invariant tests)
Tier 3: Provider Adapter Isolation & Handshake Tests (HMAC, process bounds)
Tier 4: State Machine & DAG Scheduler Concurrency Tests (Thread & Process safety)
Tier 5: Policy Calculus & Non-Weakening Tests (Mutation & Metamorphic tests)
Tier 6: Adversarial Red-Team Injection Suite (16 Attack Vectors)
```

### 14.2 Adversarial Red-Team Attack Vector Suite

| Attack ID | Attack Vector Description | Expected System Defense Behavior | Invariant Enforced |
| :--- | :--- | :--- | :--- |
| **ADV-01** | Rogue provider sends fake `PASS` with invalid HMAC signature | Evidence immediately rejected as `INVALID`; mapped to `TOOL_OUTPUT_INVALID` | CORE-06 |
| **ADV-02** | Stale evidence replayed against newer repository commit SHA | Scope check detects SHA mismatch $\to \mathcal{R}(C, E) = 0 \to$ Discarded | CORE-06, CORE-12 |
| **ADV-03** | Scope mismatch (Evidence tests `GET /users`, Claim is `DELETE /users`) | Scope resolver detects target mismatch $\to \mathcal{R}(C, E) = 0$ | CORE-07 |
| **ADV-04** | Concurrent contradictory writes (Worker A `SUPPORTS`, Worker B `REFUTES`) | Reducer produces `CONFLICTED` state; neither write dropped | CORE-10, CORE-11 |
| **ADV-05** | Policy downgrade attempt (Project policy tries to remove security scan) | Policy compiler calculates intersection $\sqcap$; mandatory rule preserved | CORE-19 |
| **ADV-06** | Autonomous infinite repair loop injection (perpetually failing test) | Bounded recovery exhausts budget $\to$ Transitions to `BLOCKED` and alerts | CORE-16 |
| **ADV-07** | Self-planning generated plan omitting mandatory security obligations | Assessment engine detects missing mandatory claims $\to \text{Plan } = \text{REJECTED}$ | CORE-21 |
| **ADV-08** | Cyclic dependency injection into Obligation DAG | DAG compiler rejects insertion with `CYCLIC_DEPENDENCY_ERROR` | CORE-13 |
| **ADV-09** | Replayed event log with mutated parent digest | Hash chain validation fails $\to$ Event Store halts on corrupted state | CORE-09 |
| **ADV-10** | Floating-point confidence score passed to gate obligation | Policy parser rejects score; throws `INVALID_POLICY_EXPRESSION_ERROR` | CORE-08 |
| **ADV-11** | Unprivileged LLM planner attempting to execute unauthorized shell tool | Controller intercepts proposal $\to$ Verdict: `REJECTED` | CORE-05 |
| **ADV-12** | Partial coverage masquerading as full coverage | Multi-dimensional coverage calculus evaluates `PARTIAL` $\to$ Close blocked | CORE-07 |
| **ADV-13** | Duplicate provider results masquerading as independent sources | Independence deduplication collapses runs into single group $\to$ Policy fails | CORE-04, CORE-07 |
| **ADV-14** | Code edit applied without running regression suite | Assessment engine flags missing regression evidence $\to$ Closing blocked | CORE-17 |
| **ADV-15** | Forged human approval without valid cryptographic signature | Signature verification fails $\to$ Exception rejected $\to$ Obligation stays open | CORE-18 |
| **ADV-16** | Replay of historical state with non-deterministic timestamps | Reducer uses event log timestamps strictly; produces identical bit-for-bit state | CORE-10 |

---

## 15. D0 Freeze Certification

### 15.1 Contract Sign-Off

The D0 contracts specified in this document (`SCLASS_CORE_SPECIFICATION.md`) are hereby:

$$\mathbf{FROZEN} \quad \text{as of 2026-08-17}$$

- **Single Source of Truth**: This document represents the frozen contract governing all subsequent layers (D1–D12).
- **Zero Drift Guarantee**: No implementation code in D1 through D12 may alter these domain schemas, state transition tables, policy calculi, or core invariants without an explicit update to this specification and the Master Plan.

---
*(End of Canonical D0 Specification)*
