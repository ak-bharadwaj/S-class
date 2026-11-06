# Mechanism Sheet: Ralph Claude Code (frankbria)

- **Canonical Repository:** [frankbria/ralph-claude-code](https://github.com/frankbria/ralph-claude-code)
- **Pinned Commit SHA:** `11f9df5becc8093ff2265542107e8e53a42e9970`
- **Last Commit Date:** `2026-11-03T22:44:54-07:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 154
- **Commands / CLI Scripts:** 43
- **Agent Definitions / Prompts:** 3
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 0
- **Test Files / Suites:** 65
- **CI / Workflow Files:** 7

## 2. Declared Lifecycle
Task queue state machine: `pending` -> `in_progress` -> `done` | `failed` (`ralph_loop.sh:1058`). Manages sessions across iterations.

## 3. State & Artifact Files Written
- `.ralph/`: Loop state, queue, and logs (`ralph_loop.sh:121`)
- `.ralph/.claude_session_id`: Session ID persistence across runs (`ralph_loop.sh:121`)
- `PRD.md` / `prd.json`: Product requirements and task checklists (`ralph_import.sh:1370`)

## 4. WHO SETS "DONE"
Multiple completion signals: `ralph_loop.sh:1058` ("2. Multiple 'done' signals") and agent output parsing checking for completion tokens.

## 5. Declared Verification Steps
Git diff status verification: `ralph_queue.sh:349` (`git diff --cached --quiet`), `ralph_loop.sh:2370` (`git diff --name-only "$loop_start_sha" "$current_sha"`).

## 6. Declared Loop Controls
Per-task timeout and iteration limits: `setup.sh:95` (`CLAUDE_TIMEOUT_MINUTES=15`), `ralph_queue.sh:394` (`max_iter=$((total + 1))`).

## 7. Declared Context Handling
Configurable session expiry: `ralph_loop.sh:176` ("Session expiration: 24 hours default balances project continuity with fresh context"), `docs/CLI_OPTIONS.md:299` (`ralph --session-expiry 4`).

## 8. Declared Runtime / Host Support
Bash CLI (`ralph_loop.sh`, `setup.sh:70`), Claude Code CLI (`setup.sh:86`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__frankbria-ralph`)
- **Last Commit Date:** `2026-11-03T22:44:54-07:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__frankbria-ralph`)
