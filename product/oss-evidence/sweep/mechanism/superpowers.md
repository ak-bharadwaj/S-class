# Mechanism Sheet: Superpowers

- **Canonical Repository:** [obra/superpowers](https://github.com/obra/superpowers)
- **Pinned Commit SHA:** `22f0b463e7a5e579904dd6211a520321035526f7`
- **Last Commit Date:** `2026-11-03T14:17:07-08:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 236
- **Commands / CLI Scripts:** 53
- **Agent Definitions / Prompts:** 31
- **Skills Directories / Files:** 102
- **Lifecycle / Git Hooks:** 9
- **Test Files / Suites:** 83
- **CI / Workflow Files:** 2

## 2. Declared Lifecycle
Specification and subagent-driven development workflow: `README.md:3` ("Superpowers is a complete software development methodology for your coding agents") beginning with user intent (`README.md:38` ("It starts from the moment you fire up your coding agent.")), signing off on design (`README.md:42` ("After you've signed off on the design, your agent puts together an implementation plan")), and executing subagents (`README.md:44` ('Next up, once you say "go", it launches a *subagent-driven-development* process')).

## 3. State & Artifact Files Written
- Implementation plans, design specs, and skill libraries (`README.md:3` ("Superpowers is a complete software development methodology for your coding agents")).

## 4. WHO SETS "DONE"
Subagents inspect and review work against implementation plan: `README.md:44` ('Next up, once you say "go", it launches a *subagent-driven-development* process').

## 5. Declared Verification Steps
Red/green TDD and plan inspection: `README.md:42` ("After you've signed off on the design, your agent puts together an implementation plan").

## 6. Declared Loop Controls
Subagent task execution loop running autonomously: `README.md:44` ('Next up, once you say "go", it launches a *subagent-driven-development* process').

## 7. Declared Context Handling
Subagent isolation preventing plan deviation: `README.md:44` ('Next up, once you say "go", it launches a *subagent-driven-development* process').

## 8. Declared Runtime / Host Support
Cross-harness skill library supporting Claude Code, Codex, Antigravity, and others: `README.md:1` ("# Superpowers").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__superpowers`)
- **Last Commit Date:** `2026-11-03T14:17:07-08:00` (verified against raw commit metadata)
- **Release Tags Count:** 17 releases/tags (verified against raw evidence `gh_releases__superpowers`)
