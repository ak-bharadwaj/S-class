# Phase: QA & TASK_VERIFICATION

Objectives:
- Run targeted automated test suites (`pytest`, `npm test`) and require 100% green exit codes.
- For UI components and web applications:
  - Capture real screenshots using Chrome DevTools MCP.
  - Verify layout integrity and responsive viewport rendering.
  - Check browser console messages and fail on uncaught JavaScript errors or HTTP 500 API responses.
- Reject solid-fill synthetic bitmaps or zero-entropy mock evidence.
- Advance to merge/release via `dispatch_event("qa_passed")` or `dispatch_event("task_verified")`.
