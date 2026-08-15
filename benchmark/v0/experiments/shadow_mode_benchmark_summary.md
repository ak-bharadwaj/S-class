# S-Class Shadow-Mode Semantic Synthesis Benchmark Summary

- **Total Tasks Evaluated**: 7 tasks
- **Shadow MUST Invariant Recall**: **92.86% (Micro)** / **92.86% (Macro)**
- **Shadow Total GT Recall**: **85.11% (Micro)** / **85.88% (Macro)**
- **Unsupported Inference Rate**: **0.00%**
- **Average Pass 3 Stability Score**: **0.9264**
- **Total Legacy Scope Explosion Prevented**: **457 requirements**
- **Total Hallucinated UI Spreads Suppressed**: **170 pages**

## 1. Task-by-Task Shadow Synthesis & Differential Evaluation

| Task ID | Domain | Legacy Reqs (Pages) | Shadow Reqs (Pages) | MUST Recall | GT Recall | Stability | Convergence State |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **TASK-01-FINTECH-LEDGER** | fintech_banking | 103 (48) | 7 (0) | **83.33%** | **85.71%** | 0.95 | `CONVERGED` |
| **TASK-02-AUTH-SESSION-REVOKE** | auth_identity | 96 (23) | 6 (0) | **100.0%** | **100.0%** | 0.94 | `CONVERGED` |
| **TASK-03-HEALTHCARE-PHI-MASK** | healthcare_privacy | 76 (24) | 5 (0) | **100.0%** | **71.43%** | 0.925 | `STABILIZING` |
| **TASK-04-AEROSPACE-BLACKBOX-TELEMETRY** | aerospace_avionics | 63 (24) | 6 (0) | **100.0%** | **83.33%** | 0.94 | `CONVERGED` |
| **TASK-05-EXAM-BROWSER-SANDBOX** | edtech_security | 66 (25) | 6 (0) | **100.0%** | **100.0%** | 0.94 | `CONVERGED` |
| **TASK-06-PAYMENT-GATEWAY-AMBIGUOUS** | fintech_payments_ambiguous | 45 (8) | 3 (0) | **100.0%** | **85.71%** | 0.85 | `STABILIZING` |
| **TASK-07-AUTH-TOKEN-REVOCATION-AMBIGUOUS** | auth_identity_ambiguous | 47 (18) | 6 (0) | **66.67%** | **75.0%** | 0.94 | `CONVERGED` |

## 2. Output Diffing & Integrity Ledger

| Task ID | Scope Explosion Delta | UI Pages Hallucinated by Legacy | Omitted by Legacy | Semantic Integrity Score |
| :--- | :---: | :---: | :---: | :---: |
| **TASK-01-FINTECH-LEDGER** | -96 reqs | 48 pages | 5 invariants | 0.1 |
| **TASK-02-AUTH-SESSION-REVOKE** | -90 reqs | 23 pages | 4 invariants | 0.1 |
| **TASK-03-HEALTHCARE-PHI-MASK** | -71 reqs | 24 pages | 3 invariants | 0.1 |
| **TASK-04-AEROSPACE-BLACKBOX-TELEMETRY** | -57 reqs | 24 pages | 4 invariants | 0.1 |
| **TASK-05-EXAM-BROWSER-SANDBOX** | -60 reqs | 25 pages | 4 invariants | 0.1 |
| **TASK-06-PAYMENT-GATEWAY-AMBIGUOUS** | -42 reqs | 8 pages | 1 invariants | 0.18 |
| **TASK-07-AUTH-TOKEN-REVOCATION-AMBIGUOUS** | -41 reqs | 18 pages | 4 invariants | 0.1 |
