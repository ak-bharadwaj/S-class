# Mechanism Sheet: Beads

- **Canonical Repository:** [gastownhall/beads](https://github.com/gastownhall/beads)
- **Pinned Commit SHA:** `8c3eb30f30f7fbb509d80cd12cb13e54bdbbb45d`
- **Last Commit Date:** `2026-11-06T03:55:10Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 5303
- **Commands / CLI Scripts:** 2018
- **Agent Definitions / Prompts:** 55
- **Skills Directories / Files:** 57
- **Lifecycle / Git Hooks:** 120
- **Test Files / Suites:** 2776
- **CI / Workflow Files:** 23

## 2. Declared Lifecycle
Explicit multi-state issue lifecycle: `open` -> `in_progress` -> `blocked` -> `closed` (done/wontfix/duplicate) (`claim.go:24`, `issue_lifecycle_external_test.go:42`). Transitions enforced through Go API / CLI `bd` commands (`claim_roundtrip_test.go:66`).

## 3. State & Artifact Files Written
- `.beads/`: Local SQLite database and config (`open_nocgo_test.go:19`)
- `issues.jsonl`: Portable JSONL issue ledger (`issues.jsonl:1`, `export_dependency_add_options_test.go:12`)
- `.beads/metadata.json`: Storage and compaction state (`VERSIONED-BEADS-WRITE-PATHS.md:45`)

## 4. WHO SETS "DONE"
CLI command or verifier closes issue: `CHANGELOG.md:15617` ("Example: `bd close bd-1 bd-2 bd-3 --reason 'Done'`") and `claim_roundtrip_test.go:66` ("store.CloseIssue(ctx, 'rt-2', 'done', 'tester', '')").

## 5. Declared Verification Steps
Deterministic data store integrity checks: `query_interfaces_test.go:80`, full regression scenario tests `tests/regression/scenarios_test.go:70`, and git diff consistency on export `CHANGELOG.md:16024` ("Export sorts issues by ID for consistent git diffs").

## 6. Declared Loop Controls
Network dialing and response header timeouts: `beads_test.go:58` (`net.DialTimeout("tcp", addr, 200*time.Millisecond)`), `README.md:280` (`BEADS_HTTP_RESPONSE_HEADER_TIMEOUT=30s`). CLI commands execute synchronously without unbounded polling.

## 7. Declared Context Handling
Semantic compaction and memory decay: `README.md:65` ("Compaction: Semantic 'memory decay' summarizes old closed tasks to save context window.") and `PROPOSAL-pluggable-storage-backends.md:130` (`CompactionStore`).

## 8. Declared Runtime / Host Support
Command-line tool (`bd`), Go library/SDK (`beads.go`), CGO and pure non-CGO backends (`beads_nocgo.go`), Bazel/Nix builds (`BUILD.bazel:1`, `default.nix:1`), and NPM package (`npm-package/package.json:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__beads`)
- **Last Commit Date:** `2026-11-06T03:55:10Z` (verified against raw commit metadata)
- **Release Tags Count:** 111 releases/tags (verified against raw evidence `gh_releases__beads`)
