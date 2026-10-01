# Agent Client Protocol (ACP) Specification

## 1. Protocol Architecture
ACP standardizes communication between developer IDEs and S-Class:
```text
[IDE / Editor] ──(JSON-RPC 2.0 ACP)──▶ [S-Class Proxy] ──▶ [Coding Agent]
```

## 2. Core RPC Methods
- `acp.session.initialize`: Initialize coding session and exchange capability matrix.
- `acp.action.request`: Submit action candidate for Layer B policy authorization.
- `acp.action.observe`: Stream physical execution receipts to Layer E observer.
