# ACP (Agent Communication Protocol) Adapter

## Overview
The S-Class ACP Adapter (`src/sclass/integrations/acp/adapter.py`) interfaces with systems communicating via the Agent Communication Protocol.

## Protocol Invariant (Invariant 5)
An adapter must only normalize agent events into `ActionRequest` instances or submit claims for evaluation. It must never directly issue an `EvidenceReceipt` or certify its own actions.

## Event Normalization
- Converts raw ACP JSON events into structured `AgentEvent` objects.
- Translates tool requests into `ActionRequest`.
- Passes requests to S-Class `PolicyEngine` for authorization before any execution occurs.
