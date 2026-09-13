# OSS Candidate Evaluation: Model Context Protocol (MCP)

## 1. Candidate Overview
- **Project**: Model Context Protocol (`modelcontextprotocol/specification` / SDKs) — https://github.com/modelcontextprotocol
- **Purpose**: Open standard protocol that enables AI applications to securely interact with external tools, data sources, and services.
- **License**: MIT License (SPDX: `MIT`).
- **Primary Language / Ecosystem**: Official Tier-1 SDKs in Python (`mcp`), TypeScript (`@modelcontextprotocol/sdk`), C#, and Go. Protocol transports include stdio and Streamable HTTP (SSE).

## 2. Maturity & Governance
- **Maturity**: Created by Anthropic in 2024 and broadly adopted across the AI industry (Claude Desktop, Cursor, Zed, Sourcegraph Cody). Major spec evolution on 2026-07-28 introduced stateless core, self-describing requests, header-based routing, cacheable list results, MRTR (Multiplexed Request-Trace Routing), and formal extensions.
- **Maintainer Health**: Exceptionally active, supported by Anthropic, broad open-source developer consortium, and thousands of community tool servers.
- **Release Cadence**: Regular SDK releases; stable schema evolution with strict version headers (`MCP-Protocol-Version`).

## 3. Engineering Rigor & Trustworthiness
- **Security**: Strict client-controlled capability negotiation, isolated tool endpoints, formal authorization flow, explicit resource URI boundaries.
- **Testing**: End-to-end integration tests across Tier-1 SDKs, automated schema validation fixtures, protocol compliance fuzzing.
- **Production Evidence**: Deployed across hundreds of thousands of production developer machines and enterprise AI workflows.
- **Platform Coverage**: Cross-platform (POSIX and Windows).
- **Protocol Compliance**: JSON-RPC 2.0 based, JSON Schema v7 validation for tool inputs and outputs.
- **Performance**: High-throughput multiplexed message handling with streaming response capability.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Low. Official SDK is easily integrated or wrapped behind standard transport layers.
- **Failure Modes**: Tool server crash, unhandled RPC errors, schema mismatch, malicious tool poisoning or impersonation.
- **What We Adopt**: Official protocol wire semantics, MCP 2026-07-28 stateless self-describing requests, header-based policy checking (`MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`), tool schemas, resource schemas, and long-running task operations.
- **What We DON'T Adopt**: MCP tools are NOT granted direct unmonitored host execution. Tool calls must converge onto S-Class `ActionRequest` objects, subjected to policy authorization and execution observation.
- **S-Class Wrapper**: `sclass.integrations.mcp` containing `MCPAdapter`, `MCPGateway`, `MCPProtocolTransport`, `MCPHeaderPolicy`, and tool execution bridge.
- **Escape Plan**: Abstract `CapabilityProvider` interface. S-Class views MCP servers as one of many capability sources (alongside CLI, local plugins, and OS commands).

## 5. Architectural Decision
- **Decision**: `ADOPT`
- **Architectural Tier**: Tier 1 (Foundational Tool Protocol)
- **Rationale Summary**: MCP is the universal standard for AI tool integrations. Using the official MCP SDK and 2026-07-28 specifications ensures full ecosystem compatibility while channeling all tool executions through S-Class trust invariants.
