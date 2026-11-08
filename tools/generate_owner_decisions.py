#!/usr/bin/env python3
"""Generate OWNER-DECISIONS-DRAFT.md verbatim from Round 10 Addendum (Owner Task T3)."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

OUT_FILES = [
    REPO_ROOT / "OWNER-DECISIONS-DRAFT.md",
    REPO_ROOT / "delivery-global" / "OWNER-DECISIONS-DRAFT.md",
]

CONTENT = """# OWNER DECISIONS (DRAFT)
Reference: Round 10 Addendum (2026-11-08 21:50 IST)
Status: DRAFT FOR AK SIGNATURE
Instruction: Ak signs by committing this file as OWNER-DECISIONS.txt (AG does NOT commit the signed version).

## D1 FROZEN SEMANTICS FILE
CL decides to ACCEPT the repo version (sha ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922) as the hardened baseline IF AND ONLY IF the generated diff between the package-original (sha 66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76) and the repo version shows only additions/tightenings. Task T1 produces that diff classified per hunk (ADDED_CONSTRAINT / EXPLANATORY / CHANGED_VALUE / REMOVED). Any CHANGED_VALUE or REMOVED hunk = STOP, report hunk, do not decide. Both hashes stay recorded; the guard keeps pinning ed2faf.

## D2 MASTER IN REPO
The master v6.0.2 is committed under docs/design/ (T2) with sha check 340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff (699,827 bytes). Never edited afterwards (a guard test pins the hash).

## D3 BRANCH PROTECTION
integration-r30-b1 gets: require pull request, no force push, no deletion. Required status checks are NOT enabled until CI is green on integration (otherwise nothing can merge). Try via gh api (T4); if permission denied, output the exact click-path for Ak.

## D4 PR #3
Close with a comment "superseded by PR #13/#14; no code lost" (T5), only after confirming refs/pull/3/head (e60a089d) is ancestor of integration or listing what is not.

## D5 TAGS
None now. Criteria for tag v6.0.2-impl-rc1 (Ak creates it): integration CI green on all 8 jobs, Round 10 close-out merged, CL static LPC kit passes.

## D6 MAIN
Do NOT merge into main now. main (ecc28aec) and integration have diverged. T6 produces a generated report of the 74 commits that are on main but not on integration (grouped by path; flag any file on main that integration changed differently). CL decides after reading it; Ak owns the final move on main.

## D7 BRANCH CLEANUP
No deletions. Before any later cleanup, every lane tip is archived as a tag archive/<branch> by Ak.

## D8 CAP WAIVER
CAP WAIVER W-B2-1 stays Block 2 only.

## D9 GPT
Stays optional. CL performs the LPC L1-L10 review using AG's generated kit (S1-S8) and the P1 packet; GPT is used later only as an independent second opinion.

---

## SIGNATURE BLOCK

I, Ak Bharadwaj, as Owner and Principal Authority of the S-Class repository, hereby ratify and sign the decisions D1 through D9 as drafted above:

Signature: _____________________________________________
Ak Bharadwaj (Repository Owner)

Date: 2026-11-08
Commit Hash: _________________________________________
"""

def main():
    for f in OUT_FILES:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(CONTENT, encoding="utf-8")
        print(f"Generated {f}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
