# ADR 0009: Step-Code Harness Absorption & Assurance-Plane Consolidation

## Status
Accepted

## Context
Step-Code provides a mature runtime execution substrate for terminal coding agents, including durable operation lifecycles, tool execution engines, session trees, worker lanes, and command permission analysis.

S-Class requires a mature, production-grade execution harness while maintaining its position as the independent epistemic authority for technical obligations, evidence verification, regression frontiers, bounded recovery, and completion adjudication.

Directly coupling execution and assurance within a single loop creates a conflict of interest where an execution runtime could declare its own work "complete" without independent validation. Furthermore, duplicating general LLM agent loops within S-Class would blur architectural responsibilities.

## Decision
1. **Explicit Separation of Planes**:
   Step-Code provides the execution substrate (LLM conversation loop, tool execution, session trees, worker lanes, permissions, retries). S-Class provides the independent assurance substrate (authorization, independent observation, evidence verification, canonical truth, mutation invalidation, regression frontiers, bounded recovery, completion adjudication).
2. **External RPC Subprocess Architecture**:
   Step-Code runs as a separate process or daemon communicating with S-Class (`StepCodeRpcHarness`) over stdio using strict single-byte LF (`0x0A`, `\n`) delimited JSONL. Unicode line terminators (`\u2028`, `\u2029`) are preserved without corrupting the protocol.
3. **Strict Epistemic Isolation**:
   Runtime `SUCCESS`, `SETTLED`, or `goal_complete` signals can **never** establish S-Class project truth. All tool returns and execution candidate outputs carry `untrusted_candidate = True`.
4. **Dual-Layer Authorization**:
   Every action request must pass both S-Class cryptographic authorization (Layer 1) and Step-Code runtime command permission analysis (Layer 2) before execution. Action parameter tampering aborts execution immediately.
5. **Two-Ledger Architecture**:
   - `ExecutionLedger` (`cross_runtime_operations.jsonl` + SQLite `cross_runtime_operations` via Migration 006): tracks operational execution truth.
   - `AssuranceLedger` (`assurance_ledger.jsonl`): tracks canonical project truth.
6. **Fail-Closed Crash Semantics**:
   If the Step-Code runtime terminates unexpectedly, `StepCodeRpcHarness` fails closed, transitions active operations to `FAILED`, and rejects further unverified actions until cleanly restarted.
7. **Six-Tier Benchmark SLA**:
   Performance across all 6 tiers (baseline, +auth, +event bridge, +observation, +verification, +full assurance) is continuously tracked to ensure assurance overhead remains tightly bounded.

## Consequences
- S-Class does not duplicate general LLM provider loops, conversation trees, or tool runners.
- Any execution harness (Step-Code, Claude Code, Codex, Custom) can operate the project without altering S-Class assurance semantics.
- Runtime claims or goal complete signals can never directly establish verified project truth.
- Independent observers and typed verifiers remain the sole path to canonical project state promotion.

## Attribution
Portions of the durable operation lifecycle, session tree concepts, and command permission analysis patterns are derived from **Step-Code** under the MIT License.
