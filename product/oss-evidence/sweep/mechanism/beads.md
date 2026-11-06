# Mechanism Sheet: Beads

- **Canonical Repository:** [gastownhall/beads](https://github.com/gastownhall/beads)
- **Pinned Commit SHA:** `8c3eb30f30f7fbb509d80cd12cb13e54bdbbb45d`
- **Last Commit Date:** `2026-11-06T03:55:10Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 5303
- **Commands / CLI Scripts:** 263
- **Agent Definitions / Prompts:** 54
- **Skills Directories / Files:** 57
- **Lifecycle / Git Hooks:** 119
- **Test Files / Suites:** 2782
- **CI / Workflow Files:** 28

## 2. Declared Lifecycle
Discrete issue lifecycle transitions executed through API / CLI calls (`claim_roundtrip_test.go:66` ('if err := store.CloseIssue(ctx, "rt-2", "done", "tester", ""); err != nil {')).

## 3. State & Artifact Files Written
- Local store and version journals: `VERSIONED-BEADS-WRITE-PATHS.md:1` ("# Versioned Beads: issue-plane write paths and their Phase 2 disposition")
- Issue ops version history seam: `VERSIONED-BEADS-WRITE-PATHS.md:14` ("The seam is `issueops.RecordVersionInTx` in internal/storage/issueops/version_history.go (line 87 at")

## 4. WHO SETS "DONE"
CLI command or test verifier closes issue: `CHANGELOG.md:15617` ('- Example: `bd close bd-1 bd-2 bd-3 --reason "Done"`') and programmatic close in `claim_roundtrip_test.go:66` ('if err := store.CloseIssue(ctx, "rt-2", "done", "tester", ""); err != nil {').

## 5. Declared Verification Steps
Storage assertions, regression tests, and database transactions: `claim_roundtrip_test.go:66` ('if err := store.CloseIssue(ctx, "rt-2", "done", "tester", ""); err != nil {').

## 6. Declared Loop Controls
Network dialing timeouts: `beads_test.go:58` ('net.DialTimeout("tcp", addr, 200*time.Millisecond)'). CLI executes synchronously without unbounded loops.

## 7. Declared Context Handling
Semantic memory compaction: `README.md:65` ('* **Compaction:** Semantic "memory decay" summarizes old closed tasks to save context window.').

## 8. Declared Runtime / Host Support
Go library and CLI tool: `beads.go:1` ("// Package beads provides a minimal public API for extending bd with custom orchestration.").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__beads`)
- **Last Commit Date:** `2026-11-06T03:55:10Z` (verified against raw commit metadata)
- **Release Tags Count:** 111 releases/tags (verified against raw evidence `gh_releases__beads`)
