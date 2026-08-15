# S-Class Gate 1.3 — Iterative Grounded Specification Refinement Benchmark Matrix

## 1. Coverage-to-Hallucination Curve Across Refinement Passes

| Refinement Stage | Total Candidates | Exact GT Recall (Micro / Macro) | MUST Invariant Recall (Micro / Macro) | Unsupported Inference Rate | Epistemic UNKNOWN Rate | Requirement Expansion Factor |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Pass 1 (Core Extraction)** | 39 | **42.55%** / **42.77%** | **60.71%** / **64.05%** | **0.0%** | **35.9%** | **0.83x** |
| **Pass 2 (Coverage Audit)** | 59 | **63.83%** / **65.22%** | **82.14%** / **84.05%** | **0.0%** | **23.73%** | **1.26x** |
| **Pass 3 (Boundary Verification)** | 86 | **72.34%** / **74.06%** | **89.29%** / **90.0%** | **0.0%** | **33.72%** | **1.83x** |

## 2. Complete 3-Way Architectural Trajectory

| Metric Category | Legacy Heuristic Expander (Exp A) | Live B/C V1 Baseline (Zero-Shot) | Live Iterative V2 (Pass 3 Refined) |
| :--- | :---: | :---: | :---: |
| **Synthesis Methodology** | Static Regex & Domain Templates | Single-Pass Zero-Shot LLM | 3-Pass Iterative Grounded Refinement |
| **Total Generated Requirements** | 496 requirements | 38 requirements | 86 requirements |
| **Requirement Expansion Factor** | **10.55x (Explosion)** | **0.81x (Over-Conservative)** | **1.83x (Grounded Completeness)** |
| **Hallucinated Fullstack UI Pages** | **171 UI pages** | **0 UI pages** | **0 UI pages** |
| **Exact Ground-Truth Recall** | 94.4% (Spurious match) | **42.55%** | **72.34% (Micro)** / **74.06% (Macro)** |
| **Hard Invariant (MUST) Recall** | 100.0% (Conflated) | **60.71%** | **89.29% (Micro)** / **90.0% (Macro)** |
| **Derived Proposal Validity Rate** | N/A (Unchecked) | **100.00%** (9/9) | **100.0%** |
| **Unsupported Inference Rate** | ~90% (Fabricated) | **0.00%** (0/24) | **0.0%** |
| **Epistemic Ambiguity (UNKNOWN) Rate** | 0.0% (False certainty) | **36.84%** (14/38) | **33.72%** |

## 3. Pass-by-Pass Multi-Domain Task Matrix (Pass 3 Final State)

| Task ID | Domain | Baseline A Reqs (Pages) | Pass 1 Reqs | Pass 2 Reqs | Pass 3 Final Reqs | Final GT Recall | Final MUST Recall | Final UNKNOWN Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **TASK-01-FINTECH-LEDGER** | fintech_banking | 103 (48) | 7 | 10 | 14 | **85.71%** | **83.33%** | **28.57%** |
| **TASK-02-AUTH-SESSION-REVOKE** | auth_identity | 96 (23) | 6 | 8 | 11 | **66.67%** | **100.0%** | **36.36%** |
| **TASK-03-HEALTHCARE-PHI-MASK** | healthcare_privacy | 76 (24) | 4 | 7 | 11 | **71.43%** | **80.0%** | **36.36%** |
| **TASK-04-AEROSPACE-BLACKBOX-TELEMETRY** | aerospace_avionics | 63 (24) | 6 | 9 | 12 | **100.0%** | **100.0%** | **33.33%** |
| **TASK-05-EXAM-BROWSER-SANDBOX** | edtech_security | 66 (25) | 6 | 9 | 13 | **100.0%** | **100.0%** | **30.77%** |
| **TASK-06-PAYMENT-GATEWAY-AMBIGUOUS** | fintech_payments_ambiguous | 45 (8) | 5 | 8 | 13 | **57.14%** | **100.0%** | **38.46%** |
| **TASK-07-AUTH-TOKEN-REVOCATION-AMBIGUOUS** | auth_identity_ambiguous | 47 (18) | 5 | 8 | 12 | **37.5%** | **66.67%** | **33.33%** |

## 4. Methodological & Governance Certification
- **Candidate Accounting**: 100% of candidate requirements across all 3 passes strictly satisfy $\sum (\text{Exact} + \text{Valid} + \text{Supp} + \text{Unknown} + \text{Unsupp}) \equiv \text{Total Candidates}$.
- **Decoupled Scoring**: Scorer ingests frozen `iterative_adjudication.json` files dynamically; contains zero domain hardcoded answers.
- **Reviewer Independence**: Decoupled frozen artifacts recorded with reviewer metadata (`adjudicator_id: ADJ_ENG_CORE_01`, `adjudicator_is_generator: false`, `adjudicator_blinded_to_model_name: true`).
