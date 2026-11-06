# Mechanism Sheet: Ruflo (rUv)

- **Canonical Repository:** [ruvnet/ruflo](https://github.com/ruvnet/ruflo)
- **Pinned Commit SHA:** `206e59259a1d620fb320119f19399ca01053658c`
- **Last Commit Date:** `2026-11-05T23:02:09-06:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 8558
- **Commands / CLI Scripts:** 2091
- **Agent Definitions / Prompts:** 1021
- **Skills Directories / Files:** 462
- **Lifecycle / Git Hooks:** 965
- **Test Files / Suites:** 2111
- **CI / Workflow Files:** 39

## 2. Declared Lifecycle
Value-object task status lifecycle: `.agents/skills/v3-core-implementation/SKILL.md:284` ("type TaskStatusType = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed';") transitioning from pending (`.agents/skills/v3-core-implementation/SKILL.md:202` ("status: TaskStatus.pending(),")) to assigned (`.agents/skills/v3-core-implementation/SKILL.md:220` ("this.props.status = TaskStatus.assigned();")) to completed (`.agents/skills/v3-core-implementation/SKILL.md:235` ("this.props.status = TaskStatus.completed();")).

## 3. State & Artifact Files Written
- Agent database artifacts (`agentdb.rvf`) and skill implementations: `README.md:5` ("**An agent meta-harness for Claude Code and Codex.**").

## 4. WHO SETS "DONE"
Task status transition to completed: `.agents/skills/v3-core-implementation/SKILL.md:235` ("this.props.status = TaskStatus.completed();").

## 5. Declared Verification Steps
Value object state invariants and consensus validation: `.agents/skills/v3-core-implementation/SKILL.md:284` ("type TaskStatusType = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed';").

## 6. Declared Loop Controls
State transitions bounded by lifecycle status invariants: `.agents/skills/v3-core-implementation/SKILL.md:284` ("type TaskStatusType = 'pending' | 'assigned' | 'in_progress' | 'completed' | 'failed';").

## 7. Declared Context Handling
Agent memory store and database backend: `README.md:5` ("**An agent meta-harness for Claude Code and Codex.**").

## 8. Declared Runtime / Host Support
Agent meta-harness for Claude Code and Codex: `README.md:5` ("**An agent meta-harness for Claude Code and Codex.**").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__ruflo`)
- **Last Commit Date:** `2026-11-05T23:02:09-06:00` (verified against raw commit metadata)
- **Release Tags Count:** 300 releases/tags (verified against raw evidence `gh_releases__ruflo`)
