# Mechanism Sheet: Claude Plugins Official (Ralph Plugin)

- **Canonical Repository:** [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official)
- **Pinned Commit SHA:** `1aa4a4b10e6c5e8694d0f72a03dbac4e93bcafd8`
- **Last Commit Date:** `2026-11-05T18:04:05-08:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 619
- **Commands / CLI Scripts:** 22
- **Agent Definitions / Prompts:** 55
- **Skills Directories / Files:** 161
- **Lifecycle / Git Hooks:** 90
- **Test Files / Suites:** 79
- **CI / Workflow Files:** 9

## 2. Declared Lifecycle
Official Anthropic plugins packaging repository containing Ralph plugin workflows: `install` -> `configure` -> `invoke` (`plugins/ralph/`).

## 3. State & Artifact Files Written
- `.claude-plugin/`: Plugin registration manifest and skill declarations (`plugins/ralph/.claude-plugin/plugin.json:1`)
- `skills/`: Packaged workflow skills

## 4. WHO SETS "DONE"
Agent evaluation against skill criteria (`plugins/ralph/skills/ralph/SKILL.md:1`).

## 5. Declared Verification Steps
Plugin schema validation and automated test checks (`tests/plugins.test.ts:1`).

## 6. Declared Loop Controls
Invocation bounds defined by Claude host environment.

## 7. Declared Context Handling
Skills invoked on-demand to maintain clean context window.

## 8. Declared Runtime / Host Support
Claude Desktop, Claude Code, Anthropic Plugins host infrastructure (`README.md:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** Apache-2.0 (verified against raw evidence `gh_license__claude-plugins-ralph`)
- **Last Commit Date:** `2026-11-05T18:04:05-08:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__claude-plugins-ralph`)
