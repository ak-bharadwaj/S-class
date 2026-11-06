# Mechanism Sheet: Ralphy (Michael Shimeles)

- **Canonical Repository:** [michaelshimeles/ralphy](https://github.com/michaelshimeles/ralphy)
- **Pinned Commit SHA:** `506eea0e7d72c8eeb96dd2f697363bef396add34`
- **Last Commit Date:** `2026-02-05T19:28:20+03:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 105
- **Commands / CLI Scripts:** 75
- **Agent Definitions / Prompts:** 3
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 2
- **Test Files / Suites:** 6
- **CI / Workflow Files:** 0

## 2. Declared Lifecycle
Autonomous coding loop running until completion: `ralphy.sh:4` ("# Ralphy - Autonomous AI Coding Loop") and `ralphy.sh:6` ("# Runs until PRD is complete").

## 3. State & Artifact Files Written
- Progress tracking file: `ralphy.sh:19` ('PROGRESS_FILE="$RALPHY_DIR/progress.txt"')
- Configuration YAML: `ralphy.sh:20` ('CONFIG_FILE="$RALPHY_DIR/config.yaml"')

## 4. WHO SETS "DONE"
Loop runner notifies done and writes status: `ralphy.sh:1500` ("notify_done() {"), displaying completion `ralphy.sh:2038` ('printf "  ${GREEN}✓${RESET} %-16s │ %s\n" "Done"') and writing `ralphy.sh:2366` ('echo "done" > "$status_file"').

## 5. Declared Verification Steps
Automated lint and test checks: `ralphy.sh:28` ("SKIP_TESTS=false") and `ralphy.sh:29` ("SKIP_LINT=false").

## 6. Declared Loop Controls
Max iterations control: `ralphy.sh:33` ("MAX_ITERATIONS=0  # 0 = unlimited") with retry handling `ralphy.sh:34` ("MAX_RETRIES=3").

## 7. Declared Context Handling
Fresh execution invocations per task across supported AI engines: `ralphy.sh:30` ('AI_ENGINE="claude"').

## 8. Declared Runtime / Host Support
Multi-engine CLI runner: `ralphy.sh:5` ("# Supports Claude Code, OpenCode, Codex, Cursor, Qwen-Code and Factory Droid").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__michaelshimeles-ralphy`)
- **Last Commit Date:** `2026-02-05T19:28:20+03:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__michaelshimeles-ralphy`)
