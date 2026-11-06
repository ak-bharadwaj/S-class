# Mechanism Sheet: Ruflo (formerly claude-flow)

- **Canonical Repository:** [ruvnet/ruflo](https://github.com/ruvnet/ruflo)
- **Pinned Commit SHA:** `206e59259a1d620fb320119f19399ca01053658c`
- **Last Commit Date:** `2026-11-06T05:02:09Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 8558
- **Commands / CLI Scripts:** 2021
- **Agent Definitions / Prompts:** 1022
- **Skills Directories / Files:** 462
- **Lifecycle / Git Hooks:** 968
- **Test Files / Suites:** 2077
- **CI / Workflow Files:** 37

## 2. Declared Lifecycle
Swarm and workflow orchestration lifecycle: `init` -> `plan` -> `route` -> `execute` -> `review` (`packages/core/src/orchestrator.ts:50`).

## 3. State & Artifact Files Written
- `.ruflo/`: Swarm state, vector memory, execution logs (`packages/cli/src/config.ts:25`)
- `.ruflo/memory.db`: Embedded SQLite / vector storage (`packages/memory/src/index.ts:18`)

## 4. WHO SETS "DONE"
Evaluator agent or verification gate verifies consensus: `packages/core/src/gate.ts:92` ("evaluateConsensus() -> status: 'DONE'").

## 5. Declared Verification Steps
Automated code evaluation, linting, and unit test runners (`packages/core/tests/eval.spec.ts:1`).

## 6. Declared Loop Controls
Max swarm iterations and token budget controls (`packages/core/src/config.ts:110` `maxSteps: 50`).

## 7. Declared Context Handling
Hierarchical memory decay, vector indexing, and memory compaction (`packages/memory/src/compact.ts:42`).

## 8. Declared Runtime / Host Support
Node.js CLI (`ruflo`), MCP server integration, VS Code extension (`packages/vscode/package.json:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__ruflo`)
- **Last Commit Date:** `2026-11-06T05:02:09Z` (verified against raw commit metadata)
- **Release Tags Count:** 300 releases/tags (verified against raw evidence `gh_releases__ruflo`)
