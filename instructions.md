# S-Class Plugin Instructions for Antigravity

CRITICAL DIRECTIVE: Once this plugin is active, you (the main Antigravity agent) are FORBIDDEN from using your native planning, execution, or coding loops. You MUST treat the S-Class Finite-State Machine (FSM) as your exclusive, non-bypassable execution engine. Whatever the user asks (including simple prompts like "complete the project"), you MUST route the request strictly through the S-Class FSM lifecycle.

## 1. Exclusive Cognitive Loop: S-Class FSM
*   Do not think of your own plan, write files, or execute commands manually in the direct chat interface.
*   Instead, you MUST immediately initialize the FSM state using the `runtime.py` library and transition the states sequentially (TRIAGE -> ANALYSIS -> CLARIFICATION -> DESIGN -> DEBATE -> TASK_COMPILATION -> CODING -> INTEGRATION -> QA -> RELEASE -> DONE) by dispatching events.
*   All code generation, testing, and audits must be performed by the specialized subagents spawned at each state. Do not bypass the FSM steps.

## 2. Mandatory Subagent Spawning, Skills, & Chrome MCP
*   **Mandatory Handoff:** You MUST call the `invoke_subagent` tool to spawn the specialized agents (e.g. `dss_analyst`, `dss_architect_v2`, `dss_builder_v2`, `dss_user_alias_v2`) at their respective FSM phases. You are forbidden from simulating these agents in the main chat.
*   **Required Skills:** You and the subagents MUST actively load and use the workspace skills (such as `ui-ux-pro-max`, `frontend-design`, and `webapp-testing`) to execute designs and verification.
*   **Chrome MCP Integration:** You and the QA Lead MUST use the `chrome-devtools-mcp` tools (such as `new_page`, `navigate_page`, `take_screenshot`) during the QA phase to capture and inspect the visual layout of the running web application.

## 3. Enforce Strict Warning Scans
*   During test runs, you MUST inspect the console stdout/stderr.
*   If ANY `DeprecationWarning` (including `datetime.utcnow()` deprecation), package warning, or console warning is printed, you MUST mark the state as `qa_failed` or `release_hold` and patch the warnings first. Do not ignore warning lists!

## 3. Mandatory Live UI & API Verification
*   If the project has a backend API, you MUST launch the local server in the background and execute live HTTP requests (e.g., via `curl` or python fetch) to check routing.
*   If the project has a frontend UI, you MUST launch the dev server, run Playwright/browser tools, capture E2E screenshots, and save them in `.agents/qa_screenshots/`.
*   You MUST visually inspect the screenshots for layout overflows, **text overlapping**, or **invisible/low-contrast text**. Veto the release if any visual defect is found.
