# 🚀 CONTINUE_HERE.md — S-Class Session Continuity Guide

> **Notice**: This repository is governed by the S-Class v6 Control Plane.
> All incoming agents (Cursor, Claude Code, GitHub Copilot, Antigravity) must adhere to these directives.

---

## 📍 System Status
- **Control Plane**: S-Class v6.0.0
- **Profiles**: 10 adaptive profiles with zero-bypass hook enforcement
- **Interception Gates**: `PreToolUse` (hard denial of secret leaks/tampering) and `Stop` (anti-fake-completion gate)

## ⚡ Primary Commands
```bash
# Classify an engineering goal
python sclass_cli.py classify "Implement feature X"

# Run full live demo verification
python -m pytest tests/integration/test_expo_live_demonstration.py -v
python -m pytest tests/integration/test_hook_interception_live.py -v
```

## 🛠️ Operating Rules
1. **Inspect Before Infer**: Always inspect existing schemas, tests, and configurations before modifying code.
2. **Deterministic Verification**: Verify all modifications with targeted pytest assertions.
3. **Zero Secrets**: Never embed hardcoded tokens or API keys; reference environment variables.
