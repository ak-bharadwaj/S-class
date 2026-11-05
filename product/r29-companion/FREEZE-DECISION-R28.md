# S-Class v6.0.2 — FREEZE DECISION (qualified baseline)

Decision: R28 is frozen as an explicitly QUALIFIED BASELINE. It is not a verified release.
Decided by: Ak (owner), 2026-10-20. Recorded by Claude (architect). Owner signature line below is for Ak to complete.

## Bound artefacts (sha256)
- FREEZE-CANDIDATE-v6.0.2-R28.zip: 15fb91437221cbc0a012e0d6c39973ab350fdb9e3bd63a4a215ef7bf28462c54
- Master S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md: 508fc017924736ad6d1739fcca81b0a9923dcdf2061b3f81e46448bfb02a8c98
- MANIFEST.sha256: 86218d5222ef248ceee7d6d6b3d77fa6da66d54ca855863d42c8d1023d082256
- gates/REVIEWER-GATES-RAW.txt (not covered by the manifest): ea2c848a02f3ab5b68959f113f0ef33c55ab959ccc929dd38d95beb464a3e903
- RERUN.sh exit code in the author's clean-room run: 0 (ALL GATES PASSED, 61 s)

## Conditions
1. Change control: no edit to this baseline. Any change is a new revision with a new candidate id, diff and rerun.
2. Section status: the 54 DRAFT sections are NOT flipped to ACCEPTED by this decision. The ledger is unchanged.
3. Known limitation: a kernel state named only by a bare ordinary word, with no declaration phrase and no inline code, can evade the concept gate. Authoritative enforcement is the kernel enum and its tests (OI-034), which have not yet run.
4. Verification status: the complete RERUN.sh was reproduced only by the author, not independently. External reviewers' full reruns timed out in their environments.
5. Sign-off incomplete and recorded as such: review/INDEPENDENT-REVIEW.txt absent (the 189 variant dispositions are a self-review); OWNER-DECISIONS.txt unsigned (distinctness choices, external inputs, OSS addendum, item F length ceilings, item G reviewer independence, digest bindings). gates/chk_release_ready.py exits 1 with 7 findings and must stay that way until these are done.
6. Open, not closed by freezing: OI-003 and OI-034 (fixtures never executed against a real kernel), OI-031 (11 artifact types shape-only), OI-036 (five external documents), OI-015 (OSS addendum choice).

## Owner signature
Name: Ak     Date: ______     Signature/ack: ______
