# ADR-029: CLI Terminal UI Live Monitoring

## Status
Accepted

## Context
Developers need real-time visual feedback on agent actions without parsing raw JSON logs.

## Decision
`sclass watch` provides a curses/rich terminal UI showing active symbol leases, task graphs, and verifier verdicts.
