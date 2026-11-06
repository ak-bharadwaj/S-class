# Mechanism Sheet: GSD (ludicrypt fork)

- **Canonical Repository:** [ludicrypt/get-shit-done](https://github.com/ludicrypt/get-shit-done)
- **Pinned Commit SHA:** `6027b5e4d8ef2a51c679aee57592fad411ac20f6`
- **Last Commit Date:** `2026-01-20T12:11:12-06:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 126
- **Commands / CLI Scripts:** 30
- **Agent Definitions / Prompts:** 18
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 6
- **Test Files / Suites:** 1
- **CI / Workflow Files:** 0

## 2. Declared Lifecycle
Multi-phase planning and execution lifecycle mirroring core GSD architecture with tailored hooks (`get-shit-done/workflows/transition.md:69`).

## 3. State & Artifact Files Written
- `.planning/`: Phase directories, task plans, state tracking (`README.md:117`)
- `.claude/`: Slash commands (`.claude/commands/gsd-plan.md:1`)

## 4. WHO SETS "DONE"
Interactive confirmation: `get-shit-done/workflows/transition.md:78` ("Ask: 'Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?'").

## 5. Declared Verification Steps
Executes testing frameworks and inspects git changes: `get-shit-done/workflows/execute-plan.md:1081` (Jest, pytest) and `README.md:156` (`Bash(git diff:*)`).

## 6. Declared Loop Controls
30-second subprocess spawn timeout: `hooks/gsd-intel-index.js:712` (`timeout: 30000`). Bounded phase iterations.

## 7. Declared Context Handling
Fresh context per plan: `README.md:245` ("200k tokens purely for implementation, zero accumulated garbage").

## 8. Declared Runtime / Host Support
Node.js npm package (`get-shit-done-cc`), Claude Code CLI (`README.md:98`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__ludicrypt-gsd`)
- **Last Commit Date:** `2026-01-20T12:11:12-06:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__ludicrypt-gsd`)
