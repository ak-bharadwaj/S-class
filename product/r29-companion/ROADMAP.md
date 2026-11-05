# S-Class implementation roadmap (R28 baseline, H0-H7 spine, v1 = 4 hosts x 4 languages)
Legend: AG builds, CL verifies/accepts, AK decides. A step opens only after its predecessor is ACCEPTED. "Exit evidence" = raw logs reviewed by CL.

## Stage 0 — Baseline truth (no new features)
| Step | Who | Deliverable | Exit evidence |
|---|---|---|---|
| B00/B00b | AG -> CL | Correct repo scan (real citations, real state machines, real counts) | REVIEW-00 ACCEPT |
| B01 | AG -> CL | Baseline lock: sha256 of 00-SPEC/* and 10-CONFORMANCE/* on main, h0, h1a, h1b; written to governance/BASELINE-HASHES.txt; plus clean-install run (`pip install -e .`, fresh venv) of the FULL test suite (incl. tests/) on main and each branch, on Linux (WSL or CI), with env-vs-code classification of every failure | hashes equal across branches; failures classified |
| B02 | CL (AK decides) | Review of the 16 declared runtime hunks in docs/KERNEL-CHANGES.md as errata-style changes: accept / revise / reject each; decide whether 20-RUNTIME is inside the frozen boundary | DECISIONS.md entry; REVIEW-02 |
| B03 | AG -> CL | Branch plan execution (only after B02 and AK's word): reconcile h0 -> h1a -> h1b into one line, no merge to main yet; CI green on Linux | CI log, branch diff vs B02 decisions |
| T0 | CL | MUST-TRACKER.tsv (195 MUSTs -> H phase, owner, dependency, fixture ids, status), MATRIX.tsv (16 cells UNSUPPORTED), STATUS.md | AK reads and corrects |

## Stage H0 — canonical foundation (mostly present on main; prove it)
B04: run conformance/property/replay/crash-recovery suites from a clean install; produce replay-from-genesis digest equality evidence; add the kernel-enum guard test (fails if any EventType/state/machine differs from state-machines.v6.0.1.json — this is the real "no new kernel state" enforcement). Exit: conformance+replay+guard green on Linux CI, hashes unchanged. Closes OI-005 for the kernel surface.

## Stage H1-H3 — boundary, durability, evidence
- B05 (H1): qualify ExecutionGate on real Linux (bubblewrap/cgroup v2), run launch/write-boundary adversarial suite; Windows/mac stay fail-closed with explicit skip reasons; OS scope recorded. Exit: adversarial suite log on Linux; unavailable platforms documented, never "passed".
- B06 (H2): crash/replay consistency under the K-stage kill matrix; canonical-authority tests. Exit: matrix log.
- B07 (H3): evidence integrity: receipt identity, freshness, independence, TestInputSet binding; fixture runner that executes master fixtures (the 66 gaming/happy pairs) against the real gate: this is OI-003/OI-034 closing. Exit: per-fixture result table (SATISFIED/MISSING/BLOCKED_ON_HUMAN as expected), each MUST -> FIXTURE RAN.
First vertical slice acceptance (end of B07): one task from intake -> requirement -> authorized change -> real verification -> gate decision -> audit export -> replay, in Python, via MCP, in VS Code reference host. A model-only demo is not a slice.

## Stage H4 — workers, workspace, recovery (Chapter 8)
B08 bounded worker lifecycle, retry/cancel/recover; B09 out-of-band edit detection, re-snapshot, overlapping-write serialisation, workspace promotion with rollback evidence, index completeness. Exit: scenario logs per MUST group CH8.

## Stage H5 — product surface (Chapters 6 and 7) and the v1 matrix
- B10 MCP protocol hardening: replace hand-rolled stdio server with a qualified implementation (or qualify the existing one), versioned requests/responses, structured errors, session identity. Exit: protocol conformance log.
- B11 host adapters: VS Code (reference), then Cursor, Antigravity, Codex (Codex has no adapter today: new). Per host: install, session, next-action, status, block display, resume; capability level E0/E1/E2 recorded per version/OS. Exit: per host a MATRIX row with raw run logs.
- B12 knowledge plane: pack manifest, resolution, signature/licence/provenance checks, revocation, pinning. One reference pack (Python) end to end.
- B13/B14/B15 language packs and adapters in order TypeScript/JavaScript, Java, then frameworks (pytest/Django/FastAPI; Jest/Vitest/Node/React; JUnit/Maven/Gradle/Spring). Each pack = qualification record; cells promoted by CL on evidence.
Exit H5: v1 matrix table with real levels; every host QUALIFIED for >=1 language and every language QUALIFIED on >=1 host (AK may change this bar).

## Stage H6 — production engineering and evaluation (Chapter 9)
B16 performance baselines on Linux CI hardware (the Windows perf-contract failures are not evidence either way); B17 adversarial/threat-map coverage (every listed threat has attack, boundary, fixture); B18 evaluation harness: benchmark set, denominators, confidence intervals, false-completion and false-block rates, independent audit labels; B19 telemetry/retention/data access; B20 OSS qualification records (16 fields) for each dependency actually used.

## Stage H7 — release evidence
B21 versioning/compatibility matrix and install/upgrade/rollback path; B22 audit export and replay bundle; B23 release evaluation and traceability bundle (all MUSTs with evidence), independent review of the 189 variant dispositions, AK signs OWNER-DECISIONS, status flips by evidence, tags.

## Who decides what (AK only)
Merging/tagging; accepting changes to 20-RUNTIME (B02); which cells must be QUALIFIED vs DETECT-ONLY at launch; framework defaults; ratifying QUALIFIED; signing OWNER-DECISIONS (items F, G) and the five external docs; OSS addendum choice.

## Order of work from today
1. AK pastes BRIEF-00b into AG -> AG returns scan v2 -> CL REVIEW-00.
2. CL issues BRIEF-01 (baseline lock + clean-install full suite on Linux).
3. CL reviews hunks (B02) while AG runs B01; AK decides.
4. T0 tracker written by CL after B01.
5. Then B03 onward strictly in order.
