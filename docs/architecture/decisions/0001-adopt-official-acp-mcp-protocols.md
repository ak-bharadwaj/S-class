# ADR 0001: Adopt Official ACP and MCP Protocols

## Status
Accepted

## Context
Earlier iterations of S-Class experimented with synthetic JSON-RPC models and custom Pydantic schemas for Agent Client Protocol (ACP) and Model Context Protocol (MCP). As both protocols rapidly mature across the AI industry—particularly with the MCP 2026-07-28 release featuring stateless requests, header-based routing, and Tier-1 SDKs in Python, Go, TypeScript, and C#—maintaining proprietary protocol implementations introduces severe maintenance burden and risk of wire incompatibility.

## Decision
1. Stop implementing custom protocol dialects in S-Class.
2. Directly adopt the official ACP v1 protocol specifications, schemas, and lifecycle methods.
3. Directly adopt the official MCP 2026-07-28 specifications and SDK patterns.
4. Establish thin adapter layers (`sclass.integrations.acp` and `sclass.integrations.mcp`) whose sole responsibility is mapping external protocol messages into universal S-Class `ActionRequest` and `Session` structures.
5. S-Class retains 100% authority over identity, permissions, policy enforcement, execution observation, and state persistence.

## Consequences
- **Positive**: Full wire compatibility with the broader ecosystem (Claude Code, Cursor, Codex, OpenCode, and community MCP tool servers). Zero protocol drift.
- **Negative**: Must track official protocol releases and schema deprecation cycles.
- **Invariants Upheld**: Invariant I9 (Protocol adapters cannot directly certify execution).
