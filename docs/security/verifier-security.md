# Verifier Security & Invariant Enforcement

## Invariant 3: Caller-Supplied Verifiers Cannot Upgrade Status

A fundamental attack vector against verification engines is an agent running an arbitrary command (such as `echo "all tests passed"`) and declaring `verifier="pytest"`.

In S-Class:
1. The verifier detector (`StandardVerifierDetector`) independently identifies the test runner by analyzing:
   - The resolved executable name and binary hash.
   - The exact argv arguments.
   - Whether python was invoked with `-c` or a script file.
2. If an agent claims `verifier="pytest"`, but the detector identified the command as `generic_command`, S-Class rejects or marks the claim as inconclusive (`CONTRADICTED` or `UNKNOWN`).
3. Verification results (passed, failed, skipped) are parsed strictly from raw stdout/stderr using deterministic result parsers (`PytestResultParser`, `UnittestResultParser`, etc.), completely ignoring any self-reported counts.
