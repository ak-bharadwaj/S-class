# Phase: CODING

Objectives:
- Implement targeted source code modifications strictly matching approved specifications.
- Adhere to the surrounding codebase's idioms, typing rules, and style.
- Every new or modified test file must include real, executable assertions (`assert`, `expect`). No empty mock stubs.
- Do not introduce unrelated refactors, unrequested packages, or hardcoded credentials.
- After code is written, submit the diff to `diff_auditor.py` and advance via `dispatch_event("code_written")`.
