# S-Class Gate 1.2 — Multi-Domain Semantic Inference Evaluation Matrix (5 Diverse Domains)

## 1. Disambiguated Micro vs Macro Metric Matrix

| Metric | TASK-01 (Fintech) | TASK-02 (Auth IAM) | TASK-03 (Healthcare) | TASK-04 (Aerospace) | TASK-05 (EdTech OS) | Micro-Average (Pooled) | Macro-Average (Task Mean) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Baseline A Reqs (UI Pages)** | 103 (48) | 96 (23) | 76 (24) | 63 (24) | 66 (25) | **12.62x** | **12.61x** |
| **Exp B Classification Accuracy** | **100.0%** (7/7) | **100.0%** (8/8) | **100.0%** (7/7) | **100.0%** (8/8) | **100.0%** (8/8) | **100.00%** (38/38) | **100.00%** |
| **Exp C Inferred Reqs (UI Pages)** | 10 (0) | 10 (0) | 8 (0) | 11 (0) | 15 (0) | **1.69x** | **1.71x** |
| **Exact Ground-Truth Recall** | **100.0%** (7/7) | **83.33%** (5/6) | **100.0%** (7/7) | **100.0%** (6/6) | **100.0%** (6/6) | **96.88%** (31/32) | **96.67%** |
| **Derived Inference Precision** | **100.0%** (6/6) | **100.0%** (5/5) | **100.0%** (5/5) | **100.0%** (7/7) | **100.0%** (8/8) | **100.00%** (31/31) | **100.00%** |
| **Unsupported Inference Rate** | **0.00%** (0/9) | **0.00%** (0/7) | **0.00%** (0/7) | **0.00%** (0/9) | **0.00%** (0/11) | **0.00%** (0/43) | **0.00%** |
| **Ambiguity / UNKNOWN Rate** | **10.0%** (1/10) | **30.0%** (3/10) | **12.5%** (1/8) | **18.18%** (2/11) | **26.67%** (4/15) | **20.37%** (11/54) | **19.47%** |

## 2. Independent Adjudication Integrity
- **Evaluator Decoupling**: All labels loaded dynamically from external `adjudication.json` files; zero hardcoded answers in evaluator logic.
- **Sample Scope**: 0 unsupported inferences among 43 independently adjudicated non-unknown candidates across 5 diverse domains.
- **Classification Status**: Validated prototype architecture under Gate 1.2 evaluation.