# Mechanism Sheet: GSD (ludicrypt fork)

- **Canonical Repository:** [ludicrypt/get-shit-done](https://github.com/ludicrypt/get-shit-done)
- **Pinned Commit SHA:** `6027b5e4d8ef2a51c679aee57592fad411ac20f6`
- **Last Commit Date:** `2026-01-20T12:11:12-06:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 126
- **Commands / CLI Scripts:** 2
- **Agent Definitions / Prompts:** 19
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 6
- **Test Files / Suites:** 1
- **CI / Workflow Files:** 1

## 2. Declared Lifecycle
Phased delivery workflow: `README.md:3` ("# GET SHIT DONE") with transition gating between milestones.

## 3. State & Artifact Files Written
- `.planning/` directory containing roadmaps and task definitions (`README.md:3` ("# GET SHIT DONE")).

## 4. WHO SETS "DONE"
User confirmation prompt at phase boundary: `get-shit-done/workflows/transition.md:78` ('Ask: "Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?"').

## 5. Declared Verification Steps
Phase review and test execution prior to milestone transition (`README.md:3` ("# GET SHIT DONE")).

## 6. Declared Loop Controls
Phase transitions require explicit confirmation: `get-shit-done/workflows/transition.md:78` ('Ask: "Phase [X] complete — all [Y] plans finished. Ready to mark done and move to Phase [X+1]?"').

## 7. Declared Context Handling
Fresh subagent execution contexts per plan (`README.md:3` ("# GET SHIT DONE")).

## 8. Declared Runtime / Host Support
Node.js CLI runner: `README.md:17` ("npx get-shit-done-cc").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__ludicrypt-gsd`)
- **Last Commit Date:** `2026-01-20T12:11:12-06:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__ludicrypt-gsd`)
