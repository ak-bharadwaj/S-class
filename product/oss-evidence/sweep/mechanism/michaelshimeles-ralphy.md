# Mechanism Sheet: Ralphy (michaelshimeles)

- **Canonical Repository:** [michaelshimeles/ralphy](https://github.com/michaelshimeles/ralphy)
- **Pinned Commit SHA:** `506eea0e7d72c8eeb96dd2f697363bef396add34`
- **Last Commit Date:** `2026-02-05T19:28:20+03:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 105
- **Commands / CLI Scripts:** 75
- **Agent Definitions / Prompts:** 0
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 2
- **Test Files / Suites:** 6
- **CI / Workflow Files:** 0

## 2. Declared Lifecycle
Automated multi-engine task execution lifecycle: parses tasks -> executes engine -> checks test output -> marks status (`ralphy.sh:2038`).

## 3. State & Artifact Files Written
- `.claude/skills/`: Injected execution skills (`cli/src/execution/prompt.ts:24`)
- `PRD.json`: Task list and status tracking (`README.md:162`)
- Temporary status files written per task (`ralphy.sh:2366`)

## 4. WHO SETS "DONE"
Script writes completion token when task passes: `ralphy.sh:2366` ("echo 'done' > '$status_file'") after test execution succeeds.

## 5. Declared Verification Steps
Automatic test runner execution: `ralphy.sh:1463` ("elif echo '$content' | grep -qE 'vitest|jest|bun test|npm test|pytest|go test'; then"). Script actively runs workspace test suites.

## 6. Declared Loop Controls
Iteration limit controls: `ralphy.sh:33` (`MAX_ITERATIONS=0 # 0 = unlimited`), `ralphy.sh:844` (`MAX_ITERATIONS="${2:-0}"`).

## 7. Declared Context Handling
Engine-dependent context reset per task loop iteration (`ralphy.sh:1443`).

## 8. Declared Runtime / Host Support
Multi-engine CLI supporting Claude Code, OpenCode, Codex, Cursor, Qwen-Code, and Factory Droid (`ralphy.sh:5`, `ralphy.sh:30`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** See raw (verified against raw evidence `gh_license__michaelshimeles-ralphy`)
- **Last Commit Date:** `2026-02-05T19:28:20+03:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__michaelshimeles-ralphy`)
