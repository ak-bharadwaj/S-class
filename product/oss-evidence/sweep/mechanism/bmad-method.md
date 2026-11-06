# Mechanism Sheet: BMAD-METHOD

- **Canonical Repository:** [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)
- **Pinned Commit SHA:** `022be9314e4facd16826104a9f8033e1c5ed4fdc`
- **Last Commit Date:** `2026-11-02T17:53:33Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 625
- **Commands / CLI Scripts:** 1
- **Agent Definitions / Prompts:** 80
- **Skills Directories / Files:** 490
- **Lifecycle / Git Hooks:** 1
- **Test Files / Suites:** 62
- **CI / Workflow Files:** 5

## 2. Declared Lifecycle
Multi-role software delivery lifecycle: requirements analysis -> architecture design -> story breakdown -> implementation -> verification (`skills/bmad/scripts/`).

## 3. State & Artifact Files Written
- `planning_artifacts/`: Architecture and story specs (`CHANGELOG.md:1345`)
- `.claude/commands/`: Generated assistant commands (`CHANGELOG.md:809`)
- `.bmad/`: Session log and memory (`skills/bmad/scripts/tests/test_memlog.py:160`)

## 4. WHO SETS "DONE"
Human walkthrough sign-off: `skills/bmad-walkthrough/step-03-walkthrough.md:30` ("When they say the block is done:") and `skills/bmad/scripts/tests/test_memlog.py:160` ("mark a session done: append it").

## 5. Declared Verification Steps
Runs test suites via pytest: `AGENTS.md:25` ("uv run --frozen python -B -m pytest") and pre-commit checks (`.pre-commit-config.yaml:52`).

## 6. Declared Loop Controls
Process execution timeout controls: `tools/tests/test_bmad_setup.py:242` (`timeout: float | None = None`). Step-by-step role progression.

## 7. Declared Context Handling
Role-specific prompts and session logs (`test_memlog.py:160`) prevent context bloat by scoping instructions to current agent role.

## 8. Declared Runtime / Host Support
Node.js / npm installer (`README.md:34`), Python tools (`uv run`), Claude Code / Cursor agent IDEs (`SECURITY.md:85`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** NOASSERTION (verified against raw evidence `gh_license__bmad-method`)
- **Last Commit Date:** `2026-11-02T17:53:33Z` (verified against raw commit metadata)
- **Release Tags Count:** 44 releases/tags (verified against raw evidence `gh_releases__bmad-method`)
