# Mechanism Sheet: Paperclip

- **Canonical Repository:** [paperclipai/paperclip](https://github.com/paperclipai/paperclip)
- **Pinned Commit SHA:** `a4bb059f5926875b908678d3b563b3725bc1e3de`
- **Last Commit Date:** `2026-11-06T06:08:44Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 14206
- **Commands / CLI Scripts:** 2174
- **Agent Definitions / Prompts:** 977
- **Skills Directories / Files:** 628
- **Lifecycle / Git Hooks:** 194
- **Test Files / Suites:** 5484
- **CI / Workflow Files:** 30

## 2. Declared Lifecycle
Autonomous agency lifecycle: company setup -> goal ingestion -> project breakdown -> task assignment -> agent execution (`src/engine/lifecycle.ts:60`).

## 3. State & Artifact Files Written
- `.paperclip/`: Organization database, project state, agent configs (`src/config/paths.ts:15`)
- `paperclip.yaml`: Organization goals and agents definition

## 4. WHO SETS "DONE"
Supervisor agent verifies pull request or task output against goal criteria (`src/agents/supervisor.ts:145`).

## 5. Declared Verification Steps
CI integration running test suites, TypeScript compiler checks, and git diff audits (`src/verifier/git.ts:35`).

## 6. Declared Loop Controls
Budget caps, max execution steps per goal, and human-in-the-loop escalation pauses (`src/engine/budget.ts:28`).

## 7. Declared Context Handling
Agent memory scratchpad, conversation history summarization, and vector store retrieval (`src/memory/vector.ts:50`).

## 8. Declared Runtime / Host Support
Full web application (Next.js / Node.js), CLI management tool (`package.json:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__paperclip`)
- **Last Commit Date:** `2026-11-06T06:08:44Z` (verified against raw commit metadata)
- **Release Tags Count:** 30 releases/tags (verified against raw evidence `gh_releases__paperclip`)
