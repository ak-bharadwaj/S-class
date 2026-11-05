# Brief 00 — READ-ONLY repo scan (no code changes, no commits)
Repo: github.com/ak-bharadwaj/S-class (all branches incl. h0, h1a, h1b). Authority: FREEZE-CANDIDATE-v6.0.2-R28 master; frozen kernel spec v6.0.1. Read both before starting.

## Rules
- Read-only. Do not edit, format, commit, merge, rebase or tag anything. Do not install global tools.
- Every statement needs file:line or a command with raw output. If you cannot show it, write UNVERIFIED. Do not summarise from memory or from file names.
- Do not run anything that takes more than a few minutes. Run the repo's existing test command once per branch and paste the raw tail.

## Deliverables (put in a new untracked folder scan-00/, plus paste the files here)
1. scan-00/branches.txt: for h0, h1a, h1b, main: head sha, merge-base with main, commits ahead/behind, `git diff --stat main..<branch>` (raw).
2. scan-00/tree.txt: `git ls-files` per branch with line counts for source files (raw).
3. scan-00/tests.txt: the exact test command used, exit code, pass/fail/skip counts, raw output tail, per branch. If tests cannot run, paste the error.
4. scan-00/REPO-SCAN.md with these sections, each fact cited file:line:
   a. Kernel inventory: where the canonical encoding, reducer, EventStore, event types, states, ExecutionGate live; entry points; public APIs.
   b. Frozen-spec conformance: for each frozen kernel event/state in v6.0.1, the code location that implements it, or MISSING.
   c. Implementation-reality map (master §10.4): each item as keep / replace / retire / qualify with evidence, or UNVERIFIED.
   d. H0 readiness: what exists vs what H0 needs (canonical encoding, reducer, EventStore conformance/replay suite). List gaps.
   e. Any code that adds kernel events/states/enums beyond v6.0.1, any second state machine, any agent-writable trust field, any edit to frozen spec files. Quote lines. Say NONE FOUND only after showing the search commands you ran.
   f. Dependencies and licences actually used (lockfile lines), versus the master's OSS records.
   g. Risks and unknowns, each marked UNVERIFIED unless proven.
   h. Matrix touchpoints (read-only facts, UNVERIFIED if not shown): which hosts (VS Code, Cursor, Codex, Antigravity) and which languages/frameworks (Java, Python, JavaScript, TypeScript) the repo currently has any adapter, pack, extension code or tests for; MCP server code if any. See V1-SCOPE-MATRIX.md.
   i. Test-count reconciliation: the frozen docs disagree (DEVELOPMENT-EXECUTION-PLAN.md says 91 tests = 57 conformance + 34 runtime; 00-START-HERE-IMPLEMENTERS.md says 92 = 57 + 35). Report the real count per branch from the raw run and which test accounts for the difference.
5. A final checklist: every deliverable above present yes/no.

## What Claude will do with it
Open the cited lines for a sample of your claims and re-run one test command. Any uncited or wrong claim means the scan is returned. Do not start Brief 01 until Claude accepts Brief 00.
