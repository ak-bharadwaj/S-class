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




