# S-Class Workflow & FSM Transitions

This document details the canonical 19-state Finite-State Machine (FSM) execution loop, parallel scheduler groups, and event transition conditions enforced by `workflow.json`.

---

## 1. The Canonical 19 FSM States

S-Class manages workflows through 19 explicit states:
1.  **`TRIAGE`:** Evaluates goal complexity, detects risk profile, and initializes FSM state.
2.  **`ANALYSIS`:** Analyzes requirements, dependencies, AST code structures, and scope constraints.
3.  **`CLARIFICATION`:** Handles human-in-the-loop clarification for unresolved scope/design ambiguities.
4.  **`SPECIFICATION_SYNTHESIS`:** Synthesizes explicit/derived requirements, runs evidence-driven expansion (`spec_synthesis.py`), and evaluates semantic gate.
5.  **`DESIGN`:** Establishes 3-tier full-stack blueprints (`backend_spec`, `db_schema`, `frontend_layout`).
6.  **`DEBATE`:** Reviews spec designs concurrently across Parallel Group #1 (`dss_governor`, `dss_ui_ux`, `dss_frontend_dev`, `dss_backend_dev`, `dss_db_architect`, `dss_cso_v2`, `dss_qa_frontend`, `dss_user_alias_v2`).
7.  **`DESIGN_REVISION`:** Incorporates red-team debate findings into revised design blueprints.
8.  **`TASK_COMPILATION`:** Aggregates critiques and design specifications into structured task DAGs.
9.  **`CODING`:** Builder subagents implement task lists into sandbox workspace branches.
10. **`TASK_VERIFICATION`:** Verifies individual task implementation receipts before code merging.
11. **`MERGE`:** Merges verified task sandbox branches into the primary workspace branch.
12. **`INTEGRATION`:** Audits cross-service APIs, database schemas, AST imports, and Zero-Infra DB fallbacks.
13. **`QA`:** Executes testing suites and visual Playwright Chrome MCP receipts across Parallel Group #2.
14. **`RECOVERY`:** Performs failure inspection, classifies root causes, and structures patch tasks.
15. **`RELEASE`:** Verifies build receipts, security scans, and mandatory user contract coverage.
16. **`MONITORING`:** Active multi-stream telemetry monitoring (`monitoring.py`) for post-release health.
17. **`FEEDBACK`:** Ingests post-release user feedback and anomaly reports.
18. **`ISSUE_DETECTION`:** Evaluates telemetry anomalies to trigger automated recovery or hotfix patches.
19. **`DONE`:** Execution complete with verified safety case.

---

## 2. Event-Driven Transition Matrix

| FSM Current State | Incoming Event | Target State |
| :--- | :--- | :--- |
| **`TRIAGE`** | `triage_done` | `ANALYSIS` |
| **`ANALYSIS`** | `context_loaded` | `SPECIFICATION_SYNTHESIS` |
| **`ANALYSIS`** | `ambiguity_detected` | `CLARIFICATION` |
| **`CLARIFICATION`** | `clarified` | `SPECIFICATION_SYNTHESIS` |
| **`SPECIFICATION_SYNTHESIS`** | `spec_synthesized` | `DESIGN` |
| **`SPECIFICATION_SYNTHESIS`** | `spec_conflict_detected` | `CLARIFICATION` |
| **`SPECIFICATION_SYNTHESIS`** | `spec_scope_decision_needed` | `CLARIFICATION` |
| **`DESIGN`** | `design_drafted` | `DEBATE` |
| **`DEBATE`** | `spec_approved` | `DESIGN_REVISION` |
| **`DEBATE`** | `debate_failed` | `DESIGN` |
| **`DESIGN_REVISION`** | `revision_approved` | `TASK_COMPILATION` |
| **`DESIGN_REVISION`** | `further_design_needed` | `DESIGN` |
| **`TASK_COMPILATION`** | `tasks_ready` | `CODING` |
| **`CODING`** | `code_written` | `TASK_VERIFICATION` |
| **`TASK_VERIFICATION`** | `task_verified` | `MERGE` |
| **`TASK_VERIFICATION`** | `task_verification_failed` | `CODING` |
| **`MERGE`** | `task_merged` | `INTEGRATION` |
| **`INTEGRATION`** | `integration_passed` | `QA` |
| **`INTEGRATION`** | `integration_failed` | `CODING` |
| **`QA`** | `qa_passed` | `RELEASE` |
| **`QA`** | `qa_failed` | `RECOVERY` |
| **`RECOVERY`** | `patch_assigned` | `CODING` |
| **`RELEASE`** | `release_complete` | `MONITORING` |
| **`RELEASE`** | `release_hold` | `CODING` |
| **`MONITORING`** | `monitoring_passed` | `DONE` |
| **`MONITORING`** | `issue_detected` | `FEEDBACK` |
| **`FEEDBACK`** | `feedback_analyzed` | `ISSUE_DETECTION` |
| **`ISSUE_DETECTION`** | `hotfix_triggered` | `RECOVERY` |
| **`ISSUE_DETECTION`** | `resolved` | `MONITORING` |
