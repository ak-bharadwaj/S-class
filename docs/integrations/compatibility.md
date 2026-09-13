# Integration Compatibility Matrix

| Platform / Harness | Adapter Module | Execution Capture | Boundary Enforcement | Status |
|---|---|---|---|---|
| Anthropic Claude Code | `sclass.integrations.claude` | ProcessRunner / HostArgv | Enforced | Supported & Verified |
| OpenAI Codex / ChatGPT CLI | `sclass.integrations.codex` | ProcessRunner / HostArgv | Enforced | Supported & Verified |
| Cursor IDE | `sclass.integrations.cursor` | ProcessRunner / HostArgv | Enforced | Supported & Verified |
| OpenCode | `sclass.integrations.opencode` | ProcessRunner / HostArgv | Enforced | Supported & Verified |
| Model Context Protocol (MCP) | `sclass.integrations.mcp` | Tool Gating / Arg Inspection | Enforced | Supported & Verified |
| Agent Communication Protocol (ACP) | `sclass.integrations.acp` | Event Normalization | Enforced | Supported & Verified |
| Generic Shell / CLI | `sclass.integrations.generic` | ProcessRunner | Enforced | Supported & Verified |
