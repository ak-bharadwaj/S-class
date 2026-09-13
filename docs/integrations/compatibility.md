# S-Class Integration Compatibility Matrix & Specification

## 1. Supported Agent Harnesses & Platforms

| Platform / Harness | Adapter Module | Native Protocol | Enforcement Hooks | Observation & Evidence | Claim Verification | Status |
|---|---|---|---|---|---|---|
| **Anthropic Claude Code** | `sclass.integrations.claude.adapter` | ACP / CLI wrapper | Pre-action bash/edit hook, permission requests (`ALLOW`, `DENY`, `APPROVAL`), secret shielding | Subprocess observation, exit code tracking, stdout/stderr capture | Pytest, unittest, jest, cargo, go structured test parsing | Full Production |
| **OpenAI Codex / ChatGPT CLI** | `sclass.integrations.codex.adapter` | CLI / Tool hooks | Action requests, tool authorization, protected resource blocking, subagent dispatch | Subagent observation, MCP gateway integration, terminal failure capture | Test claims, file change claims, build claims | Full Production |
| **Cursor IDE** | `sclass.integrations.cursor.adapter` | Composer hooks | `before_shell_execution`, `on_file_operation`, protected directory shielding (`.sclass/*`, `.env`) | Terminal error capture, composer event observation | Completion claim vs local ledger observation receipt | Full Production |
| **OpenCode / CodeSandbox** | `sclass.integrations.opencode.adapter` | ACP / WebSocket | `on_action`, `on_tool`, sandbox lifecycle hooks, token validation | Process tree observation, execution receipt provenance | Authoritative claim evaluation, handoff assembly | Full Production |
| **Model Context Protocol (MCP)** | `sclass.integrations.mcp.gateway` | JSON-RPC 2.0 (stdio / SSE) | Schema inspection, dynamic schema mutation invalidation, tool call authorization, resource URI access control | Tool execution receipts, stdout/stderr normalization, parameter auditing | Multi-tool composite claims, resource access verification | Full Production |
| **Agent Communication Protocol (ACP)** | `sclass.integrations.acp.adapter` | JSON-RPC 2.0 (stdio / HTTP) | 10 lifecycle methods: `initialize`, `session/new`, `prompt`, `session/update`, `permission`, `tool/action`, `cancellation`, `session/resume`, `session/fork`, `shutdown` | Full event stream normalization, session state tracking | Cross-agent handoff packages, cryptographic checkpoints | Full Production |
| **Generic Shell / CLI** | `sclass.integrations.generic.adapter` | POSIX / Win32 Process | Argument inspection, wrapper decomposition, environment scrubbing | Parent-child process tree tracking, exit code extraction | Standard verifier parsers (12 test runners) | Full Production |

---

## 2. Protocol Integration Details

### 2.1 Model Context Protocol (MCP)
- **Registry & Dynamic Mutation Protection**: `MCPToolRegistry` tracks tool definitions with a cryptographic schema hash. Any runtime tool mutation immediately revokes cached authorization, enforcing re-validation.
- **Protected Resources**: Resources matching `.env*`, `*.pem`, `*.key`, `credentials.json`, or `.sclass/trust/*` are classified as `ResourceKind.SECRET` and blocked from agent inspection unless explicitly approved.
- **Transport Modes**: Bidirectional stdio framing with length prefixes and HTTP/SSE streaming.

### 2.2 Agent Communication Protocol (ACP)
- **Lifecycle Guarantees**:
  - `initialize`: Negotiates capability flags (pre-action enforcement, post-action observation, cryptographic handoff).
  - `session/new` & `session/resume`: Restores or forks state from verified checkpoints without context hallucination.
  - `permission`: Resolves ambient capability escalation via explicit human-in-the-loop or policy rules.
  - `tool/action`: Authorizes every tool invocation against the active `TaskBoundary` and `TrustPolicy`.
- **Handoff Packaging**: Encapsulates repo HEAD commit, working tree dirty fingerprint, ledger head hash, task status, blockers, and single authoritative next action.

---

## 3. Supported Verifiers & Result Parsers

| Verifier / Tool | Binary Name | Command Formats | Result Parser | Normalized Output |
|---|---|---|---|---|
| Pytest | `pytest` | `pytest [options] [files]` | `PytestResultParser` | Discovered, passed, failed, skipped, duration |
| Unittest | `python -m unittest` | `python -m unittest [tests]` | `UnittestResultParser` | Test counts, failure stack traces, exit codes |
| Jest | `jest` / `npm test` | `jest [files]`, `npm test -- [files]` | `JestResultParser` | Suite counts, pass/fail counts, duration |
| Vitest | `vitest` | `vitest run [files]` | `VitestResultParser` | Structured test results, snapshot assertions |
| Mocha | `mocha` | `mocha [files]` | `MochaResultParser` | Spec counts, pending tests, execution time |
| Playwright | `playwright` | `playwright test [files]` | `PlaywrightResultParser` | Browser test counts, flaky tests, duration |
| Cargo Test | `cargo` | `cargo test [options]` | `CargoTestResultParser` | Doc-tests, unit tests, integration tests |
| Go Test | `go` | `go test [packages]` | `GoTestResultParser` | Package-level results, benchmark results, pass/fail |
| Package Scripts | `npm`, `pnpm`, `yarn`, `bun` | `[runner] test` | `PackageScriptResultParser` | Delegated verifier parsing, subprocess results |
