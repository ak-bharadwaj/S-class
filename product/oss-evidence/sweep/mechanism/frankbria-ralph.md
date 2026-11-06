# Mechanism Sheet: Ralph for Claude Code (Frank Bria)

- **Canonical Repository:** [frankbria/ralph-claude-code](https://github.com/frankbria/ralph-claude-code)
- **Pinned Commit SHA:** `11f9df5becc8093ff2265542107e8e53a42e9970`
- **Last Commit Date:** `2026-11-03T22:44:54-07:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 154
- **Commands / CLI Scripts:** 35
- **Agent Definitions / Prompts:** 5
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 0
- **Test Files / Suites:** 68
- **CI / Workflow Files:** 8

## 2. Declared Lifecycle
Autonomous development loop: `README.md:12` ("> **Autonomous AI development loop with intelligent exit detection and rate limiting**").

## 3. State & Artifact Files Written
- Local loop logs, queue state, and response analyzer records (`ralph_loop.sh:1060` ('log_status "WARN" "Exit condition: Multiple completion signals')).

## 4. WHO SETS "DONE"
Claude signals done or multiple consecutive signals received: `README.md:327` ("→ EXIT_SIGNAL: true (Claude confirms done)") and `ralph_loop.sh:1058` ('# 2. Multiple "done" signals'), evaluated at `ralph_loop.sh:1059` ('if [[ $recent_done_signals -ge $MAX_CONSECUTIVE_DONE_SIGNALS ]]; then').

## 5. Declared Verification Steps
Test suite execution and error detection scripts: `README.md:12` ("> **Autonomous AI development loop with intelligent exit detection and rate limiting**").

## 6. Declared Loop Controls
Configurable session expiration timeout: `README.md:32` ("- **Session expiration with configurable timeout (default: 24 hours)**").

## 7. Declared Context Handling
Context rotation and rate limit handling across iterations: `README.md:12` ("> **Autonomous AI development loop with intelligent exit detection and rate limiting**").

## 8. Declared Runtime / Host Support
Bash loop runner for Claude Code: `README.md:12` ("> **Autonomous AI development loop with intelligent exit detection and rate limiting**").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__frankbria-ralph`)
- **Last Commit Date:** `2026-11-03T22:44:54-07:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__frankbria-ralph`)
