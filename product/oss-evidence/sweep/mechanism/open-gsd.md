# Mechanism Sheet: GSD (open-gsd successor)

- **Canonical Repository:** [open-gsd/gsd-core](https://github.com/open-gsd/gsd-core)
- **Pinned Commit SHA:** `f3f3a182627f56267028cf3145239ef8d8154635`
- **Last Commit Date:** `2026-11-05T23:18:35Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 4238
- **Commands / CLI Scripts:** 141
- **Agent Definitions / Prompts:** 176
- **Skills Directories / Files:** 184
- **Lifecycle / Git Hooks:** 109
- **Test Files / Suites:** 1703
- **CI / Workflow Files:** 33

## 2. Declared Lifecycle
Phase-driven state machine: `discuss` -> `plan` -> `execute` -> `verify` -> `transition` (`get-shit-done/workflows/transition.md:69`, `packages/core/src/state.ts:45`). Transitions move through numbered milestones and phases.

## 3. State & Artifact Files Written
- `.planning/`: Phase plans, roadmaps, and requirements (`packages/core/src/planning.ts:32`)
- `.planning/STATE.md`: Persistent session state and progress tracking
- `.planning/ROADMAP.md`: Multi-phase milestone roadmap
- `.claude/commands/`: Custom slash commands (`packages/cli/src/install.ts:18`)

## 4. WHO SETS "DONE"
Agent asks user confirmation or verifies criteria: `get-shit-done/workflows/transition.md:78` ("Ask: 'Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?'").

## 5. Declared Verification Steps
Runs tests and inspects git diffs before concluding phase: `get-shit-done/workflows/execute-plan.md:1776` ("git diff --name-only ${FIRST_TASK}^..HEAD") and executes project test runners (Jest, pytest, Go).

## 6. Declared Loop Controls
Subprocess execution timeouts: `hooks/gsd-intel-index.js:712` (`timeout: 30000`), package version check `hooks/gsd-check-update.js:45` (`timeout: 10000`). Plan execution is bounded per-phase.

## 7. Declared Context Handling
Fresh context per plan: `README.md:245` ("Fresh context per plan — 200k tokens purely for implementation, zero accumulated garbage") and `GSD-STYLE.md:229` (`### Fresh Context Pattern`).

## 8. Declared Runtime / Host Support
CLI (`npx get-shit-done-cc`, `packages/cli/bin/gsd.js:1`), Claude Code integration, Node.js runtime (`packages/core/package.json:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__open-gsd`)
- **Last Commit Date:** `2026-11-05T23:18:35Z` (verified against raw commit metadata)
- **Release Tags Count:** 48 releases/tags (verified against raw evidence `gh_releases__open-gsd`)
