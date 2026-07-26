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
    *   During **`DEBATE` Phase**, you MUST invoke `invoke_subagent` passing ALL 4 agents in parallel in a single call: `dss_governor`, `dss_cso_v2`, `dss_reviewer_v2`, and `dss_user_alias_v2`.
    *   During **`QA` Phase**, you MUST invoke `invoke_subagent` passing ALL 3 agents in parallel in a single call: `dss_reviewer_v2`, `dss_cso_v2`, and `dss_qa_v2`.
*   **Required Skills:** You and subagents MUST actively load workspace skills (`ui-ux-pro-max`, `frontend-design`, `webapp-testing`).
*   **Chrome MCP Integration:** You and `dss_qa_v2` MUST use `chrome-devtools-mcp` tools (`new_page`, `navigate_page`, `take_screenshot`) during the QA phase to capture and inspect the visual layout of the running web application in `.agents/qa_screenshots/`.

## 3. Enforce Strict Warning Scans
*   During test runs, you MUST inspect the console stdout/stderr.
*   If ANY `DeprecationWarning` (including `datetime.utcnow()` deprecation), package warning, or console warning is printed, you MUST mark the state as `qa_failed` or `release_hold` and patch the warnings first. Do not ignore warning lists!

## 4. Mandatory Peer Cross-Examination & Compound Error Correction
*   **Active Peer Critique:** Subagents running in parallel MUST use `send_message` to cross-examine each other's outputs, designs, and code proposals.
*   **Error Detection & Patching:** Subagents are forbidden from blindly approving peer outputs. Each agent must actively search for bugs, missing edge cases, security flaws, and type errors in its peers' work.
*   **Compound Final Output:** If an agent detects a flaw in a peer's proposal, the peer MUST correct the mistake before consensus is reached. The final output delivered at phase completion MUST be a **Compound Verified Solution** integrating all corrections.
*   **Strict Consensus Gate:** In `DEBATE`, `spec_approved` is forbidden unless the weighted consensus score is >= 0.80. If any peer flags an uncorrected defect, the state must be marked as `debate_failed`.

