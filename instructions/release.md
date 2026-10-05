# Phase: RELEASE

Objectives:
- Compile the Output Evidence Pack containing signed test receipts and verification proofs.
- Verify tamper-evident SHA-256 state hashes against the evidence log.
- Ensure the working tree is clean with all changes committed following conventional commit rules.
- Close active leases and advance to completion via `dispatch_event("release_approved")` or `dispatch_event("deployed")`.
