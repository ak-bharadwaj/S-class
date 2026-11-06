# Mechanism Sheet: GSD (gsd-build predecessor - archived)

- **Canonical Repository:** [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)
- **Pinned Commit SHA:** `bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815`
- **Last Commit Date:** `2026-05-31T08:34:35-05:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 1854
- **Commands / CLI Scripts:** 114
- **Agent Definitions / Prompts:** 69
- **Skills Directories / Files:** 37
- **Lifecycle / Git Hooks:** 54
- **Test Files / Suites:** 736
- **CI / Workflow Files:** 20

## 2. Declared Lifecycle
Foundational milestone/phase lifecycle: planning -> plan-execution -> verification -> milestone completion (`workflows/milestone.md:40`). Upstream archived predecessor to open-gsd.

## 3. State & Artifact Files Written
- `.planning/`: Milestone specifications, phase directories, task files (`workflows/execute-plan.md:52`)
- `.planning/STATE.md`: Workflow state machine persistence
- `.claude/commands/`: Injected Claude Code commands (`package.json:28`)

## 4. WHO SETS "DONE"
User prompt confirmation required: `workflows/transition.md:78` ("Ask: 'Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?'").

## 5. Declared Verification Steps
Executes workspace test runners and verifies uncommitted git diffs: `workflows/execute-plan.md:1081` (`pytest`, `npm test`) and `git diff` review.

## 6. Declared Loop Controls
Tool invocation timeout: `hooks/gsd-intel-index.js:712` (`timeout: 30000`). Bounded human-in-the-loop transition checkpoints.

## 7. Declared Context Handling
Fresh context per execution unit: `README.md:245` ("2. **Fresh context per plan** — 200k tokens purely for implementation, zero accumulated garbage").

## 8. Declared Runtime / Host Support
Node.js CLI (`npm install -g get-shit-done-cc`), Claude Code host environment (`README.md:98`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__gsd-build`)
- **Last Commit Date:** `2026-05-31T08:34:35-05:00` (verified against raw commit metadata)
- **Release Tags Count:** 78 releases/tags (verified against raw evidence `gh_releases__gsd-build`)
