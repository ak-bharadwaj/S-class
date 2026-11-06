# Mechanism Sheet: Claude Plugins Ralph (Anthropic)

- **Canonical Repository:** [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)
- **Pinned Commit SHA:** `a1ecfbc7f138a0ef455088f7f28cda2d22a0f853`
- **Last Commit Date:** `2026-11-05T23:07:19-08:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 633
- **Commands / CLI Scripts:** 20
- **Agent Definitions / Prompts:** 63
- **Skills Directories / Files:** 161
- **Lifecycle / Git Hooks:** 90
- **Test Files / Suites:** 81
- **CI / Workflow Files:** 9

## 2. Declared Lifecycle
Plugin-based iterative execution loop: `plugins/ralph-loop/README.md:7` ("Ralph Loop is a development methodology based on continuous AI agent loops.") managed via a Stop hook: `plugins/ralph-loop/README.md:13` ("This plugin implements Ralph using a **Stop hook** that intercepts Claude's exit attempts:").

## 3. State & Artifact Files Written
- `.claude/ralph-loop.local.md`: State file tracking iteration and completion promise (`plugins/ralph-loop/hooks/stop-hook.sh:13` ('RALPH_STATE_FILE=".claude/ralph-loop.local.md"')).

## 4. WHO SETS "DONE"
Agent completes task and outputs completion promise: `plugins/ralph-loop/hooks/stop-hook.sh:138` ('echo "✅ Ralph loop: Detected <promise>$COMPLETION_PROMISE</promise>"'), allowing the session to exit (`plugins/ralph-loop/hooks/stop-hook.sh:140` ("exit 0")).

## 5. Declared Verification Steps
Iterative test execution and bug correction: `plugins/ralph-loop/README.md:1` ("# Ralph Loop Plugin").

## 6. Declared Loop Controls
Stop hook blocks normal exit and re-injects prompt (`plugins/ralph-loop/hooks/stop-hook.sh:185` ('"decision": "block",')), bounded by max iterations (`plugins/ralph-loop/README.md:56` ('/ralph-loop "<prompt>" --max-iterations <n> --completion-promise "<text>"')).

## 7. Declared Context Handling
Self-referential feedback loop in session: `plugins/ralph-loop/README.md:17` ('/ralph-loop "Your task description" --completion-promise "DONE"').

## 8. Declared Runtime / Host Support
Claude Code plugin marketplace: `plugins/ralph-loop/README.md:1` ("# Ralph Loop Plugin").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__claude-plugins-ralph`)
- **Last Commit Date:** `2026-11-05T23:07:19-08:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__claude-plugins-ralph`)
