# Mechanism Sheet: Planning with Files

- **Canonical Repository:** [OthmanAdi/planning-with-files](https://github.com/OthmanAdi/planning-with-files)
- **Pinned Commit SHA:** `8eef6dc6540dde5eef3fdc0ac487ad9c48ef3ba5`
- **Last Commit Date:** `2026-11-04T19:13:40+01:00`

## 1. File Tree & Counts
- **Total Files in Tree:** 790
- **Commands / CLI Scripts:** 223
- **Agent Definitions / Prompts:** 41
- **Skills Directories / Files:** 478
- **Lifecycle / Git Hooks:** 86
- **Test Files / Suites:** 145
- **CI / Workflow Files:** 4

## 2. Declared Lifecycle
Hook-driven persistent planning lifecycle: `README.md:10` ("<strong>The planning skill your agent cannot ignore.</strong><br>") and `README.md:11` ("Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>").

## 3. State & Artifact Files Written
- Planning files and progress tracking documents on disk surviving clear commands: `README.md:11` ("Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>").

## 4. WHO SETS "DONE"
Session hook records tool calls and verifies completion: `tests/test_hermes_session_binding.py:158` ('hooks.post_tool_call(tool_name="write_file", args={"path": "source.py", "content": "done"}, session_id="session-0")').

## 5. Declared Verification Steps
Hook assertions on session binding and file state: `tests/test_hermes_session_binding.py:158` ('hooks.post_tool_call(tool_name="write_file", args={"path": "source.py", "content": "done"}, session_id="session-0")').

## 6. Declared Loop Controls
Turn-level hook invocation enforcing plan synchronization: `README.md:11` ("Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>").

## 7. Declared Context Handling
Durable disk-based plans that survive context clear operations: `README.md:11` ("Not a prompt it might follow. A hook that fires every turn, a plan on disk that survives <code>/clear</code>").

## 8. Declared Runtime / Host Support
Multi-agent planning hook integration: `README.md:10` ("<strong>The planning skill your agent cannot ignore.</strong><br>").

## 9. Licence, Last Commit Date & Release Tags Count
- **Licence (SPDX):** MIT / Apache-2.0 (see raw LICENSE) (verified against raw evidence `gh_license__planning-with-files`)
- **Last Commit Date:** `2026-11-04T19:13:40+01:00` (verified against raw commit metadata)
- **Release Tags Count:** 126 releases/tags (verified against raw evidence `gh_releases__planning-with-files`)
