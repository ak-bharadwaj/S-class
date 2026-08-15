# S-Class Gate 1.2 — Multi-Domain Semantic Inference Evaluation Matrix (7 Engineering Tasks)

## 1. Disambiguated Micro vs Macro Metric Matrix

| Task ID | Domain | Baseline A Reqs (Pages) | Exp B Accuracy | Exp C Reqs | Candidate Breakdown (Exact/Valid/Supp/Unk/Unsupp) | Exact GT Recall | MUST Invariant Recall | UNKNOWN Rate |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TASK-01-FINTECH-LEDGER** | fintech_banking | 103 (48) | **85.7%** (6/7) | 6 | 4/0/0/2/0 | **57.1%** (4/7) | **50.0%** (3/6) | **33.3%** |
| **TASK-02-AUTH-SESSION-REVOKE** | auth_identity | 96 (23) | **100.0%** (8/8) | 5 | 2/1/1/1/0 | **33.3%** (2/6) | **66.7%** (2/3) | **20.0%** |
| **TASK-03-HEALTHCARE-PHI-MASK** | healthcare_privacy | 76 (24) | **85.7%** (6/7) | 4 | 1/1/0/2/0 | **28.6%** (2/7) | **40.0%** (2/5) | **50.0%** |
| **TASK-04-AEROSPACE-BLACKBOX-TELEMETRY** | aerospace_avionics | 63 (24) | **100.0%** (8/8) | 7 | 4/1/0/2/0 | **66.7%** (4/6) | **75.0%** (3/4) | **28.6%** |
| **TASK-05-EXAM-BROWSER-SANDBOX** | edtech_security | 66 (25) | **75.0%** (6/8) | 5 | 3/0/0/2/0 | **50.0%** (3/6) | **75.0%** (3/4) | **40.0%** |
| **TASK-06-PAYMENT-GATEWAY-AMBIGUOUS** | fintech_payments_ambiguous | 45 (8) | **66.7%** (2/3) | 6 | 3/0/0/3/0 | **42.9%** (3/7) | **100.0%** (3/3) | **50.0%** |
| **TASK-07-AUTH-TOKEN-REVOCATION-AMBIGUOUS** | auth_identity_ambiguous | 47 (18) | **100.0%** (4/4) | 5 | 2/0/1/2/0 | **25.0%** (2/8) | **33.3%** (1/3) | **40.0%** |

## 2. Overall Multi-Domain Summary Statistics

| Statistic Category | Micro-Average (Pooled Aggregate) | Macro-Average (Task Mean) |
| :--- | :--- | :--- |
| **Stage 1 (Semantic Classification Accuracy)** | **88.89%** (40/45) | **87.58%** |
| **Baseline A Requirement Explosion Factor** | **10.55x** | **10.77x** |
| **Exp C Requirement Expansion Factor** | **0.81x** | **0.82x** |
| **Exact Ground-Truth Recall** | **42.55%** (20/47) | **43.37%** |
| **Hard Invariant (MUST) Recall** | **60.71%** (17/28) | **62.86%** |
| **Adjudicated Derived Validity Rate** | **100.00%** (9/9) | **100.00%** |
| **Unsupported Inference Rate** | **0.00%** (0/24) | **0.00%** |
| **Epistemic Ambiguity (UNKNOWN) Rate** | **36.84%** (14/38) | **37.41%** |

## 3. Methodological & Governance Notes
- **Accounting Verification**: 100% of candidate requirements across all 7 tasks strictly account for sum(Exact + Valid + Supp + Unknown + Unsupp) == Total Candidates.
- **Scope of Precision Claim**: 100% adjudicated validity among 9 candidates proposed as derivations across these 7 benchmark tasks.
- **Scope of Unsupported Claim**: 0 unsupported inferences among 24 independently adjudicated non-unknown candidates across these 7 benchmark tasks.
- **Adjudication Decoupling Status**: Decoupled frozen JSON artifacts; internal peer audit metadata recorded (🟠 external third-party certification pending).