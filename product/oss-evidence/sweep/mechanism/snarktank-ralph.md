# Mechanism Sheet: Ralph (snarktank)

- **Canonical Repository:** [snarktank/ralph](https://github.com/snarktank/ralph)
- **Pinned Commit SHA:** `6c53cb0b831ebe8739c6a003e22af14902d8b0b5`
- **Last Commit Date:** `2026-02-01T20:46:21-05:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 31
- **Commands / CLI Scripts:** 1
- **Agent Definitions / Prompts:** 3
- **Skills Directories / Files:** 2
- **Lifecycle / Git Hooks:** 0
- **Test Files / Suites:** 0
- **CI / Workflow Files:** 1

## 2. Declared Lifecycle
No multi-state lifecycle is defined in the repo; task execution is binary. The loop picks a story where passes is false (`prompt.md:10` ("4. Pick the **highest priority** user story where `passes: false`")), runs implementation, and updates status upon completion (`prompt.md:15` ("9. Update the PRD to set `passes: true` for the completed story")).

## 3. State & Artifact Files Written
- `prd.json`: PRD artifact tracking stories and status (`ralph.sh:37` ('PRD_FILE="$SCRIPT_DIR/prd.json"'))
- `progress.txt`: Append-only progress log (`ralph.sh:38` ('PROGRESS_FILE="$SCRIPT_DIR/progress.txt"'))

## 4. WHO SETS "DONE"
Done flag is set by the agent: `prompt.md:15` ("9. Update the PRD to set `passes: true` for the completed story"). When all stories pass (`prompt.md:96` ("After completing a user story, check if ALL stories have `passes: true`.")), the agent emits the completion promise (`prompt.md:99` ("<promise>COMPLETE</promise>")), detected by the loop runner (`ralph.sh:99` ('if echo "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then')), which exits successfully (`ralph.sh:103` ("exit 0")).

## 5. Declared Verification Steps
Project quality checks: `prompt.md:78` ("- ALL commits must pass your project's quality checks (typecheck, lint, test)") and browser verification for UI changes: `prompt.md:83` ("## Browser Testing (Required for Frontend Stories)").

## 6. Declared Loop Controls
Bash loop iteration cap: `ralph.sh:9` ("MAX_ITERATIONS=10").

## 7. Declared Context Handling
Fresh context per loop iteration: `README.md:163` ("Each Iteration = Fresh Context"). The loop spawns a brand new Claude / Amp CLI process per task, avoiding context degradation.

## 8. Declared Runtime / Host Support
CLI runner supporting Amp and Claude Code: `ralph.sh:3` ("# Usage: ./ralph.sh [--tool amp|claude] [max_iterations]").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__snarktank-ralph`)
- **Last Commit Date:** `2026-02-01T20:46:21-05:00` (verified against raw commit metadata)
- **Release Tags Count:** 0 releases/tags (verified against raw evidence `gh_releases__snarktank-ralph`)
