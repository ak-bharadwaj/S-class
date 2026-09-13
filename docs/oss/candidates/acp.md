# OSS Candidate Evaluation: Agent Client Protocol (ACP)

## 1. Candidate Overview
- **Project**: Agent Client Protocol (`agentprotocol/acp` / official schema & SDK specifications)
- **Purpose**: Open standard protocol for communication between AI coding agents and client applications (IDEs, CLI tools, execution platforms). Covers session negotiation, prompt lifecycle, tool calls, streaming updates, permission requests, cancellations, and workspace gateways.
- **License**: Apache License 2.0 / MIT.
- **Primary Language / Ecosystem**: Language-agnostic JSON-RPC 2.0 protocol with official TypeScript and Python SDKs.

## 2. Maturity & Governance
- **Maturity**: Protocol v1 is stable. Wire compatibility is explicitly negotiated separately from schema artifact revisions. Backed by multi-vendor industry working groups.
- **Maintainer Health**: Active multi-organizational maintenance and governance.
- **Release Cadence**: Regular versioning with explicit protocol negotiation during handshake (`initialize`).

## 3. Engineering Rigor & Trustworthiness
- **Security**: Structured capability negotiation, explicit permission requests for filesystem and terminal operations, sandboxed execution boundaries.
- **Testing**: Protocol conformance test suites, schema validation harnesses, client/server mock fixtures.
- **Production Evidence**: Implemented across emerging agent harnesses, IDE extensions, and automated coding runners.
- **Platform Coverage**: Cross-platform (JSON-RPC over stdio, HTTP/SSE, WebSockets).
- **Protocol Compliance**: Strict JSON-RPC 2.0 compliance, formal JSON Schema definitions.
- **Performance**: Lightweight message serialization with streaming chunk support.

## 4. Architectural Fit & S-Class Boundaries
- **Integration Cost**: Low. S-Class consumes official schemas and protocol transports, adapting them directly to internal `ActionRequest` and `Session` structures.
- **Failure Modes**: Malformed protocol payloads, transport disconnection, unhandled notification methods. Handled fail-closed with JSON-RPC error responses.
- **What We Adopt**: Official wire format, schema definitions, session lifecycle (`initialize`, `session/new`, `prompt`, `session/update`, `session/cancel`), terminal and filesystem gateway interfaces.
- **What We DON'T Adopt**: ACP protocol does not own execution authorization, process observation, evidence generation, or project truth. S-Class enforces policies, observes execution via OS primitives, and anchors truth.
- **S-Class Wrapper**: `sclass.integrations.acp` containing `ACPAdapter`, `ACPTransport`, `ACPSessionManager`, `ACPPermissionsBridge`, `ACPCapabilityMap`, `ACPFsGateway`, and `ACPTerminalGateway`.
- **Escape Plan**: Protocol adapter abstraction (`AgentProtocolAdapter`). The internal S-Class control plane operates entirely on normalized `ActionRequest` models; swapping ACP for any alternative protocol requires zero changes to the trust kernel.

## 5. Architectural Decision
- **Decision**: `ADOPT`
- **Architectural Tier**: Tier 1 (Foundational Agent Protocol)
- **Rationale Summary**: Re-implementing a proprietary or synthetic dialect of ACP causes protocol drift. Consuming the official ACP protocol/schema guarantees standard compliance while keeping the S-Class adapter thin and focused solely on trust boundary enforcement.
