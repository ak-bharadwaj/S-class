# Mechanism Sheet: Planning with Files

- **Canonical Repository:** [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files)
- **Pinned Commit SHA:** `8eef6dc6540dde5eef3fdc0ac487ad9c48ef3ba5`
- **Last Commit Date:** `2026-11-04T19:13:40+01:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 790
- **Commands / CLI Scripts:** 222
- **Agent Definitions / Prompts:** 42
- **Skills Directories / Files:** 478
- **Lifecycle / Git Hooks:** 86
- **Test Files / Suites:** 146
- **CI / Workflow Files:** 3

## 2. Declared Lifecycle
File-based planning lifecycle: `init` -> `plan` -> `execute` -> `done` (`tests/test_hermes_first_class.py:152`). State transitions tracked across file moves (`.planning/done`).

## 3. State & Artifact Files Written
- `.planning/`: Active plan files (`.planning/done`, `.planning/in_progress`) (`.pi/skills/planning-with-files/extensions/planning-with-files/__tests__/runtime.test.ts:526`)
- `plan.md`: Current step-by-step task execution plan

## 4. WHO SETS "DONE"
File system status update: `tests/test_hermes_session_binding.py:158` (`content: 'done'`) and moving plan files into `.planning/done` directory.

## 5. Declared Verification Steps
Runs tests and verifies changed paths: `tests/test_hermes_first_class.py:152` (`final_response='done', changed_paths=['a.py']`).

## 6. Declared Loop Controls
Step-by-step tool invocation bounds within session controller (`src/controller.py:45`).

## 7. Declared Context Handling
File-backed persistence enables resetting conversation context while retaining plan state on disk.

## 8. Declared Runtime / Host Support
Python runtime, Hermes session binding, TypeScript skill extension (`package.json:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__planning-with-files`)
- **Last Commit Date:** `2026-11-04T19:13:40+01:00` (verified against raw commit metadata)
- **Release Tags Count:** 126 releases/tags (verified against raw evidence `gh_releases__planning-with-files`)
