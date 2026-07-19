# S-Class Plugin API & Schema Specifications

This document outlines the API interfaces, capabilities parameters, and schema structures required to develop and load S-Class plugins.

---

## 1. Plugin Metadata Schema (`plugin.json`)
Every plugin must declare its compatibility matrix and features:
```json
{
  "id": "sclass-v5",
  "name": "S-Class Engineering Pipeline",
  "version": "5.2.0",
  "author": "ak-bharadwaj",
  "description": "Short description...",
  "supports": ["FastAPI", "NextJS", "Python"],
  "executionModes": ["human", "assisted", "goal"]
}
```

---

## 2. Shared State Model (`state_schema.json`)
The shared state tracking uses standard lowercase JSON Schema parameters (`object`, `array`, `string`, `integer`, `number`):
*   `taskId`: Unique execution ID.
*   `currentPhase`: Current FSM State.
*   `retryCount`: Counter for self-healing loops.
*   `tasks`: Task queue list with dependencies (`dependsOn`).
*   `decisionLog`: Log entries detailing choices, alternatives, confidence, and timestamps.

---

## 3. Agent Capabilities Matrix (`capabilities.json`)
Enforces agent boundaries by setting true/false constraints:
*   `can_read`: Permission to read codebase files.
*   `can_write`: Permission to write or patch source code files.
*   `can_dispatch_events`: Permission to trigger FSM transition events.
*   `can_vote`: Permission to issue confidence scores during gates.
