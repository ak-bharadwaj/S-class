# Layer A — Universal Interface & Primitives

Normalizes disparate coding agent platform events into standard typed primitives:
- `ActionRequest`: Target command, arguments, requested capabilities, and intent declaration.
- `Capability`: Declared resource access boundaries (`fs:read`, `fs:write`, `net:http`).
- `AgentSession`: Lifecycle container tracking agent credentials, active leases, and tasks.
