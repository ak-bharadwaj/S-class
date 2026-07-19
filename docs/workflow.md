# S-Class Workflow & FSM Transitions

This document details the Finite-State Machine (FSM) execution loop, parallel scheduler groups, and event transition conditions.

---

## 1. The 11 FSM States

S-Class manages workflows through 11 explicit states:
1.  **`TRIAGE`:** Evaluates cost and routes request to the target complexity tier.
2.  **`ANALYSIS`:** Analyzes requirements, dependencies, and constraints.
3.  **`DESIGN`:** Establishes blueprints.
4.  **`DEBATE`:** Reviews spec designs concurrently (Parallel Group #1).
5.  **`TASK_COMPILATION`:** Aggregates critiques into structured tasks.
6.  **`CODING`:** Sequential builder implements task lists.
7.  **`INTEGRATION`:** Audits APIs, schemas, and contract mappings.
8.  **`QA`:** Executes testing suites (Parallel Group #2).
9.  **`RECOVERY`:** Performs failure inspection and structures patch tasks.
10. **`RELEASE`:** Verifies build, docs, and rollback plans.
11. **`DONE`:** Execution complete.

---

## 2. Event-Driven Transition Matrix

| FSM Current State | Incoming Event | Target State |
| :--- | :--- | :--- |
| **`TRIAGE`** | `triage_done` | `ANALYSIS` |
| **`ANALYSIS`** | `context_loaded` | `DESIGN` |
| **`DESIGN`** | `design_drafted` | `DEBATE` |
| **`DEBATE`** | `spec_approved` | `TASK_COMPILATION` |
| **`DEBATE`** | `debate_failed` | `DESIGN` |
| **`TASK_COMPILATION`** | `tasks_ready` | `CODING` |
| **`CODING`** | `code_written` | `INTEGRATION` |
| **`INTEGRATION`** | `integration_passed` | `QA` |
| **`INTEGRATION`** | `integration_failed` | `CODING` |
| **`QA`** | `qa_passed` | `RELEASE` |
| **`QA`** | `qa_failed` | `RECOVERY` |
| **`RECOVERY`** | `patch_assigned` | `CODING` |
| **`RELEASE`** | `release_complete` | `DONE` |
| **`RELEASE`** | `release_hold` | `CODING` |
