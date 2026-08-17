# S-Class — Master System Design & Build Plan
### (Single Source of Truth — supersedes all prior drafts)

> Rule for this document: this is the **only** design file. No parallel or partial versions. Any future change updates this file directly.

---

## 1. Product Definition

S-Class is:

> A governance and assurance layer for AI coding agents that makes them follow a disciplined software-engineering process: understand requirements, derive obligations, plan, implement, verify, diagnose, repair, regression-check, and close only when the required evidence satisfies explicit acceptance policy.

It is **not**:

- another LLM coding agent
- another test framework
- another static analyzer
- another Semgrep / Schemathesis / Hypothesis clone
- an autonomous agent that blindly controls everything

**The AI agent remains the worker. S-Class is the engineering discipline around the worker.**

---

## 2. The Central Model

```text
TASK
  ↓
OBLIGATIONS
  ↓
CLAIMS
  ↓
POLICY
  ↓
ACTIONS
  ↓
EVIDENCE
  ↓
ASSESSMENT
  ↓
REPAIR / ACCEPT
```

Underneath everything:

```text
EVENTS + PROVENANCE + DEPENDENCIES
```

---

## 3. High-Level Architecture

```text
                         ┌───────────────────────┐
                         │     AI CODING AGENT    │
                         │   LLM / IDE / Agent    │
                         └───────────┬───────────┘
                                     │ proposals/actions
                                     ▼
┌────────────────────────────────────────────────────────────────────┐
│                         S-CLASS CORE                                │
│                                                                       │
│  1. TASK & CONTEXT                                                  │
│  2. OBLIGATION ENGINE                                               │
│  3. CLAIM ENGINE                                                    │
│  4. POLICY ENGINE                                                   │
│  5. PLANNER / REASONER                                              │
│  5b. SELF-PLANNING / PLAN-AS-ARTIFACT MODEL                         │
│  6. DETERMINISTIC CONTROLLER                                        │
│  7. EXECUTION / TOOL FABRIC                                         │
│  8. EVIDENCE ENGINE                                                  │
│  9. CLAIM/EVIDENCE REDUCER                                          │
│ 10. ASSESSMENT ENGINE                                                │
│     ├── ACCEPT                                                      │
│     └── RECOVER ──► PLANNER                                         │
│ 11. EVENT / AUDIT / PROVENANCE STORE                                │
└────────────────────────────────────────────────────────────────────┘
              │                    │                    │
              ▼                    ▼                    ▼
          pytest             Schemathesis          Semgrep
          Hypothesis          OSV-Scanner           Ruff
          Pyright             fuzzers               other tools
```

---

## 4. Ownership Boundary

| Component | S-Class owns? |
|---|---|
| Requirement interpretation | Yes |
| Obligation graph | Yes |
| Claim semantics | Yes |
| Acceptance policy | Yes |
| Planning (incl. self-planning) | Yes |
| Action authorization | Yes |
| Evidence normalization | Yes |
| Evidence provenance | Yes |
| Claim/evidence relationships | Yes |
| Staleness | Yes |
| Conflict handling | Yes |
| Audit trail | Yes |
| Code generation | No |
| Static-analysis implementation | No |
| Property-testing implementation | No |
| API fuzzing implementation | No |
| Dependency vulnerability database | No |
| Sandbox implementation | No |

This boundary prevents scope explosion — including when S-Class is asked to design its own execution plan (see §12).

---

## 5. Task Model

```yaml
task:
  id: TASK-001
  request: "Add authentication to the API."
  repository:
    revision: abc123
  constraints:
    language: python
    framework: fastapi
  environment:
    ...
```

The request is not yet executable. It is raw input to the Obligation Engine.

---

## 6. Obligation Engine

A task becomes an obligation graph.

```text
TASK
 │
 ├── O1 Authentication behavior
 │    ├── C1 unauthorized request rejected
 │    ├── C2 authorized request accepted
 │    └── C3 privilege escalation prevented
 │
 ├── O2 Backward compatibility
 │    ├── C4 existing API preserved
 │    └── C5 existing clients continue working
 │
 └── O3 Security
      ├── C6 credentials handled safely
      └── C7 forbidden access paths blocked
```

**Key property:** nothing important is allowed to disappear merely because the coding agent forgets it later.

---

## 7. Claim Engine

Claims are structured propositions with subject, predicate, context, expected outcome, and criticality.

```yaml
claim:
  id: C1
  subject:
    endpoint: DELETE:/users/{id}
  predicate:
    type: UNAUTHORIZED_REQUEST_REJECTED
  context:
    identity: NON_ADMIN
  expected:
    status: 403
  criticality: HIGH
```

The claim can then be mechanically related to evidence.

### Claim Taxonomy (kept deliberately small in v1)

- **V0 — Observable:** HTTP status, return value, exit code, file existence
- **V1 — Structural:** AST property, schema property, dependency constraint, type property
- **V2 — Behavioral:** invariant, idempotency, concurrency, error behavior
- **V3 — System-level:** backward compatibility, cross-component invariant, workflow behavior
- **V4 — Judgment:** maintainability, design quality, usability

**V4 is explicitly never treated as equivalent to deterministic proof**, and can never by itself satisfy a mandatory obligation — it requires either supplementary lower-tier evidence or explicit human-authorized exception (§10).

---

## 8. Policy Engine

```text
IMMUTABLE S-CLASS INVARIANTS
            ↓
ORGANIZATION POLICY
            ↓
PROJECT POLICY
            ↓
OBLIGATION REQUIREMENTS
            ↓
EFFECTIVE POLICY
```

Lower levels may **strengthen** requirements. They cannot **weaken** mandatory higher-level rules.

### Worked example

```text
Organization: Security obligations require runtime verification.
Project:      Unit tests are preferred.
Obligation:   Verify unauthorized DELETE behavior.

Effective policy:
  runtime verification → REQUIRED
  unit test            → ADDITIONAL
```

The agent cannot simply declare "unit test passed, therefore security obligation closed" — the effective policy demands runtime verification regardless of what the agent prefers.

---

## 9. Policy Exceptions

Exceptions are first-class but controlled — never a silent bypass.

```text
REQUEST
  ↓
JUSTIFICATION
  ↓
AUTHORIZED DECISION
  ↓
CONDITIONAL ACCEPTANCE
```

Each exception record contains:

- reason
- authority (who approved it)
- scope (exactly what it covers)
- expiry
- compensating controls

---

## 10. Planner

The planner answers: **"What should we do next?"**

It may use an LLM and dynamic reasoning, and may choose among many strategies. Its output is only a **proposal**.

```yaml
proposal:
  action: RUN_API_CONTRACT_TESTS
  target: API
  reason: "Claim C4 lacks behavioral evidence."
```

---

## 11. Self-Planning / Plan-as-Artifact Model

*(New in this revision — the recursive capability that lets S-Class harness the core LLM's own reasoning to design a build plan from scratch, without surrendering governance.)*

### 11.1 Why this exists

Two different capabilities need to be kept distinct:

**(a) Task-level planning (already covered in §10).** Given "add authentication to this API," S-Class derives obligations → claims → evidence requirements → an execution plan for *that task*.

**(b) Product-level self-planning.** Given "build this system from scratch" (e.g., the very prompt that produced this document), S-Class should eventually be able to generate its own:

```text
Requirements
      ↓
Architecture
      ↓
Subsystems
      ↓
Dependencies
      ↓
Implementation phases
      ↓
Interfaces
      ↓
Testing strategy
      ↓
Security strategy
      ↓
Milestones
      ↓
Execution plan
```

...and then continuously revise that plan as evidence accumulates.

This is powerful because it harnesses the core LLM's general reasoning to do something no rule-based system can do: **draft a full system design from an ambiguous prompt.** But it is dangerous if that generated plan is treated as automatically correct just because an LLM produced it. A self-designed architecture is exactly the kind of judgment-heavy (V4) artifact that must never masquerade as deterministic truth (see §7).

### 11.2 The core principle

> **A plan generated by S-Class is not a privileged artifact. It is just another claim-bearing object, subject to the same governance as any AI-proposed action.**

This closes the obvious loophole: without this rule, an LLM-run planner could design its own architecture and then simply declare that architecture correct — grading its own homework. Instead:

```text
S-Class Planner (LLM reasoning)
      │
      │ proposes a candidate PLAN
      ▼
PLAN becomes a set of ARCHITECTURE CLAIMS
      │
      ▼
Verification / Evidence gathering against those claims
      │
      ├── contradiction found
      ├── missing requirement found
      ├── infeasible dependency found
      └── security or policy problem found
             │
             ▼
        REVISE THE PLAN
             │
             ▼
      VALIDATED PLAN (governed artifact)
```

### 11.3 Plan-as-Artifact schema

A generated plan is stored the same way any other epistemic object is stored — as claims backed (or refuted) by evidence, not as free-form prose.

```yaml
plan:
  id: PLAN-001
  origin: SELF_PLANNING
  source_prompt: "Design and build S-Class from scratch."
  status: DRAFT   # DRAFT | UNDER_REVIEW | VALIDATED | REJECTED | SUPERSEDED

  architecture_claims:
    - id: AC1
      subject: "Planner / Controller separation"
      predicate: PREVENTS_UNAUTHORIZED_ACTION
      criticality: HIGH
      evidence_required:
        - TYPE: STRUCTURAL_REVIEW      # V1
        - TYPE: ADVERSARIAL_TEST       # V2/V3

    - id: AC2
      subject: "Event-sourced reducer with CONFLICTED state"
      predicate: NO_SILENT_DATA_LOSS_ON_CONCURRENT_WRITES
      criticality: HIGH
      evidence_required:
        - TYPE: CONCURRENCY_TEST       # V2

  dependency_graph: ...
  milestone_sequence: ...
  open_risks:
    - "Adapter contract not yet specified — blocks D6."
  contradictions: []
  revision_of: null
```

### 11.4 How self-planning stays inside S-Class's ownership boundary (§4)

The LLM is still only a **worker** at this layer too — it drafts candidate architecture; it does not get to decide the architecture is acceptable. Concretely:

| Sub-step | Who performs it |
|---|---|
| Generate candidate architecture / phase breakdown | LLM (Planner) |
| Decompose the plan into architecture claims | LLM proposes, S-Class schema enforces structure |
| Decide what evidence would validate/refute each claim | S-Class (deterministic — same claim taxonomy as §7) |
| Actually gather that evidence (reviews, prototypes, adversarial tests) | Execution/Tool Fabric (§13) + human reviewers as evidence providers (§29) |
| Decide whether the plan is VALIDATED | Assessment Engine + Policy Engine, **not the LLM** |
| Revise the plan on contradiction | LLM (Planner), triggering a new PLAN version |

### 11.5 Plan lifecycle states

```text
DRAFT → UNDER_REVIEW → VALIDATED
                     ↘ REJECTED
VALIDATED → SUPERSEDED   (when a later revision replaces it)
```

A plan can only move from `UNDER_REVIEW` to `VALIDATED` when every `HIGH`-criticality architecture claim has satisfying evidence and there are zero unresolved `CONFLICTED` claims — exactly the same acceptance discipline used for ordinary task obligations (§18–20). Nothing about self-planning gets a shortcut.

### 11.6 Why this matters for the "build from scratch" use case

This is what lets you eventually say to S-Class:

> "Design and build a new subsystem / product from scratch."

...and have it produce a *governed* plan rather than a persuasive-sounding but unverified one. The LLM's reasoning is fully harnessed for the creative/generative part (drafting architecture, breaking down phases, spotting dependencies) — but the resulting plan earns trust the same way any other claim earns trust in this system: **by being checked, not by being fluent.**

This section must be implemented as part of D8 (Planner) at the earliest, and the plan-as-artifact schema must be frozen as part of D0, because the Controller, Assessment Engine, and Event Store all need to know how to treat a `PLAN` object before the Planner can safely emit one.

---

## 12. Controller

The controller answers: **"Is this action legal and valid in the current state?"**

```text
Planner
   ↓
Proposal
   ↓
Controller
   ├── prerequisites?
   ├── policy?
   ├── dependencies?
   ├── permissions?
   ├── resource limits?
   └── state transition valid?
        ↓
     APPROVE / REJECT / DEFER
```

> **Core rule: Planner proposes. Controller disposes.**

This applies identically whether the proposal is an ordinary task action or a self-generated architecture plan (§11).

---

## 13. Execution Layer

```text
Controller → Execution Adapter → Tool / Agent / Sandbox → Raw result
```

Execution can involve: the AI coding agent, pytest, Hypothesis, Schemathesis, Semgrep, Ruff, Pyright, OSV-Scanner, fuzzing, build systems, Git operations, and other approved providers.

---

## 14. OSS Integration Strategy

We integrate mature tools. We do not recreate them.

```text
S-Class
   ↓
Provider Interface
   ├── Hypothesis
   ├── Schemathesis
   ├── Semgrep
   ├── OSV
   ├── Ruff
   ├── Pyright
   ├── fuzzing
   └── future tools
```

Each provider produces normalized S-Class evidence.

### The strategic difference

Semgrep answers: *"What did my analyzer find?"*

S-Class answers: *"Was this verification required, was it executed against the correct obligation, what does the result actually establish, is it current, and can this obligation now close?"*

**That's the moat.**

### OSS provider ecosystem (target shape)

```text
                S-CLASS
                   │
        ┌──────────┼───────────┐
        │          │           │
      CODE       API        SECURITY
        │          │           │
  Ruff/Pyright  Schemathesis   OSV
   Semgrep       Contract    Semgrep
        │
        ▼
    BEHAVIOR
        │
 pytest/Hypothesis
        │
        ▼
     FUZZING
```

We don't need every tool on day one — the architecture just makes adding them cheap.

---

## 15. Evidence Engine

Raw output becomes normalized evidence.

```yaml
evidence:
  id: EV-102
  provider: SCHEMATHESIS
  capability: API_CONTRACT
  execution:
    id: EXEC-55
  revision:
    sha: abc123
  scope:
    endpoints:
      - POST:/users
  observation:
    status: PASS
  polarity: SUPPORTS
  provenance:
    environment: ...
    timestamp: ...
```

---

## 16. Evidence Validation

```text
Raw Result
   ↓
Provider Validation
   ↓
Capability Validation
   ↓
Provenance Validation
   ↓
Revision Validation
   ↓
Scope Validation
   ↓
Evidence Record
```

A provider cannot simply say "PASS" and have S-Class accept it blindly.

---

## 17. Relevance

Relevance is derived from: **Claim + Provider capability + Actual execution scope + Context + Revision + Provenance.**

Not: *"the LLM says this evidence is relevant."*

### Worked example

```text
Claim:    DELETE /users must reject non-admins
Evidence: GET /users tested by pytest

Result: IRRELEVANT — even if the test passed.
```

---

## 18. Coverage

A claim can have partial coverage.

```text
Claim:    Cache is thread-safe and idempotent.
Evidence: Concurrent test passed.

Result:
  Thread safety → FULL
  Idempotency   → NONE
  Overall       → PARTIAL
```

Therefore the obligation cannot close if full coverage is required.

---

## 19. Evidence Combination

Use explicit policy expressions — **never** a universal numerical confidence score as a substitute for acceptance logic.

```text
ALL
ANY
AT_LEAST
CONDITIONAL
```

```text
ALL(
    schema_check,
    integration_test,
    regression_test
)
```

There is no `confidence = 0.93` used to gate closure.

---

## 20. Evidence Polarity

Evidence can `SUPPORT`, `REFUTE`, or remain `NEUTRAL`.

```text
EV1 → SUPPORT
EV2 → REFUTE
        ↓
CLAIM = CONFLICTED
```

Not: "5 green tests > 1 red test."

---

## 21. Evidence Independence

Evidence carries provenance groups so duplicate sources don't masquerade as independent confirmation.

```text
EV1  provider = pytest, execution = 10
EV2  provider = pytest, execution = 10
```

These do **not** automatically count as two independent sources. Policies can require:

```text
AT_LEAST 2
INDEPENDENT_BY provider
```

---

## 22. Claim / Evidence Store

```text
append-only events
        ↓
deterministic reducer
        ↓
canonical materialized state
```

Workers never directly overwrite canonical epistemic state.

### Events

```text
CLAIM_CREATED
CLAIM_UPDATED
EVIDENCE_ADDED
EVIDENCE_REFUTES
EVIDENCE_INVALIDATED
EVIDENCE_SUPERSEDED
CLAIM_REASSESSED
OBLIGATION_REOPENED
OBLIGATION_CLOSED
PLAN_PROPOSED
PLAN_REVISED
PLAN_VALIDATED
PLAN_REJECTED
```

*(The last four support the Self-Planning model in §11.)*

---

## 23. Contradictory Concurrent Writes

```text
Worker A: SUPPORT C1
Worker B: REFUTE  C1
              ↓
Reducer: C1 = CONFLICTED
```

No last-write-wins. No lost information.

---

## 24. Staleness

Evidence doesn't become stale merely because it's old — dependency changes cause invalidation.

```text
source
  ↓
evidence
  ↓
claim
  ↓
obligation
```

```text
source changed
     ↓
affected evidence
     ↓
affected claims
     ↓
affected obligations
```

Only affected state is reassessed.

### States

```text
Evidence:    VALID | STALE | INVALID | SUPERSEDED
Claim:       UNSUPPORTED | SUPPORTED | CONTRADICTED | CONFLICTED | STALE
Obligation:  OPEN | READY | IN_PROGRESS | SATISFIED | BLOCKED | CONDITIONAL | REQUIRES_REASSESSMENT
```

---

## 25. Failure / Recovery Engine

```text
verification
     ↓
FAIL
     ↓
diagnose
     ↓
identify failed claim
     ↓
create repair obligation
     ↓
planner
     ↓
repair proposal
     ↓
controller
     ↓
execute
     ↓
verify
```

---

## 26. Regression Loop

```text
target verification
       ↓
dependency analysis
       ↓
affected claims
       ↓
regression verification
       ↓
assessment
```

A fix that solves A but breaks B does not close the task.

---

## 27. Bounded Autonomy

Every action carries:

```text
actor
target
purpose
prerequisites
permissions
resource limits
expected observations
transition
```

And repair has a bounded budget:

```text
max attempts
max execution time
max cost
max recursive repair depth
```

Eventually: `BLOCKED / ESCALATE` — never an infinite autonomous loop.

---

## 28. Human Interaction

Humans are not outside the architecture — they are another **controlled actor / evidence provider**.

```text
AI
 ↓
S-Class
 ↓
human escalation
 ↓
human decision/evidence
 ↓
policy evaluation
```

Human approval is **provenance-bearing**. It is not a magic override — it still flows through the same evidence validation pipeline (§16).

---

## 29. Audit System

Every significant decision generates a receipt.

```yaml
evaluation:
  obligation: OBL-17
  policy_version: POL-8
  repository_revision: abc123
  result: SATISFIED
  predicates:
    - id: C1
      result: PASS
      evidence: [EV-90]
    - id: C2
      result: PASS
      evidence: [EV-93]
  conflicts: []
  stale_evidence: []
  evaluated_at: ...
```

Anyone should be able to answer *"why did S-Class allow this task to close?"* without asking the LLM.

---

## 30. Full Runtime Flow

```text
                    USER TASK
                       │
                       ▼
                 ┌───────────┐
                 │ INGESTION │
                 └─────┬─────┘
                       ▼
                 CONTEXT MODEL
                       │
                       ▼
              OBLIGATION EXTRACTION
                       │
                       ▼
                CLAIM COMPILATION
                       │
                       ▼
                POLICY COMPILATION
                       │
                       ▼
                OBLIGATION GRAPH
                       │
                       ▼
                     PLAN  ◄── (may itself be a governed PLAN artifact, §11)
                       │
                       ▼
                ACTION PROPOSAL
                       │
                       ▼
                  CONTROLLER
                  /         \
             REJECT         APPROVE
                              │
                              ▼
                         EXECUTION
                              │
                              ▼
                           OBSERVE
                              │
                              ▼
                         EVIDENCE
                              │
                              ▼
                     EVIDENCE VALIDATION
                              │
                              ▼
                    CLAIM/EVIDENCE REDUCER
                              │
                              ▼
                         ASSESSMENT
                       /      |       \
                    PASS     FAIL    UNKNOWN
                     │        │         │
                     │        ▼         ▼
                     │     DIAGNOSE   GATHER
                     │        │       EVIDENCE
                     │        ▼         │
                     │      REPAIR ◄────┘
                     │        │
                     │        ▼
                     │     VERIFY
                     │        │
                     └────────┘
                          │
                          ▼
                    REGRESSION CHECK
                          │
                          ▼
                     FINAL ASSESSMENT
                       /        \
                    CLOSE       BLOCK
```

---

## 31. Parallel Execution

Obligations form a DAG.

```text
             O1
            /  \
           O2  O3
           │    │
           └─┬──┘
             ▼
             O4
```

Independent obligations (`O2 || O3`) execute concurrently; dependent obligations (`O1 → O2`) wait. All state updates go through the canonical event/reducer path.

---

## 32. Repository Architecture

```text
sclass/
├── core/
│   ├── contracts/
│   ├── task/
│   ├── obligations/
│   ├── claims/
│   ├── policy/
│   ├── planner/
│   │   └── self_planning/      # plan-as-artifact model, §11
│   ├── controller/
│   ├── execution/
│   ├── evidence/
│   ├── assessment/
│   ├── state/
│   └── audit/
├── adapters/
│   ├── pytest/
│   ├── hypothesis/
│   ├── schemathesis/
│   ├── semgrep/
│   ├── ruff/
│   ├── pyright/
│   ├── osv/
│   └── fuzzing/
├── runtime/
│   ├── scheduler/
│   ├── sandbox/
│   ├── resources/
│   └── workers/
├── interfaces/
│   ├── cli/
│   ├── sdk/
│   └── api/
├── storage/
│   ├── events/
│   ├── projections/
│   └── artifacts/
├── tests/
├── benchmark/
└── docs/
```

---

## 33. API Boundary

The agent interacts with S-Class through a small protocol. Endpoints follow the domain schemas — not the other way around.

```text
task     = sclass.create_task(...)
plan     = sclass.get_next_action()
decision = sclass.submit_action_result(...)
evidence = sclass.submit_evidence(...)
state    = sclass.assess()

if state.repair_required:
    ...

# Self-planning extension
draft_plan = sclass.propose_plan(prompt="Design subsystem X from scratch")
validated  = sclass.assess_plan(draft_plan.id)
```

The exact API is finalized only after the domain schemas are frozen.

---

## 34. Build Roadmap

### D0 — Design Freeze
Freeze: architecture, domain objects, state machines, policy semantics, evidence semantics, event model, concurrency semantics, adapter contract, failure semantics, security boundaries, **and the plan-as-artifact schema (§11.3)**.

**Deliverable: `SCLASS_CORE_SPECIFICATION.md`**

### D1 — Domain Kernel
Task, Obligation, Claim, Policy, Evidence, Evaluation, Event. No LLM. No external tools. No fancy UI. Everything deterministic.

### D2 — State & Event Engine
Event store, reducer, versioning, dependency graph, staleness propagation, conflict handling, idempotency, concurrency.

### D3 — Policy Engine
Hierarchy, acceptance expressions, mandatory requirements, criticality, exceptions, policy versions, fail-closed behavior. Mutation-test it aggressively.

### D4 — Claim / Evidence Engine
Claim contracts, claim decomposition, provider capabilities, scope matching, relevance, coverage, polarity, provenance, evidence combination, evaluation receipts. At this point S-Class can reason about evidence without executing any code.

### D5 — Controller
Deterministic state machine: proposal → preconditions → authorization → execution → observation → transition. No autonomous planner yet. Test it heavily.

### D6 — Tool Adapter Fabric
Start with the highest-value providers. Existing Hypothesis and Schemathesis work becomes provider infrastructure. Likely sequence: pytest → Ruff/Pyright → Semgrep → OSV-Scanner → additional fuzzing. Exact order determined by the claims the prototype needs to support.

### D7 — Coding Agent Integration
Connect an actual AI coding agent. It receives: current objective, relevant obligations, constraints, approved action, verification feedback. It does not need internal S-Class implementation details.

### D8 — Planner (incl. Self-Planning)
Give the planner open obligations, failed claims, available tools, evidence, dependencies, cost, and history — it proposes; the controller validates. **This phase also implements the Self-Planning / Plan-as-Artifact model (§11):** the planner may draft a full product/subsystem plan from an ambiguous prompt, but that plan is decomposed into architecture claims and validated through the normal evidence pipeline before it is trusted.

### D9 — Recovery & Regression
Failure diagnosis, repair planning, bounded retries, impact analysis, regression verification, escalation.

### D10 — Prototype
Demonstrate one complete task end-to-end:

```text
feature request
→ obligations
→ AI implementation
→ verification
→ defect detected
→ repair obligation
→ AI repair
→ regression verification
→ assurance receipt
```

### D11 — Adversarial Product Testing
Attack S-Class itself: fabricated/stale evidence, wrong revision, scope mismatch, provider lies/failures, duplicate/contradictory evidence, policy/criticality downgrade, missing obligations, malicious action proposals, concurrent claim writes, replayed events, mutated reducer, infinite repair, provenance corruption, incomplete coverage, false claim decomposition, **and a self-planning-specific case: a generated plan that quietly omits a mandatory security obligation.**

### D12 — External Validation (THESIS-GATE-1B)
Compare BASELINE vs S-CLASS with real developers. Measure: task completion time, defects caught before/after generation, rework, developer interventions, trust, usefulness, requirement misses, regressions. This is evidence for the product hypothesis — not a prerequisite for building the prototype.

---

## 35. Enterprise Evolution

The core is designed so enterprise features attach later without contaminating the prototype.

```text
                 S-CLASS CORE
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
   Developer       Team          Enterprise
   Edition         Edition          Edition
       │              │              │
       │              │         ┌────┼────┐
       │              │         ▼    ▼    ▼
       │              │       RBAC Audit SSO
       │              │         │
       │              │       Policy
       │              │       Registry
       │              │       Compliance
       │              │       Multi-project
       │              │       Governance
```

---

## 36. What Is Actually Novel

The novelty is **not**:

- "S-Class can run pytest."
- "S-Class can run Semgrep."
- "S-Class uses an LLM."
- "S-Class can generate a plan." (any LLM can generate a plan)

The differentiated proposition is:

> S-Class maintains a machine-auditable model of what an AI coding agent is obligated to establish, what claims represent those obligations, what evidence supports or refutes those claims, what policy is required for acceptance, how changes invalidate previous assurance, how the agent must recover when assurance fails — **and it applies that exact same discipline to its own self-generated plans, so that "the LLM designed it" is never, by itself, a reason to trust it.**

---

## 37. Final Product Equation

```text
S-CLASS
=
OBLIGATION MANAGEMENT
+
CLAIM/EVIDENCE GRAPH
+
POLICY ENGINE
+
DETERMINISTIC CONTROL
+
INTELLIGENT PLANNING (incl. governed self-planning)
+
VERIFICATION FABRIC
+
RECOVERY
+
REGRESSION
+
AUDITABILITY
```

And underneath: `EVENT SOURCING + PROVENANCE + DEPENDENCY TRACKING`

---

## 38. Core Invariants

```text
CORE-01  Obligation-centric architecture
CORE-02  Claim contracts instead of free-form assertions
CORE-03  Evidence as first-class objects
CORE-04  Policy-controlled acceptance
CORE-05  Planner proposes / Controller authorizes
CORE-06  Explicit evidence provenance
CORE-07  Explicit relevance and coverage
CORE-08  No universal confidence score
CORE-09  Immutable event history
CORE-10  Deterministic claim reducer
CORE-11  Explicit contradiction state
CORE-12  Dependency-driven staleness
CORE-13  Parallel obligation execution
CORE-14  External tools through adapters
CORE-15  Fail-closed acceptance
CORE-16  Bounded recovery loops
CORE-17  Regression reassessment after repair
CORE-18  Explicit human escalation
CORE-19  Policy hierarchy with non-weakening semantics
CORE-20  Unknown claims remain unknown
CORE-21  A self-generated plan is a governed claim-bearing artifact, never a privileged one
```

---

## 39. Final Development Order

```text
             DESIGN
                │
                ▼
       DOMAIN CONTRACTS
                │
                ▼
        EVENT / STATE CORE
                │
                ▼
         POLICY ENGINE
                │
                ▼
       CLAIM / EVIDENCE
                │
                ▼
          CONTROLLER
                │
                ▼
        TOOL ADAPTERS
                │
                ▼
        AGENT INTEGRATION
                │
                ▼
   PLANNER (incl. self-planning)
                │
                ▼
      FAILURE / RECOVERY
                │
                ▼
          REGRESSION
                │
                ▼
           PROTOTYPE
                │
                ▼
      ADVERSARIAL TESTING
                │
                ▼
     EXTERNAL VALIDATION
                │
                ▼
       ENTERPRISE HARDENING
```

### Hard Rule

**Do not implement a layer until its contract above it is frozen.**

This prevents building substantial machinery before the product architecture is completely settled — including letting the planner self-design an architecture before the plan-as-artifact governance model (§11) exists to check it.

---

## 40. Current Status

```text
PARITY-GATE-1          🟢 CLOSED
PARITY-GATE-2          🟢 CLOSED
PARITY-GATE-3          🟡 PROVIDER
S-CLASS CORE DESIGN    🟢 ARCHITECTURE FROZEN (this document)
```

**Next actual artifact: `SCLASS_CORE_SPECIFICATION.md`** — canonical schemas, state-transition tables, event definitions, policy grammar, evidence contract, claim contract, planner/controller contract, **plan-as-artifact contract**, adapter contract, concurrency semantics, staleness algorithm, security boundaries, invariants, and test architecture.

Only after that specification is internally consistent does implementation of the kernel begin.
