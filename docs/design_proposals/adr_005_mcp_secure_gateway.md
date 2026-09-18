# ADR-005: Model Context Protocol (MCP) Secure Gateway

## Status
Accepted

## Context
MCP tool servers allow LLMs to invoke local and network tools. Direct unrestricted tool exposure allows prompt injection attacks.

## Decision
S-Class wraps MCP tool registrations with policy evaluation gates. All input parameters must conform to registered JSON schemas.
High-entropy credentials in parameters are blocked before dispatch.
