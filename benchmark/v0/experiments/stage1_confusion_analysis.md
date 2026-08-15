# S-Class Gate 1.3 — Stage 1 Semantic Classifier Confusion Matrix & Topology Analysis

- **Total Units Evaluated**: 45 units across 7 benchmark tasks
- **Micro-Accuracy (Pooled Aggregate)**: **88.89%** (40/45)
- **Macro-Accuracy (Task Mean)**: **87.58%**

## 1. 6x6 Semantic Class Confusion Matrix

| Ground Truth \ Predicted | ENTITY | INVARIANT | BEHAVIOR | CONSTRAINT | ATTRIBUTE | NOISE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **ENTITY** | 13 | 0 | 1 | 0 | 0 | 0 |
| **INVARIANT** | 0 | 3 | 0 | 1 | 0 | 0 |
| **BEHAVIOR** | 0 | 1 | 12 | 0 | 0 | 0 |
| **CONSTRAINT** | 0 | 1 | 0 | 4 | 1 | 0 |
| **ATTRIBUTE** | 0 | 0 | 0 | 0 | 1 | 0 |
| **NOISE** | 0 | 0 | 0 | 0 | 0 | 7 |

## 2. Per-Class Precision, Recall, and F1-Score

| Semantic Class | Support (GT Count) | True Positives | False Positives | False Negatives | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **ENTITY** | 14 | 13 | 0 | 1 | **100.0%** | **92.86%** | **96.3%** |
| **INVARIANT** | 4 | 3 | 2 | 1 | **60.0%** | **75.0%** | **66.67%** |
| **BEHAVIOR** | 13 | 12 | 1 | 1 | **92.31%** | **92.31%** | **92.31%** |
| **CONSTRAINT** | 6 | 4 | 1 | 2 | **80.0%** | **66.67%** | **72.73%** |
| **ATTRIBUTE** | 1 | 1 | 1 | 0 | **50.0%** | **100.0%** | **66.67%** |
| **NOISE** | 7 | 7 | 0 | 0 | **100.0%** | **100.0%** | **100.0%** |

## 3. Dissected Error Topology (All 5 Mismatches)

| Task | Semantic Unit | Expected (GT) | Predicted | Confidence | Analysis & Mitigation |
| :--- | :--- | :--- | :--- | :---: | :--- |
| **TASK_01** | `"atomic"` | `INVARIANT` | `CONSTRAINT` | 0.95 | Specifies an all-or-nothing transactional boundary constraint (ACID property) governing execution rather than a distinct domain object or functional logic. |
| **TASK_03** | `"analytics ingestion"` | `ENTITY` | `BEHAVIOR` | 0.9 | Describes the workflow and integration operation of receiving processed data into the downstream analytics environment. |
| **TASK_05** | `"lockdown"` | `BEHAVIOR` | `INVARIANT` | 0.91 | Specifies an immutable security enforcement state and non-negotiable safety invariant governing system operation. |
| **TASK_05** | `"dual-monitor mirroring"` | `CONSTRAINT` | `ATTRIBUTE` | 0.89 | Identifies a specific multi-display hardware configuration property and topology state subject to inspection. |
| **TASK_06** | `"secure"` | `CONSTRAINT` | `INVARIANT` | 0.92 | Specifies a non-negotiable security invariant and safety rule governing all data handling, transmission, and access control policies across the service. |

## 4. Epistemic Confidence Boundary Policy
- **Threshold**: Confidence $\ge 0.85$ required for autonomous ingestion into Requirement IR.
- **Boundary Demotion**: Ambiguous `INVARIANT` $\leftrightarrow$ `CONSTRAINT` transitions without formal mathematical predicates are flagged as `UNKNOWN / CLARIFICATION` candidates to prevent latent corruption of downstream formal models.
