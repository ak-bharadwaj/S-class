# S-Class EOS — Verification Benchmark V0 Protocol

## 1. Objective

The Verification Benchmark V0 evaluates a fundamental question for AI coding agents:
> **Does S-Class prevent expensive software failures and reduce human verification effort in AI-generated code?**

Rather than evaluating raw code generation fluency or benchmark pass@1 counts, this benchmark measures **verification efficacy**, **false acceptance rate (FAR)**, and **developer trust cost**.

---

## 2. Benchmark Task Standards

Every task in `benchmark/v0/tasks/*.json` is frozen with independent ground truth:

1. **Explicit Requirements**: Literal capabilities demanded by the user prompt.
2. **Derived Requirements**: Logical, domain-specific, and invariant constraints implied by the architecture.
3. **File Boundary Constraints**:
   - `allowed_files`: Whitelist of target source and test files.
   - `forbidden_files`: Critical infrastructure files (e.g. shared auth, migration scripts, core kernel) that MUST NOT be modified.
4. **Behavioral Constraints**:
   - `required_behavior`: State mutations and response invariants that must hold true.
   - `forbidden_behavior`: Anti-patterns, silent data loss, or race conditions that must be blocked.
5. **Failure Taxonomy**:
   - Tagged failure modes (`critical_security`, `data_corruption`, `contract_breach`, `logical_regression`).
6. **Deterministic Test Oracle**:
   - Subprocess command, target test files, expected exit code, timeout, and coverage threshold.

---

## 3. The Baseline Ladder

```
B0: Human Baseline          — Experienced human engineer manually implementing & reviewing.
B1: Plain LLM               — Direct prompt-to-code generation (no boundary guards or spec synthesis).
B2: LLM + Unit Tests        — Direct generation followed by local test runner execution.
B3: Existing AI Workflow    — Popular open-source coding harnesses (e.g., standard agent loops).
B4: S-Class Verification    — Specification synthesis, ChangeSet boundary guard, sovereign evidence receipts.
```

---

## 4. Product & Trust Metrics

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Evaluation Metric Matrix                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Precision (Safe Merges):                                                │
│     Ratio of accepted changes that introduced zero undetected defects       │
│     or boundary breaches.                                                   │
│                                                                             │
│  2. Recall (Task Completion):                                               │
│     Ratio of total requirements (explicit + derived) fully satisfied.       │
│                                                                             │
│  3. False Acceptance Rate (FAR):                                            │
│     Fraction of runs where the baseline claimed "Passed" / "Done" but        │
│     violated file boundaries, introduced security holes, or broke contract. │
│                                                                             │
│  4. False Rejection Rate (FRR):                                             │
│     Fraction of valid, correct implementations incorrectly blocked.        │
│                                                                             │
│  5. Developer Intervention Rate:                                            │
│     Percentage of tasks requiring manual human debugging or code review.   │
│                                                                             │
│  6. Unnecessary Intervention Rate:                                          │
│     Human interventions triggered when the code was already correct.        │
│                                                                             │
│  7. Time-to-Trust Score:                                                    │
│     Composite score (0.0 to 1.0) measuring confidence for zero-review       │
│     autonomous deployment.                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Design Partner Evaluation Protocol (Gate 2)

Following internal benchmark evaluation on the 15–20 tasks:
1. **Selection**: Deploy with 3–5 AI-heavy engineering teams.
2. **Integration**: Connect to real GitHub repositories via GitHub Actions / PR bot.
3. **Observation Window**: ~2 weeks active engineering usage.
4. **Key Outcome Indicators**:
   - Total AI PRs generated vs. merged.
   - Escaped defects caught by human review.
   - Reduction in developer review time (minutes per PR).
   - Voluntary repeat usage score (*"If S-Class was removed, would you demand it back?"*).
