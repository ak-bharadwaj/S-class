# Upstream Mechanism Harvest & Licensing Manifest

## 1. Executive Summary & Epistemic Separation

This manifest establishes the formal catalog of mechanisms harvested from:
1. **Step-Code** (MIT License, StepFun) — execution/runtime/harness substrate.
2. **RRSI** (Apache License 2.0, Google LLC) — harness-evolution/search/optimization substrate.

### Absolute Axioms
- **Step-Code execution state != S-Class project truth.**
- **RRSI evolution score != S-Class project truth.**
- Step-Code and RRSI may propose, execute, optimize, observe, and measure. Neither is authoritative about project truth.
- Canonical state (`AUTHORIZED`, `OBSERVED`, `VERIFIED`, `SATISFIED`, `ACCEPTED`, `COMPLETED`) is established solely by the S-Class assurance plane through independent sensory observation and typed verifier assessment.

---

## 2. Capability Taxonomy

Every harvested mechanism is classified into exactly one of five integration modes:

| Mode | Semantic Definition | Authority Rule |
| :--- | :--- | :--- |
| **ADOPT** | Direct absorption without semantic distortion. | Conforms to strict S-Class input/output interfaces. |
| **ADAPT** | Architectural pattern adapted with stronger S-Class epistemic/security invariants. | Bound to dual-layer authorization and verification. |
| **WRAP** | External runtime subsystem encapsulated behind a stable provider interface. | Runs out-of-process or sandboxed; fails closed. |
| **REFERENCE_ONLY** | Architectural design pattern referenced; zero direct source transplantation. | Provides structural schema only. |
| **REJECT** | Explicitly forbidden from adoption to prevent competing truth or scope creep. | Excluded by architectural mandate. |

---

## 3. Comprehensive Mechanism Registry

| Source Project | Source Path | Symbol / Mechanism | Purpose | Decision | S-Class Target Subsystem | License |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Step-Code** | `packages/agent-core/src/storage/entries` | `immutable entries` | Tamper-evident append-only session and event logs | **ADAPT** | `src/sclass/trust/two_ledgers.py` & `src/sclass/observation/receipts/` | MIT |
| **Step-Code** | `packages/agent-core/src/storage/registers` | `mutable registers` | Pointers to active operation, leaf, and session state | **ADAPT** | `src/sclass/runtime/sessions.py` | MIT |
| **Step-Code** | `packages/agent-core/src/telemetry/ledger` | `append-only usage ledger` | Model token, tool latency, and operational cost accounting | **ADAPT** | `src/sclass/runtime/telemetry.py` | MIT |
| **Step-Code** | `packages/agent-core/src/execution/durable_operation` | `durable operation state` | Total program counter (Intent -> Effect Pending -> Settlement) | **ADAPT** | `src/sclass/execution/operations.py` & `src/sclass/execution/effect_boundary.py` | MIT |
| **Step-Code** | `packages/agent-core/src/lanes/lane_state` | `lane state` | Execution lane isolation (main, parallel, subagent, workflow) | **ADAPT** | `src/sclass/runtime/lanes.py` | MIT |
| **Step-Code** | `packages/agent-core/src/session/tree` | `session tree & branch index` | Branching, checkpointing, and context tree navigation | **WRAP** | `src/sclass/runtime/sessions.py` | MIT |
| **Step-Code** | `packages/agent-core/src/recovery/checkpointing` | `checkpointing & recovery` | Checkpointing, retry ladder, and crash consistency | **ADAPT** | `src/sclass/runtime/recovery.py` | MIT |
| **Step-Code** | `packages/coding-agent/src/core/extensions/tool_call` | `pi.on("tool_call")` | Real extension hook intercepting tool calls before dispatch | **ADOPT** | `src/sclass/adapters/step_extension.js` | MIT |
| **Step-Code** | `packages/coding-agent/src/core/extensions/tool_result` | `pi.on("tool_result")` | Intercepting tool results for exit code and stdio hashing | **ADAPT** | `src/sclass/adapters/step_extension.js` & `src/sclass/runtime/stepcode.py` | MIT |
| **Step-Code** | `docs/command-permissions.md` | `four permission presets` | Ask, Read-only, Bypass, Autopilot with 5-way conjunction | **ADAPT** | `src/sclass/runtime/permissions.py` | MIT |
| **Step-Code** | `packages/coding-agent/src/features/subagent/` | `subagent lifecycle` | Subagent creation, progress, stop, reply, and child ACL | **ADAPT** | `src/sclass/runtime/subagents.py` | MIT |
| **Step-Code** | `packages/coding-agent/src/features/workflow/` | `workflow orchestration` | Primitives: `phase()`, `parallel()`, `pipeline()`, `agent()` | **ADAPT** | `src/sclass/runtime/workflows.py` | MIT |
| **Step-Code** | `packages/coding-agent/src/agent_loop.ts` | `conversational loop` | Interactive chat-driven coding loop | **REJECT** | N/A (S-Class is an assurance plane, not a chat client) | MIT |
| **RRSI** | `rrsi/loop.py` | `evolution search loop` | Autonomous candidate search, mutation, and evaluation | **ADAPT** | `src/sclass/evolution/engine.py` | Apache-2.0 |
| **RRSI** | `rrsi/history.py` | `immutable evolution history` | Causal history of rounds, candidates, edits, hypotheses, deltas | **ADOPT** | `src/sclass/evolution/history.py` | Apache-2.0 |
| **RRSI** | `rrsi/components.py` | `component vocabulary` | Structural taxonomy: prompt, tool, skill, subagent, memory | **ADAPT** | `src/sclass/evolution/components.py` | Apache-2.0 |
| **RRSI** | `rrsi/critic.py` | `pre-eval critic` | Deterministic and model critic blocking oracle/test leaks | **ADAPT** | `src/sclass/evolution/critic.py` | Apache-2.0 |
| **RRSI** | `rrsi/evaluate.py` | `evaluator & smoke gate` | Fast smoke verification and repeated benchmark evaluation (k trials) | **ADAPT** | `src/sclass/evolution/evaluator.py` | Apache-2.0 |
| **RRSI** | `rrsi/calibrate.py` | `noise calibration` | Empirical noise band estimation via baseline variance | **ADAPT** | `src/sclass/evolution/calibration.py` | Apache-2.0 |
| **RRSI** | `rrsi/selection.py` | `multi-objective selector` | Admissibility: quality gain, cost discipline, domain guards | **ADAPT** | `src/sclass/evolution/selector.py` | Apache-2.0 |
| **RRSI** | `rrsi/domain.py` | `domain adapter` | Modular domain datasets: evolve, heldout, smoke, adversarial | **ADAPT** | `src/sclass/evolution/domain.py` | Apache-2.0 |
| **RRSI** | `rrsi/gitops.py` | `git candidate worktrees` | Worktree isolation per candidate branch | **ADAPT** | `src/sclass/evolution/gitops.py` | Apache-2.0 |
| **RRSI** | `rrsi/readjudication.py` | `offline readjudication` | Re-evaluates selection criteria over stored historical evidence | **ADAPT** | `src/sclass/evolution/readjudication.py` | Apache-2.0 |
| **RRSI** | `rrsi/reevaluation.py` | `infra reevaluation` | Remeasures invalid infrastructure runs without dropping failures | **ADAPT** | `src/sclass/evolution/reevaluation.py` | Apache-2.0 |

---

## 4. Legal, Provenance, and Licensing Audit

### Step-Code Licensing
- **License**: MIT License
- **Copyright**: (c) 2024 StepFun
- **Requirements**: Inclusion of copyright notice and permission notice in all copies or substantial portions of the Software.
- **Compliance Status**: Fully satisfied. Copyright notices preserved in file headers and `src/sclass/upstream/provenance.py`.

### RRSI Licensing
- **License**: Apache License, Version 2.0
- **Copyright**: (c) 2024 Google LLC
- **Requirements**:
  1. Retention of copyright and license notices.
  2. Prominent notices on modified files stating that changes were made.
  3. Preservation of all notices in legal distribution.
- **Compliance Status**: Fully satisfied. Provenance metadata tracks original source commits, modifications, and copyright notices. S-Class adapts the algorithms into clean, independent Python implementations without whole-tree copying.

---

## 5. Security & Trust Kernel Immutability

The **Trust Kernel** of S-Class is formally marked **NON-EVOLVABLE**:
1. Dual-layer cryptographic authorization (`DualLayerAuthorizer`, HMAC token verification).
2. Sensory observation receipts and content-hashing pipeline.
3. Independent verifier registry and technical obligation satisfaction rules.
4. Completion evaluator criteria and non-delegable canonical project truth.

Neither Step-Code runtime processes nor RRSI evolution optimization loops may modify, bypass, or weaken the Trust Kernel.
