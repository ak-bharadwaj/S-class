# S-Class: The Trust Control Plane for Autonomous Software Engineering

## Why S-Class?

Modern AI coding agents (Claude Code, Cursor, Codex, OpenCode) are powerful but prone to hallucination, sycophancy, and premature claim declaration. Agents frequently:
- Claim a bug is fixed when tests are failing or not run.
- Declare a feature complete after running an unrelated command.
- Overwrite critical state files or introduce silent regressions.

S-Class sits between the Agent/IDE and the execution environment as an **independent trust control plane**:
- **Authoritative Execution Identity**: Verifies actual process image, true PID, and argument chains.
- **Cryptographic Auditability**: Sealed evidence receipts in an append-only hash chain.
- **Independent Verification**: Parses test output directly from process streams.
- **Seamless Multi-Agent Handoff**: Passes cryptographically verified checkpoints across agent boundaries.
