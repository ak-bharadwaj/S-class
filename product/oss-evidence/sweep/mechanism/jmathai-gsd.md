# Mechanism Sheet: GSD (jmathai fork)

- **Canonical Repository:** [jmathai/get-shit-done](https://github.com/jmathai/get-shit-done)
- **Pinned Commit SHA:** `4915d28f980e27a89110b3e6a439e166c22d6337`
- **Last Commit Date:** `2026-03-16T13:42:34-06:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 224
- **Commands / CLI Scripts:** 42
- **Agent Definitions / Prompts:** 21
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 4
- **Test Files / Suites:** 26
- **CI / Workflow Files:** 2

## 2. Declared Lifecycle
Inherits GSD phase/milestone lifecycle: `discuss` -> `plan` -> `execute` -> `verify` -> `transition` with enhanced command syntax (`CHANGELOG.md:373`).

## 3. State & Artifact Files Written
- `.planning/`: Roadmaps, state, and phase plans (`get-shit-done/workflows/transition.md:25`)
- `.planning/STATE.md`: Current phase and completed plans status
- `.claude/commands/`: Local or global Claude slash commands

## 4. WHO SETS "DONE"
User-triggered phase completion command: `CHANGELOG.md:373` ("`phase complete <N>` — mark done, update state + roadmap, detect milestone end").

## 5. Declared Verification Steps
Runs tests and git diff inspections before task closure (`get-shit-done/workflows/execute-plan.md:1776`).

## 6. Declared Loop Controls
Subprocess execution timeouts: `hooks/gsd-intel-index.js:712` (`timeout: 30000`). Step-by-step interactive workflow.

## 7. Declared Context Handling
Fresh context per plan pattern: `README.md:230` ("Each plan is small enough to execute in a fresh context window. No degradation").

## 8. Declared Runtime / Host Support
Node.js CLI, Claude Code extension environment (`README.md:98`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__jmathai-gsd`)
- **Last Commit Date:** `2026-03-16T13:42:34-06:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__jmathai-gsd`)
