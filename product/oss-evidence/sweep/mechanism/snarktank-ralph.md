# Mechanism Sheet: Ralph (snarktank)

- **Canonical Repository:** [snarktank/ralph](https://github.com/snarktank/ralph)
- **Pinned Commit SHA:** `6c53cb0b831ebe8739c6a003e22af14902d8b0b5`
- **Last Commit Date:** `2026-02-02T01:46:21Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 31
- **Commands / CLI Scripts:** 1
- **Agent Definitions / Prompts:** 1
- **Skills Directories / Files:** 2
- **Lifecycle / Git Hooks:** 0
- **Test Files / Suites:** 0
- **CI / Workflow Files:** 1

## 2. Declared Lifecycle
Task lifecycle managed in `prd.json` with three discrete task states: `pending` -> `in_progress` -> `done` (`skills/ralph/SKILL.md:176`). Transitions occur iteratively as the agent loops over each user story, updating status fields in the PRD artifact.

## 3. State & Artifact Files Written
- `prd.json`: PRD artifact tracking stories and status (`ralph.sh:37`, `prompt.md:7`)
- `prompt.md`: Instructions loaded per iteration (`ralph.sh:38`)
- `.claude-plugin/`: Plugin metadata (`.claude-plugin/plugin.json:1`)
- `skills/`: Packaged skills for prd and ralph (`skills/ralph/SKILL.md:1`)

## 4. WHO SETS "DONE"
Agent decides task completion: `skills/ralph/SKILL.md:176` ("Add status column: 'pending' | 'in_progress' | 'done' (default 'pending')") and `prompt.md:14` ("Update prd.json to mark the task as done").

## 5. Declared Verification Steps
Relies on LLM self-attestation against acceptance criteria: `skills/prd/SKILL.md:73` ("Acceptance Criteria: Verifiable checklist of what 'done' means"). No automated test suite or git diff verifier is invoked in the loop script.

## 6. Declared Loop Controls
Bash loop with iteration cap: `ralph.sh:9` (`MAX_ITERATIONS=10`), overridable via CLI argument `ralph.sh:22` (`./ralph.sh [max_iterations]`). No explicit wall-clock timeout or token budget cap.

## 7. Declared Context Handling
Fresh context per loop iteration: `README.md:163` ("Each Iteration = Fresh Context"). The loop spawns a brand new Claude / Amp CLI process per task, avoiding context degradation and window limits.

## 8. Declared Runtime / Host Support
CLI-based runner supporting Amp CLI (`README.md:14`) and Claude Code CLI (`README.md:16`). Can be installed as a Claude skill (`README.md:50`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__snarktank-ralph`)
- **Last Commit Date:** `2026-02-02T01:46:21Z` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__snarktank-ralph`)
