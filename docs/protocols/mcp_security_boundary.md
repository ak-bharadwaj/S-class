# Model Context Protocol (MCP) Security Boundaries

## 1. Overview
S-Class wraps Model Context Protocol servers to enforce strict zero-trust credential scanning
and argument validation before tool execution.

## 2. Fail-Closed Tool Gate
- All incoming MCP tool requests pass through Layer B policy.
- Unregistered tools or unknown schema parameters are blocked immediately.
