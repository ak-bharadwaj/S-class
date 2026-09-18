# ADR-006: Agent Client Protocol (ACP) Multi-Agent Multiplexer

## Status
Accepted

## Context
Editors communicate with coding agents using JSON-RPC standard ACP. S-Class must sit transparently between them.

## Decision
S-Class proxies ACP connections, recording all tool dispatches, file edits, and terminal executions into the authority plane.
