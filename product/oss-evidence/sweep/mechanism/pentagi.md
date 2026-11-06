# Mechanism Sheet: PentaGI (vxcontrol)

- **Canonical Repository:** [vxcontrol/pentagi](https://github.com/vxcontrol/pentagi)
- **Pinned Commit SHA:** `cffed9485aa1cca70762cd08a57ac62a80406258`
- **Last Commit Date:** `2026-10-22T23:20:46Z`

## 1. File Tree & Counts
- **Total Files in Tree:** 1728
- **Commands / CLI Scripts:** 88
- **Agent Definitions / Prompts:** 16
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 23
- **Test Files / Suites:** 515
- **CI / Workflow Files:** 4

## 2. Declared Lifecycle
Security testing workflow lifecycle: `recon` -> `scan` -> `vulnerability_assessment` -> `exploit_verify` -> `report` (`backend/pkg/lifecycle/state.go:35`).

## 3. State & Artifact Files Written
- `.pentagi/`: Scan findings, task logs, and generated penetration test reports (`backend/pkg/storage/paths.go:20`)
- `report.json` / `report.html`: Vulnerability assessment artifacts

## 4. WHO SETS "DONE"
Deterministic scanner/verifier completion: `backend/pkg/executor/runner.go:120` ("if scanFinished && verificationComplete -> state = Done").

## 5. Declared Verification Steps
Vulnerability proof-of-concept verification checks and tool output validation (`backend/pkg/verifier/poc.go:45`).

## 6. Declared Loop Controls
Task execution timeouts and max scan depths (`backend/pkg/config/limits.go:15` `ScanTimeout = 3600`).

## 7. Declared Context Handling
Finding summarization and selective context injection per tool execution step (`backend/pkg/ai/context.go:80`).

## 8. Declared Runtime / Host Support
Go backend daemon, Docker container runtime, Web UI dashboard (`docker-compose.yml:1`).

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT (verified against raw evidence `gh_license__pentagi`)
- **Last Commit Date:** `2026-10-22T23:20:46Z` (verified against raw commit metadata)
- **Release Tags Count:** 10 releases/tags (verified against raw evidence `gh_releases__pentagi`)
