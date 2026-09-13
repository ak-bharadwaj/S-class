# S-Class End-to-End Demo Walkthrough

## Scenario: Securing Autonomous Task Execution

This walkthrough demonstrates how S-Class prevents common failure and spoofing modes during autonomous development.

### Step 1: Initialize S-Class in Workspace
```bash
sclass init
sclass doctor
```
Generates the cryptographically anchored `.sclass/` ledger and state database.

### Step 2: Agent Requests File Edit
Agent creates a feature implementation in `src/service.py`. S-Class policy engine checks boundaries and authorizes the change.

### Step 3: Attack Scenario — Agent Claims Tests Pass Without Running Valid Tests
Agent executes:
```bash
echo "All 50 tests passed successfully"
```
And submits claim:
`"Authentication service passes all unit tests"`

**S-Class Result**:
- Detects command as `generic_command`.
- Evaluates against `ClaimAcceptanceMatrix`.
- Verdict: **INCONCLUSIVE / REJECT** (`EXECUTION_VERIFIED != CLAIM_VERIFIED`).

### Step 4: Legitimate Test Run With Failing Tests
Agent runs pytest: 48 pass, 2 fail.
Agent claims: `"All tests pass"`.

**S-Class Result**:
- Independently parses exit code 1 and 2 test failures.
- Verdict: **REJECT** (`Independent test runner observed 2 test failure(s)`).

### Step 5: Successful Verification & Checkpoint
Agent fixes bugs, re-runs tests (50 pass, 0 fail).
**S-Class Result**:
- Verdict: **ACCEPT**.
- Creates immutable checkpoint with workspace fingerprint and ledger head hash.
- Generates handoff package for successor agent.
