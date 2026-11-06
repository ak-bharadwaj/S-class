# Mechanism Sheet: Agent OS

- **Canonical Repository:** [buildermethods/agent-os](https://github.com/buildermethods/agent-os)
- **Pinned Commit SHA:** `e892e61d322759165e7d9173e92c1010406c9f4d`
- **Last Commit Date:** `2026-10-07T00:18:58-04:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 22
- **Commands / CLI Scripts:** 3
- **Agent Definitions / Prompts:** 5
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 0
- **Test Files / Suites:** 1
- **CI / Workflow Files:** 4

## 2. Declared Lifecycle
Interactive spec shaping and product planning workflow: `README.md:5` ("[Agent OS](https://buildermethods.com/agent-os) helps you shape better specs") creating product documentation (`commands/agent-os/plan-product.md:3` ("Establish foundational product documentation through an interactive conversation. Creates mission, roadmap, and tech stack files in `agent-os/product/`.")).

## 3. State & Artifact Files Written
- Mission, roadmap, and tech stack files: `commands/agent-os/plan-product.md:3` ("Establish foundational product documentation through an interactive conversation. Creates mission, roadmap, and tech stack files in `agent-os/product/`.").

## 4. WHO SETS "DONE"
User signs off via interactive questions: `commands/agent-os/plan-product.md:7` ("- **Always use AskUserQuestion tool** when asking the user anything").

## 5. Declared Verification Steps
Lightweight guidelines and spec consistency checks: `commands/agent-os/plan-product.md:8` ("- **Keep it lightweight** — gather enough to create useful docs without over-documenting").

## 6. Declared Loop Controls
Single-question interactive guidance loop: `commands/agent-os/plan-product.md:7` ("- **Always use AskUserQuestion tool** when asking the user anything").

## 7. Declared Context Handling
Lightweight spec files keeping agent aligned without over-documenting: `commands/agent-os/plan-product.md:8` ("- **Keep it lightweight** — gather enough to create useful docs without over-documenting").

## 8. Declared Runtime / Host Support
CLI commands and standards profiles: `README.md:3` ("## Agents that build the way you would").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__agent-os`)
- **Last Commit Date:** `2026-10-07T00:18:58-04:00` (verified against raw commit metadata)
- **Release Tags Count:** 12 releases/tags (verified against raw evidence `gh_releases__agent-os`)
