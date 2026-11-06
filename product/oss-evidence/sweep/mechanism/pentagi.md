# Mechanism Sheet: PentAGI

- **Canonical Repository:** [vxcontrol/pentagi](https://github.com/vxcontrol/pentagi)
- **Pinned Commit SHA:** `cffed9485aa1cca70762cd08a57ac62a80406258`
- **Last Commit Date:** `2026-10-23T06:20:46+07:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 1728
- **Commands / CLI Scripts:** 20
- **Agent Definitions / Prompts:** 83
- **Skills Directories / Files:** 0
- **Lifecycle / Git Hooks:** 23
- **Test Files / Suites:** 537
- **CI / Workflow Files:** 6

## 2. Declared Lifecycle
Multi-agent flow lifecycle transitions: `backend/docs/controller.md:669` ("- `Created` (database.FlowStatusCreated)"), `backend/docs/controller.md:670` ("- `Running` (database.FlowStatusRunning)"), `backend/docs/controller.md:671` ("- `Waiting` (database.FlowStatusWaiting)"), `backend/docs/controller.md:672` ("- `Finished` (database.FlowStatusFinished)"), and `backend/docs/controller.md:673` ("- `Failed` (database.FlowStatusFailed)").

## 3. State & Artifact Files Written
- Penetration testing reports and Docker sandbox logs: `README.md:60` ("PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.").

## 4. WHO SETS "DONE"
Flow controller updates status to finished: `backend/docs/controller.md:195` ("SetStatus(ctx context.Context, status database.FlowStatus) error") and `backend/docs/controller.md:672` ("- `Finished` (database.FlowStatusFinished)").

## 5. Declared Verification Steps
Security tool output analysis and automated verifier checks inside Docker sandbox: `README.md:60` ("PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.").

## 6. Declared Loop Controls
State-machine flow transitions with terminal Finished/Failed states: `backend/docs/controller.md:672` ("- `Finished` (database.FlowStatusFinished)").

## 7. Declared Context Handling
Multi-agent memory and isolated Docker container environments: `README.md:60` ("PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.").

## 8. Declared Runtime / Host Support
Self-hosted Go backend and Docker sandbox: `README.md:60` ("PentAGI is an open-source, self-hosted multi-agent system for autonomous penetration testing.").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__pentagi`)
- **Last Commit Date:** `2026-10-23T06:20:46+07:00` (verified against raw commit metadata)
- **Release Tags Count:** 10 releases/tags (verified against raw evidence `gh_releases__pentagi`)
