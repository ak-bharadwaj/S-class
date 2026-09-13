<div align="center">

# S-Class

### Authoritative Verification for AI Coding Agents

[![Version](https://img.shields.io/badge/version-0.1.0--survival-blue.svg)](https://github.com/ak-bharadwaj/S-class/tree/survival-v0)
[![Tests](https://img.shields.io/badge/tests-334%20passed-brightgreen.svg)](https://github.com/ak-bharadwaj/S-class/tree/survival-v0)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](LICENSE)

</div>


---

## What?

**S-Class verifies what AI coding agents actually did.**

## Why?

AI agents can modify your code, run commands, and claim completion. S-Class checks whether those claims are supported by independent evidence.

## How?

```
Agent ──▶ S-Class Authorization ──▶ Action Execution ──▶ Evidence Receipt ──▶ Verification
```

---

## Demo

### 1. Fake Completion Rejected
```text
Agent:
"All tests pass."

S-Class:
✕ 2 tests failed
Completion rejected.
```

### 2. Destructive Action Blocked
```text
Agent:
"I need to run rm -rf .agents/qa_report.json"

S-Class:
✕ Action blocked.
[SCLASS-EVID-001] Tampering with protected authority artifact is prohibited.
```

### 3. Genuine Completion Verified
```text
Agent:
"Implemented feature."

S-Class:
✓ Changes verified (src/auth.py, tests/test_auth.py)
✓ Tests passed (18 passed, exit code 0)
✓ Evidence recorded in tamper-evident ledger
```

---

## 30-Second Quickstart

### Native Workflow (Silent Governance)

You don't need to change how you code or invoke agents. S-Class silently governs behind the scenes:

```bash
# Initialize hooks in your current workspace
python hook_runner.py --platform claude_code --event-type session_start

# Check current status & verification ledger
python sclass_cli.py status
```

Works out of the box with:
- **Claude Code** (`.claude/settings.local.json`) — Reference integration (blocking pre-tool hooks)
- **Cursor 1.7+** (`.cursor/hooks.json`) — Discrete allow/deny protocol
- **OpenAI Codex CLI** (`.codex/hooks.json`)
- **Google Antigravity** (`.agents/hooks.json`)

---

## Core Product Primitives

### 1. Canonical Authorization (`authorize`)
Platform events are normalized into a vendor-agnostic request before reaching policy rules:
- **Zero Secret Leakage:** High-confidence credentials are automatically blocked and redacted (`Value: [REDACTED]`, fingerprint correlation only). Secrets never appear in stdout, stderr, logs, or diagnostics.
- **Fail-Closed:** Unhandled hook exceptions immediately fail closed to `DENY`.
- **Authority Boundaries:** Agents cannot modify, delete, or overwrite `.agents/receipts/`, `.agents/ledger/`, or `.agents/verification/`.

### 2. Independent Evidence Receipts (`EvidenceReceipt`)
The agent is **never** authoritative for:
- Command exit codes
- Modified files
- Test pass/fail counts
- Task completion status

All evidence is observed independently from operating system subprocesses and git repository state.

### 3. Claim → Evidence Verifier (`verify`)
Evaluates agent assertions against cryptographic receipts:
- Rejects claims with failed tests (`exit_code != 0`).
- Rejects fabricated or forged evidence receipts.
- Invalidates verification if repository state changes after execution.
- Rejects completion claims produced without evidence.

### 4. Tamper-Evident Local Ledger (`LocalLedger`)
Every authorization and verification event is cryptographically linked in an append-only chain:
```json
{
  "sequence": 42,
  "event": "verification",
  "previous_hash": "a1b2c3d4...",
  "payload_hash": "e5f6g7h8...",
  "timestamp": "2026-09-13T08:00:00Z",
  "signature": "99aabbcc..."
}
```

---

## Running the Verification Suite

```bash
# Run the 10 adversarial attack tests + golden integration fixture
python -m pytest tests/survival/

# Run the complete test suite (334 tests)
python -m pytest
```

---

## 🔒 License & Legal Notice

**Copyright (c) 2026 ak-bharadwaj. All Rights Reserved.**

S-Class is **Proprietary and Confidential Software**. See [LICENSE](LICENSE) for details.
