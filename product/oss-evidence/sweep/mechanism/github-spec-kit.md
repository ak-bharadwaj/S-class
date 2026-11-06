# Mechanism Sheet: GitHub Spec Kit

- **Canonical Repository:** [github/spec-kit](https://github.com/github/spec-kit)
- **Pinned Commit SHA:** `3ca735b846afcbcf3304d571f296ec542464e08c`
- **Last Commit Date:** `2026-11-05T13:44:37-06:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 1021
- **Commands / CLI Scripts:** 535
- **Agent Definitions / Prompts:** 28
- **Skills Directories / Files:** 8
- **Lifecycle / Git Hooks:** 9
- **Test Files / Suites:** 383
- **CI / Workflow Files:** 30

## 2. Declared Lifecycle
Specification-driven SDLC lifecycle: requirements (`spec.md`) -> plan (`plan.md`) -> tasks (`tasks.md`) -> implementation (`spec-driven.md:294`).

## 3. State & Artifact Files Written
- `.spec-kit/`: Local tool configurations and templates (`src/specify_cli/__init__.py:12`)
- `spec.md`, `plan.md`, `tasks.md`: Structured specification artifacts (`docs/how-to/complex-features.md:7`)

## 4. WHO SETS "DONE"
Human approval and verification checklist: `spec-driven.md:407` ("Everything must be inspectable through CLI interfaces").

## 5. Declared Verification Steps
Explicit test runner suites: `pytest` and linter checks (`tests/test_cli.py:1`, `src/specify_cli/events/__init__.py:1986`).

## 6. Declared Loop Controls
Event-driven CLI architecture with configurable timeouts per LLM request (`src/specify_cli/events/__init__.py:35`).

## 7. Declared Context Handling
Event compaction handling: `src/specify_cli/events/__init__.py:1986` ("LLM request so the context survives compaction").

## 8. Declared Runtime / Host Support
Python CLI (`specify`, `pyproject.toml:28`), GitHub Actions workflows (`.github/workflows/ci.yml:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__github-spec-kit`)
- **Last Commit Date:** `2026-11-05T13:44:37-06:00` (verified against raw commit metadata)
- **Release Tags Count:** 240 releases/tags (verified against raw evidence `gh_releases__github-spec-kit`)
