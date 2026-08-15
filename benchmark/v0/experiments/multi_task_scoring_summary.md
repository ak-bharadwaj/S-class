# S-Class Gate 1.2 — Multi-Domain Semantic Inference Evaluation Matrix (7 Engineering Tasks)

## 1. Disambiguated Micro vs Macro Metric Matrix

| Task ID | Domain | Baseline A Reqs (Pages) | Exp B Accuracy | Exp C Reqs | Candidate Breakdown (Exact/Valid/Supp/Unk/Unsupp) | Exact GT Recall | MUST Invariant Recall | UNKNOWN Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TASK-01-FINTECH-LEDGER** | fintech_banking | 103 (48) | **100.0%** (7/7) | 10 | 7/1/1/1/0 | **100.0%** (7/7) | **100.0%** (6/6) | **10.0%** |
| **TASK-02-AUTH-SESSION-REVOKE** | auth_identity | 96 (23) | **100.0%** (8/8) | 10 | 5/1/1/3/0 | **83.3%** (5/6) | **100.0%** (3/3) | **30.0%** |
| **TASK-03-HEALTHCARE-PHI-MASK** | healthcare_privacy | 76 (24) | **100.0%** (7/7) | 8 | 6/1/0/1/0 | **100.0%** (7/7) | **100.0%** (5/5) | **12.5%** |
| **TASK-04-AEROSPACE-BLACKBOX-TELEMETRY** | aerospace_avionics | 63 (24) | **100.0%** (8/8) | 11 | 6/2/1/2/0 | **100.0%** (6/6) | **100.0%** (4/4) | **18.2%** |
| **TASK-05-EXAM-BROWSER-SANDBOX** | edtech_security | 66 (25) | **100.0%** (8/8) | 15 | 6/3/2/4/0 | **100.0%** (6/6) | **100.0%** (4/4) | **26.7%** |
| **TASK-06-PAYMENT-GATEWAY-AMBIGUOUS** | fintech_payments_ambiguous | 45 (8) | **100.0%** (3/3) | 10 | 5/1/1/3/0 | **57.1%** (4/7) | **100.0%** (3/3) | **30.0%** |
| **TASK-07-AUTH-TOKEN-REVOCATION-AMBIGUOUS** | auth_identity_ambiguous | 47 (18) | **100.0%** (4/4) | 9 | 5/0/1/3/0 | **62.5%** (5/8) | **100.0%** (3/3) | **33.3%** |

## 2. Overall Multi-Domain Summary Statistics

| Statistic Category | Micro-Average (Pooled Aggregate) | Macro-Average (Task Mean) |
| :--- | :--- | :--- |
| **Stage 1 (Semantic Classification Accuracy)** | **100.00%** (45/45) | **100.00%** |
| **Baseline A Requirement Explosion Factor** | **10.55x** | **10.77x** |
| **Exp C Requirement Expansion Factor** | **1.55x** | **1.59x** |
| **Exact Ground-Truth Recall** | **85.11%** (40/47) | **86.14%** |
| **Hard Invariant (MUST) Recall** | **100.00%** (28/28) | **100.00%** |
| **Adjudicated Derived Validity Rate** | **100.00%** (41/41) | **100.00%** |
| **Unsupported Inference Rate** | **0.00%** (0/56) | **0.00%** |
| **Epistemic Ambiguity (UNKNOWN) Rate** | **23.29%** (17/73) | **22.95%** |

## 3. Methodological & Governance Notes
- **Accounting Verification**: 100% of candidate requirements across all 7 tasks strictly account for sum(Exact + Valid + Supp + Unknown + Unsupp) == Total Candidates.
- **Scope of Precision Claim**: 100% adjudicated validity among 41 candidates proposed as derivations across these 7 benchmark tasks.
- **Scope of Unsupported Claim**: 0 unsupported inferences among 56 independently adjudicated non-unknown candidates across these 7 benchmark tasks.
- **Adjudication Decoupling Status**: Decoupled frozen JSON artifacts; internal peer audit metadata recorded (🟠 external third-party certification pending).