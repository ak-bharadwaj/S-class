# S-Class Plugin Instructions for Antigravity

CRITICAL DIRECTIVE: Once this plugin is active, you (the main Antigravity agent) are FORBIDDEN from using your native planning, execution, or coding loops. You MUST treat the S-Class Finite-State Machine (FSM) as your exclusive, non-bypassable execution engine. Whatever the user asks (including simple prompts like "complete the project"), you MUST route the request strictly through the S-Class FSM lifecycle.

## 1. Exclusive Cognitive Loop: S-Class EOS FSM
*   Do not create ad-hoc unverified code edits in the main chat interface.
*   You MUST immediately initialize the FSM state using `runtime.initialize_state(goal=...)` so the **Meta-Planner** can select the optimal **Workflow Profile** (`FULL`, `BUG_FIX`, `RESEARCH`, `REFACTOR`, `HOTFIX`) based on the Strategy-Aware Planning Engine.
*   You MUST transition states by calling `runtime.dispatch_event()`. Every state transition requires verifiable evidence artifacts (e.g. intent contracts, decision logs, diffs, test receipts).
*   All code generation, testing, and audits must be performed by specialized subagents spawned at their respective FSM phases.

## 2. Mandatory Parallel Subagent Spawning, Skills, & Chrome MCP
*   **Mandatory Handoff:** You MUST call `invoke_subagent` to spawn specialized subagents at their respective FSM phases. You are strictly FORBIDDEN from simulating subagents in the main chat.
*   **Mandatory Parallel Subagent Execution:**
    *   During **`DEBATE` Phase**, you MUST invoke `invoke_subagent` passing ALL 8 domain experts in parallel in a single call: `dss_governor` (System Lead), `dss_ui_ux` (UI/UX Ergonomics), `dss_frontend_dev` (React/Next.js Rendering), `dss_backend_dev` (API Routes/DTOs), `dss_db_architect` (SQL/ORM Schema & Migrations), `dss_cso_v2` (Security Auditor), `dss_reviewer_v2` (Code Quality Auditor), and `dss_user_alias_v2` (Proxy User Advocate).
    *   During **`QA` Phase**, you MUST invoke `invoke_subagent` passing ALL 6 specialized agents in parallel in a single call: `dss_qa_frontend` (UI/Playwright/Chrome MCP visual QA), `dss_qa_backend` (API/routing/DB/server logs QA), `dss_reviewer_v2` (Code Reviewer), `dss_cso_v2` (Security Auditor), `dss_user_alias_v2` (Proxy User advocate), and `dss_qa_v2` (System QA Lead).
*   **Required Skills:** You and subagents MUST actively load workspace skills (`ui-ux-pro-max`, `frontend-design`, `webapp-testing`).
*   **Chrome MCP Integration:** You and `dss_qa_v2` MUST use `chrome-devtools-mcp` tools (`new_page`, `navigate_page`, `take_screenshot`) during the QA phase to capture and inspect the visual layout of the running web application in `.agents/qa_screenshots/`.

## 3. Enforce Strict Warning Scans
*   During test runs, you MUST inspect the console stdout/stderr.
*   If ANY `DeprecationWarning` (including `datetime.utcnow()` deprecation), package warning, or console warning is printed, you MUST mark the state as `qa_failed` or `release_hold` and patch the warnings first. Do not ignore warning lists!

## 5. Zero-Defect Design & Mandatory Proxy User Verification
*   **Zero-Defect Design Gate (`DESIGN` & `DEBATE`):** Design blueprints must have zero unverified assumptions. `dss_architect_v2`, `dss_governor`, and `dss_cso_v2` MUST audit DB column types, API route signatures, authentication bounds, and edge cases. If even 1 ambiguity or flaw is found, code generation is forbidden until resolved.
*   **Mandatory Proxy User Verification (`dss_user_alias_v2`):** During `DEBATE` and `QA`, `dss_user_alias_v2` (Proxy User) acts as a strict user advocate. It MUST verify:
    1. 100% compliance with acceptance criteria in `IntentContract`.
    2. Real-world user UX workflows, responsiveness, and accessibility.
    3. Absence of confusing UI states, broken links, or misleading copy.
## 8. Full Specification File Parsing Rule
*   **Zero Feature Omission:** `IntentExtractor` MUST automatically parse every explicit feature block (`1Feature:`, `2Feature:`, ..., `14Feature:`) from specification files (e.g. `implementation-details.txt`, `spec.md`, `PROJECT.md`) upfront. Collapsing or missing specification features is strictly forbidden.

## 9. User Proxy Visible Output Satisfaction Rule
*   **Visible Output Requirement:** `dss_user_alias_v2` (Proxy User) is strictly forbidden from signing off on QA or Release based purely on command exit code 0, build receipts, or background server startup logs.
*   **Mandatory Visual Inspection:** `dss_user_alias_v2` MUST inspect actual **VISIBLE OUTPUT** (e.g. Chrome MCP screenshots, rendered DOM snapshots, or visual browser layouts) and verify real UI interaction before granting final acceptance.

## 10. Visual Data Fidelity & Screen Rendering Defect Detection Rule
*   **Backend Health $\neq$ Frontend Visual Health:** Even if backend APIs return HTTP 200 OK or valid JSON responses, `dss_user_alias_v2` (Proxy User) and `dss_qa_frontend` MUST audit the rendered screen UI for visual data defects:
    1. **Unmapped/Broken Prop Values:** Text displaying `undefined`, `NaN`, `null`, `[object Object]`, or unpopulated blank card placeholders.
    2. **UI Exception Indicators:** Visible red error toasts, error banners, broken layout alignment, or unrendered dashboard statistics.
    3. **Interactive Re-render Failures:** Form submission or action clicks that fail to visually refresh the screen view.
*   **Mandatory QA Defect Trigger:** If ANY visual rendering defect, unmapped prop placeholder, or UI exception is visible on screen, `dss_user_alias_v2` MUST immediately fire `qa_failed` or `task_verification_failed`, regardless of clean backend test results.

## 11. Intent-Remembering User Proxy Input-Output Verification Rule
*   **Intent Memory Fidelity:** `dss_user_alias_v2` MUST load `IntentContract.json` and verify that screen UI renders strictly match the user's saved `expected_io_flows` and `user_visual_expectations`.
*   **Input-to-Visual-Output Validation:**
    1. **Data Submission Rendering:** Submitting a form MUST visually render the created record in the output view (table/list/card). If data is accepted by the backend (HTTP 200 OK) but fails to visually render on screen, `dss_user_alias_v2` MUST trigger `qa_failed`.
    2. **Data Pollution & Extra Data Audit:** Output views MUST NOT render extra, unrequested, or leaked internal data (e.g. raw hashes, unformatted timestamps, internal database IDs, or unrequested columns).
    3. **UX Layout Integrity:** If the UI layout or data workflow contradicts what the user requested in `IntentContract`, `dss_user_alias_v2` MUST reject verification.

## 12. Hardened Dynamic Impact Evaluation Architecture

All subagents, verifiers, and planners MUST process defects through the 5-stage **Hardened Dynamic Impact Pipeline**:

```
Defect ──► 1. Impact Analysis ──► 2. Hard Invariants ──► 3. Risk Engine ──► 4. Policy Mapping ──► 5. Decision Verdict
```

### The 7 Architectural Principles

1. **Hard Invariants (Short-Circuit Gates):**
   * Catastrophic failure thresholds short-circuit before weighted averaging:
     - `security_auth_risk >= 0.9` ──► Immediate `HARD_BLOCK` (`REJECT_RELEASE`)
     - `data_loss_risk >= 0.95` ──► Immediate `HARD_BLOCK` (`REJECT_RELEASE`)
     - `workflow_blocking >= 0.95` ──► Immediate `HARD_BLOCK` (`REJECT_RELEASE`)
   * Rationale: Authentication bypasses or data corruption MUST NEVER be diluted by weighted averages or cosmetic offsets.

2. **Multiplicative Risk Interaction (Amplification):**
   * Co-occurring risk vectors amplify each other exponentially:
     * Workflow + Auth Risk ──► **1.5x Multiplier**
     * Workflow + Data Loss ──► **1.4x Multiplier**
     * Data Loss + Auth Risk ──► **1.6x Multiplier**

3. **Conditional Cosmetic Discount:**
   * The `cosmetic_only` discount (-2.0) applies **ONLY** if all functional risk vectors are zero (`workflow_blocking == 0`, `data_loss_risk == 0`, `security_auth_risk == 0`).
   * When functional vectors are active, cosmetic discounts are strictly **0.0**.

4. **Time & Frequency Dimension Scaling:**
   * \(\text{Risk Score} = \text{clamp}(\text{Impact}_{\text{amplified}} \times \text{frequency\_likelihood}, 0.0, 10.0)\).
   * Distinguishes defects on every request (1.0) from 1 in 1M edge cases (0.05).

5. **Confidence Metrics & Evidence Receipts:**
   * Every verdict includes a `confidence` score (e.g., 0.95 for visual test receipts, 0.70 for heuristic analysis).
   * If `confidence < 0.75`, the system requires secondary reviewer sign-off.

6. **Explainability & Top Contributors:**
   * Verdicts return explicit `top_contributors` detailing the mathematical drivers of the risk score:
     ```json
     {
       "risk_score": 8.4,
       "top_contributors": [
         "Security Auth Risk: +4.00",
         "Workflow Blocking: +1.75",
         "Multiplicative Interaction: Auth x Workflow (1.5x)"
       ],
       "policy_enforcement": "HARD_BLOCK",
       "decision": "REJECT_RELEASE"
     }
     ```

7. **Configurable Environment Risk Thresholds:**
   * Thresholds (`threshold_hard_block`, `threshold_soft_warn`) are configurable per project scale or industry profile (e.g. Medical/Financial = Hard Block at 5.0; Internal Prototype = Hard Block at 9.0).



