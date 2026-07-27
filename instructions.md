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

## 12. Safety Case Architecture & Output Contract Evidence

In S-Class EOS, software release is approved ONLY when supported by a complete, multi-evidence **Safety Case**:

```
                              Release Candidate
                                      │
                                      ▼
                                 SafetyCase
                                      │
 ┌─────────────────────┬──────────────┴───────┬─────────────────────┐
 ▼                     ▼                      ▼                     ▼
Build Evidence        Test Evidence       Security Evidence     Output Contract Evidence
(Build Passed)       (Tests Passed)      (Security Clean)       (Verified against
                                                               IntentContract via
                                                               dynamic mechanism)
```

### Dynamic Mechanism Selection per Output Contract

Verification mechanism is derived automatically from `IntentContract.output_contract`:

| User Requested Output Target | Output Contract Verifier Mechanism | Verification Check |
|---|---|---|
| **Web UI** (`table`, `chart`, `form`) | `playwright_dom_inspection` | Inspects DOM for tags (`<table/>`, `<canvas/>`, SVG elements), verifies layout positioning, verifies absence of `undefined`, `NaN`, `null`, `[object Object]` text. |
| **JSON API** | `json_schema_validator` | Validates API response schema keys, data types, and status bounds. |
| **CLI Tool** | `cli_snapshot_differ` | Compares terminal stdout/stderr against golden output snapshot. |
| **Markdown Document** | `markdown_ast_verifier` | Verifies rendered Markdown AST structure and link integrity. |
| **PDF Document** | `pdf_structure_parser` | Inspects generated PDF pages, headers, and text formatting. |

### Mandatory User Proxy Output Contract Gate
* `dss_user_alias_v2` (User Proxy) **CANNOT** accept QA or Release based on unit tests, build receipts, or logs alone.
* `SafetyCase.output_contract_passed` MUST be `True` via the mechanism appropriate for the user's requested output type, or else release is **HARD-BLOCKED (`REJECT_RELEASE`)**.

## 13. User Contract Coverage & Mandatory Chrome MCP Navigation Rule

To prevent "partial verification illusion" (e.g., verifying only the home page while Settings, Reports, and Export flows remain unvisited), S-Class EOS enforces **User Contract Coverage**:

$$\text{User Contract Coverage} = \frac{\text{Verified User Contracts}}{\text{Total Required Contracts in IntentContract}} \times 100\%$$

### Mandatory Governance Rules for Agents (`dss_user_alias_v2` & `dss_qa_v2`):
1. **100% Navigation Mandate:** Agents MUST use `chrome-devtools-mcp` / Playwright to navigate to and inspect **100% of defined pages, flows, and interactive components** in `IntentContract.expected_io_flows` and `acceptance_criteria`.
2. **Contract Coverage Gate:** If `contract_coverage_percent < 85.0%`, `PolicyEngine` fires an immediate **`HARD_BLOCK` (`REJECT_RELEASE`)**:
   ```json
   {
     "contract_coverage": {
       "total_required_contracts": 12,
       "verified_contracts": 5,
       "coverage_percent": 41.7,
       "unverified_contracts": ["Settings page", "Reports tab", "Export modal"]
     },
     "policy_enforcement": "HARD_BLOCK",
     "decision": "REJECT_RELEASE",
     "rationale": "SAFETY CASE INCOMPLETE: User Contract Coverage is only 41.7%, below required 85.0% threshold."
   }
   ```
3. **No Unvisited Flow Assumptions:** Verification CANNOT be claimed for an entire web application if secondary pages or modals were never rendered or tested via Chrome MCP / Playwright.

## 14. Mandatory Live Server & Chrome MCP Verification Requirement

Without launching the live application server and invoking `chrome-devtools-mcp` tools, agents CANNOT obtain actual visual rendered output.

### Hard Mandates:
1. **Live Server Execution Required:** Before starting QA or User Proxy verification, the builder agent MUST start the application dev/live server (e.g., `npm run dev`, `vite`, `next dev`, `python app.py`) as a background task.
2. **Chrome MCP Verification Call Required:** `dss_user_alias_v2` (User Proxy) and `dss_qa_v2` (QA Agent) MUST execute Chrome DevTools MCP tools (`navigate_page`, `take_screenshot`, `take_snapshot`, `click`, `fill`) against the running application URL (e.g., `http://localhost:3000`).
3. **No Terminal/Log Substitution:** Relying solely on `npm run dev` stdout logs, backend unit tests, or terminal output WITHOUT taking Chrome MCP visual snapshots is an explicit **GOVERNANCE VIOLATION**.
4. **Safety Case Invariant:** If no Chrome MCP / Playwright visual output receipt exists in `.agents/screenshots/`, `SafetyCase.output_contract_passed` evaluates to `False`, and `PolicyEngine` automatically fires a **`HARD_BLOCK` (`REJECT_RELEASE`)**.






