# Mechanism Sheet: Superpowers (obra)

- **Canonical Repository:** [obra/superpowers](https://github.com/obra/superpowers)
- **Pinned Commit SHA:** `22f0b463e7a5e579904dd6211a520321035526f7`
- **Last Commit Date:** `2026-11-03T14:17:07-08:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 236
- **Commands / CLI Scripts:** 53
- **Agent Definitions / Prompts:** 22
- **Skills Directories / Files:** 102
- **Lifecycle / Git Hooks:** 10
- **Test Files / Suites:** 84
- **CI / Workflow Files:** 0

## 2. Declared Lifecycle
Composable agent skill execution lifecycle: skill trigger -> input validation -> tool invocation -> result formatting (`skills/` tree).

## 3. State & Artifact Files Written
- `.superpowers/`: Session history and cache (`superpowers.json:1`)
- User workspace files created via specific file-writing skills

## 4. WHO SETS "DONE"
Invoking agent determines task completion based on skill tool outputs (`src/runner.py:54`).

## 5. Declared Verification Steps
Test suites included for skill execution and contract verification (`tests/test_skills.py:1`).

## 6. Declared Loop Controls
Command timeout and tool call limits (`src/executor.py:82`).

## 7. Declared Context Handling
Stateless skill execution: each skill receives targeted parameters without bloating context.

## 8. Declared Runtime / Host Support
Python CLI and agent extension framework (`pyproject.toml:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__superpowers`)
- **Last Commit Date:** `2026-11-03T14:17:07-08:00` (verified against raw commit metadata)
- **Release Tags Count:** 17 releases/tags (verified against raw evidence `gh_releases__superpowers`)
