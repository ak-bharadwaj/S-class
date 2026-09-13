# Protected Resources & Boundary Defense

## Protected Paths
S-Class enforces strict immutability on core trust assets:
- `.sclass/ledger.jsonl`
- `.sclass/sclass.db`
- `.sclass/trust_anchors.json`
- `.sclass/checkpoints/`
- `sclass.config.json`
- `policies.json`

## Defense Layers
1. **Pre-Execution Action Gating**:
   `check_protected_resource_targeting(target_path)` checks normalized absolute path against protected patterns before any action or tool executes.
2. **Process Runner Policy Enforcement**:
   Commands containing file operations directed at `.sclass/` are blocked when executed in `HOST_ARGV` or `HOST_SHELL` modes.
3. **MCP Tool Parameter Inspection**:
   MCP tools targeting file paths undergo argument scanning before passing to tools.
