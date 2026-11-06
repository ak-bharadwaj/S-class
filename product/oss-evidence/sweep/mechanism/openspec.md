# Mechanism Sheet: OpenSpec (Fission-AI)

- **Canonical Repository:** [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)
- **Pinned Commit SHA:** `3e4d5f0769e2857c8eb54f149cbf5e4f703fa04c`
- **Last Commit Date:** `2026-11-04T17:05:54Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 1312
- **Commands / CLI Scripts:** 193
- **Agent Definitions / Prompts:** 60
- **Skills Directories / Files:** 102
- **Lifecycle / Git Hooks:** 0
- **Test Files / Suites:** 250
- **CI / Workflow Files:** 5

## 2. Declared Lifecycle
Proposal-to-implementation lifecycle: `RFC` -> `Draft` -> `Review` -> `Accepted` -> `Implemented` (`spec/lifecycle.md:12`).

## 3. State & Artifact Files Written
- `openspec.yaml`: Project specification manifest (`openspec.yaml:1`)
- `specs/`: Directory of modular capability specs and schemas
- `.openspec/`: Cache and resolution state

## 4. WHO SETS "DONE"
Schema validator and human reviewer sign-off: `src/validator.ts:88` (`validateSpecCompletion()`).

## 5. Declared Verification Steps
Automated JSON Schema and OpenAPI validation tests (`tests/schema.spec.ts:1`, `tests/validate.test.ts:45`).

## 6. Declared Loop Controls
Bounded schema compilation and validation passes (`src/compiler.ts:120`).

## 7. Declared Context Handling
Modular specification bundling to fit within LLM context windows (`src/bundler.ts:40`).

## 8. Declared Runtime / Host Support
Node.js / TypeScript CLI (`openspec`), schema verification libraries (`package.json:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__openspec`)
- **Last Commit Date:** `2026-11-04T17:05:54Z` (verified against raw commit metadata)
- **Release Tags Count:** 56 releases/tags (verified against raw evidence `gh_releases__openspec`)
