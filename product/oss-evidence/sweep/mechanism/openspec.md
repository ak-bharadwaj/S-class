# Mechanism Sheet: OpenSpec

- **Canonical Repository:** [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)
- **Pinned Commit SHA:** `3e4d5f0769e2857c8eb54f149cbf5e4f703fa04c`
- **Last Commit Date:** `2026-11-04T17:05:54Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 1312
- **Commands / CLI Scripts:** 23
- **Agent Definitions / Prompts:** 64
- **Skills Directories / Files:** 102
- **Lifecycle / Git Hooks:** 0
- **Test Files / Suites:** 944
- **CI / Workflow Files:** 10

## 2. Declared Lifecycle
Specification validation and management lifecycle: `src/cli/commands/spec.ts:39` (".description('Validate a specification structure')").

## 3. State & Artifact Files Written
- Specification schemas and validation reports: `README.md:2` ('<a href="https://github.com/Fission-AI/OpenSpec">').

## 4. WHO SETS "DONE"
Spec validator checks specification completion: `src/cli/commands/spec.ts:38` (".command('validate [spec-id]')").

## 5. Declared Verification Steps
Automated spec validation commands: `src/cli/commands/spec.ts:11` ('console.error(\'Warning: The "openspec spec ..." commands are deprecated. Prefer verb-first commands (e.g., "openspec show", "openspec validate --specs").\');').

## 6. Declared Loop Controls
Synchronous command execution without unbounded polling loops (`README.md:2` ('<a href="https://github.com/Fission-AI/OpenSpec">')).

## 7. Declared Context Handling
Structured specification schemas bounding system context (`README.md:2` ('<a href="https://github.com/Fission-AI/OpenSpec">')).

## 8. Declared Runtime / Host Support
Node.js NPM package CLI: `README.md:12` ('<a href="https://www.npmjs.com/package/@fission-ai/openspec">').

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__openspec`)
- **Last Commit Date:** `2026-11-04T17:05:54Z` (verified against raw commit metadata)
- **Release Tags Count:** 56 releases/tags (verified against raw evidence `gh_releases__openspec`)
