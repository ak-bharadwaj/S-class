# Mechanism Sheet: Taskmaster

- **Canonical Repository:** [eyaltoledano/claude-task-master](https://github.com/eyaltoledano/claude-task-master)
- **Pinned Commit SHA:** `c0c98d367c55296bfe69e65680625b6db437af02`
- **Last Commit Date:** `2026-04-23T14:07:23+02:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 1254
- **Commands / CLI Scripts:** 164
- **Agent Definitions / Prompts:** 28
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 20
- **Test Files / Suites:** 274
- **CI / Workflow Files:** 17

## 2. Declared Lifecycle
Task management lifecycle with status transitions: `.claude/TM_COMMANDS_GUIDE.md:57` ("- `/project:tm/set-status/to-pending <id>`"), `.claude/TM_COMMANDS_GUIDE.md:58` ("- `/project:tm/set-status/to-in-progress <id>`"), and `.claude/TM_COMMANDS_GUIDE.md:59` ("- `/project:tm/set-status/to-done <id>`").

## 3. State & Artifact Files Written
- Task structures, dependencies, and project state (`README.md:38` ("A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.")).

## 4. WHO SETS "DONE"
CLI command marks task complete: `.claude/TM_COMMANDS_GUIDE.md:138` ("| `/project:task-master:complete` | `/project:tm/set-status/to-done` |").

## 5. Declared Verification Steps
Task dependency checks and status verification (`README.md:38` ("A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.")).

## 6. Declared Loop Controls
Taskmaster automation loop command: `README.md:56` ("- [Loop Command](https://tryhamster.com/docs/taskmaster/automation/loop)").

## 7. Declared Context Handling
Structured task dependencies and workstreams bounding context (`README.md:38` ("A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.")).

## 8. Declared Runtime / Host Support
Claude Code and Cursor AI MCP integration: `README.md:38` ("A task management system for AI-driven development with Claude, designed to work seamlessly with Cursor AI.") and `README.md:50` ("- [MCP Tools Reference](https://tryhamster.com/docs/taskmaster/capabilities/mcp)").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__taskmaster`)
- **Last Commit Date:** `2026-04-23T14:07:23+02:00` (verified against raw commit metadata)
- **Release Tags Count:** 92 releases/tags (verified against raw evidence `gh_releases__taskmaster`)
