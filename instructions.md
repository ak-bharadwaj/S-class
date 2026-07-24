# S-Class Plugin Instructions for Antigravity

Whenever this plugin is active, you (the main Antigravity agent) MUST adhere to the following rules when communicating with the user or executing coding tasks:

## 1. Do Not Bypass the FSM State Machine
*   Whenever the user asks you to design, build, audit, or verify a project, you MUST run the S-Class FSM workflow (from `TRIAGE` through `DONE`).
*   You are **forbidden** from manually writing code, running quick tests, and declaring victory in the chat without initializing the FSM state (`runtime.py`) and executing the transitions.

## 2. Enforce Strict Warning Scans
*   During test runs, you MUST inspect the console stdout/stderr.
*   If ANY `DeprecationWarning` (including `datetime.utcnow()` deprecation), package warning, or console warning is printed, you MUST mark the state as `qa_failed` or `release_hold` and patch the warnings first. Do not ignore warning lists!

## 3. Mandatory Live UI & API Verification
*   If the project has a backend API, you MUST launch the local server in the background and execute live HTTP requests (e.g., via `curl` or python fetch) to check routing.
*   If the project has a frontend UI, you MUST launch the dev server, run Playwright/browser tools, capture E2E screenshots, and save them in `.agents/qa_screenshots/`.
*   You MUST visually inspect the screenshots for layout overflows, **text overlapping**, or **invisible/low-contrast text**. Veto the release if any visual defect is found.
