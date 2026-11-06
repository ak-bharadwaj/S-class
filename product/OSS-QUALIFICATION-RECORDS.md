# OSS Qualification Records — R9

**Qualification status: BLOCKED.** The designated file `oss_facts_pypi.jsonl` is absent from the mounted workspace. Therefore no JSONL facts could populate version/tag, license expression, SHA-256/install digest, advisory, release or numeric maturity fields. Every mandatory record field remains exactly `UNVERIFIED`; this is not a claim that a candidate is qualified. The requested input-provided license/staleness flags are repeated as review tasks outside the record fields, not as verified source facts.

## Hash-pinned install controls (templates only; not executed)

- PyPI package pattern: `python -m pip install --require-hashes -r locks/<tool-id>.requirements.txt`. Each lock must contain exact direct and transitive versions plus hashes, and the install transcript must be retained. No lock/hash is present in this run; therefore do not execute the command.
- Binary/native pattern: `sha256sum --check locks/<tool-id>.sha256` followed by a separately verified provenance/signature trust check. No manifest or binary hash is available; mismatch/missing hash => BLOCKED and no execution.
- The `install_procedure_digest` mandatory field remains `UNVERIFIED` until the exact command, reviewed lock/manifest, tool identity, environment, and output transcript are hashed and recorded.

## Chosen-tool records (one per proposed tool or control; no qualification implied)

### R9-01 — GitHub Spec Kit

**Plan role / level:** P0/P4 process-source, L1. **F10 category:** process-source. **Consumed surface (proposal only):** content source only; do not execute imported process state.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/github/spec-kit (verified via gh_repo__spec-kit.json)
| `version_tag_or_commit` | GitHub release v1.3.0 (verified via gh_release_latest__spec-kit.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__spec-kit.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__spec-kit.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `Do not install or execute source templates; if a CLI is later approved, verify immutable artifact SHA-256 and provenance first.`

**Fallback (proposal only):** OpenSpec content, then S-Class-owned templates

**Known failure / fail-closed route (proposal only):** Imported instructions remain claims; bind source digest/normalization; never state or approval authority.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-02 — Fission-AI OpenSpec

**Plan role / level:** P2 process-source, L1. **F10 category:** process-source. **Consumed surface (proposal only):** proposal/spec/design/task content only.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/Fission-AI/OpenSpec (verified via gh_repo__openspec.json)
| `version_tag_or_commit` | GitHub release v1.16.0 (verified via gh_release_latest__openspec.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__openspec.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__openspec.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `Do not execute sourced content; if CLI use is approved, verify source/artifact hash manifest first.`

**Fallback (proposal only):** Spec Kit or S-Class-owned requirements templates

**Known failure / fail-closed route (proposal only):** Imported specs are claims until validated and authorized; no process/state engine authority.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-03 — python-jsonschema

**Plan role / level:** P0/P2/P3/P7 schema validator, L1 (conditional L2). **F10 category:** schema validator. **Consumed surface (proposal only):** validate frozen schema/envelope only.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/python-jsonschema/jsonschema (verified via gh_repo__jsonschema.json)
| `version_tag_or_commit` | PyPI release 4.26.0 (verified via pypi__jsonschema.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__jsonschema.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__jsonschema.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact jsonschema-4.26.0-py3-none-any.whl sha256 d489f15263b8d200f8387e64b4c3a75f06629559fb73deb8fdfb525f2dab50ce is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/python-jsonschema.requirements.txt`

**Fallback (proposal only):** independent frozen-schema validator, otherwise BLOCKED

**Known failure / fail-closed route (proposal only):** Result is evidence of schema conformance only; not semantic correctness or intent authority.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `jsonschema` 4.26.0; license MIT; first upload 2012-01-02; latest upload 2026-01-07; age 14.8y; source https://pypi.org/pypi/jsonschema/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification); flags: latest upload 279 days ago (>6mo)

### R9-04 — Tree-sitter core

**Plan role / level:** P1/P3/P6/P7 repo-intelligence, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** syntax tree only; grammar and core are separately pinned.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/tree-sitter/tree-sitter (verified via gh_repo__tree-sitter.json)
| `version_tag_or_commit` | GitHub release v0.27.1 (verified via gh_release_latest__tree-sitter.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__tree-sitter.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__tree-sitter.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact tree_sitter-0.26.0-cp310-cp310-macosx_10_9_x86_64.whl sha256 ff527388df14cb5009f9274faf78cc69a7393ae6acf3b04784b8acca249519c5 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/tree-sitter-core.sha256 && verify provenance before use; grammars need their own lock/digest.`

**Fallback (proposal only):** bounded lexical scan with explicit coverage gaps / MISSING

**Known failure / fail-closed route (proposal only):** Parser output is structural observation; language/grammar gaps mean unknown coverage. SPDX/license remains UNVERIFIED.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `tree-sitter` 0.26.0; license classifier-only: MIT License; first upload 2019-03-21; latest upload 2026-06-30; age 7.6y; source https://pypi.org/pypi/tree-sitter/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification); flags: 0.x version; SPDX unverified (classifier only)

### R9-05 — SCIP

**Plan role / level:** P1/P3/P7 repo-intelligence, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** symbol/reference index interchange.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/sourcegraph/scip (verified via gh_repo__scip.json)
| `version_tag_or_commit` | GitHub release v0.10.0 (verified via gh_release_latest__scip.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__scip.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__scip.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/scip.sha256 && verify provenance before use.`

**Fallback (proposal only):** bounded filesystem/Git inventory and cross-check

**Known failure / fail-closed route (proposal only):** Index omissions/stale index are MISSING, never proof of absence.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-06 — ast-grep

**Plan role / level:** P1/P3/P6/P8 repo-intelligence, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** structural query findings and proposed rewrites.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/ast-grep/ast-grep (verified via gh_repo__ast-grep.json)
| `version_tag_or_commit` | PyPI release 0.51.1 (verified via pypi__ast-grep-cli.json)
| `license_expression_and_obligations` | MIT License (verified via gh_license__ast-grep.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 2 security advisories in GitHub Security Advisories; ref gh_advisories__ast-grep.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact ast_grep_cli-0.50.0-py3-none-macosx_10_12_x86_64.macosx_11_0_arm64.macosx_10_12_universal2.whl sha256 cb135961f377d8e7a892e51a51cf5754ef4e09f93e0975b17cfdcf4343155451 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/ast-grep.requirements.txt only if exact PyPI distribution is verified; otherwise hash-check native artifact.`

**Fallback (proposal only):** Tree-sitter/reference scan with explicit language coverage

**Known failure / fail-closed route (proposal only):** Matches are observations; rewrite output is a proposed diff; license classifier alone is not SPDX proof.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `ast-grep-cli` 0.50.0; license classifier-only: MIT License; first upload 2023-12-01; latest upload 2026-10-09; age 2.9y; source https://pypi.org/pypi/ast-grep-cli/json; retrieved 2026-10-12

**Maturity rule result:** OPTIONAL (L1; L2 conditional); flags: young or 0.x; 0.x version; SPDX unverified (classifier only)

### R9-07 — SQLGlot

**Plan role / level:** P3 schema/SQL AST, L1 (conditional L2). **F10 category:** schema validator. **Consumed surface (proposal only):** parse/dialect output schema and normalized SQL AST.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/tobymao/sqlglot (verified via gh_repo__sqlglot.json)
| `version_tag_or_commit` | PyPI release 30.29.0 (verified via pypi__sqlglot.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__sqlglot.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__sqlglot.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact sqlglot-30.22.0-py3-none-any.whl sha256 90aa461490fcd95d14ec3842a97506ae20f6d3e9313307ad31be793d479cca65 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/sqlglot.requirements.txt`

**Fallback (proposal only):** database-native schema inspection plus integration test, otherwise BLOCKED

**Known failure / fail-closed route (proposal only):** Parse success does not prove runtime database behavior or domain invariants.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `sqlglot` 30.22.0; license MIT; first upload 2021-03-18; latest upload 2026-10-09; age 5.6y; source https://pypi.org/pypi/sqlglot/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-08 — Semgrep engine

**Plan role / level:** P3/P6/P7/P9 repo-intelligence, L1. **F10 category:** repo-intelligence. **Consumed surface (proposal only):** static-security findings; engine, rules and rule configuration bound separately.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/semgrep/semgrep (verified via gh_repo__semgrep.json)
| `version_tag_or_commit` | PyPI release 1.183.0 (verified via pypi__semgrep.json)
| `license_expression_and_obligations` | LGPL-2.1-or-later (verified via gh_license__semgrep.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__semgrep.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact semgrep-1.180.0-cp310.cp311.cp312.cp313.cp314.py310.py311.py312.py313.py314-none-macosx_10_14_x86_64.whl sha256 f074dcfd6a56095fde32c354af27ef0cce6d15607bef42fa50964dd7042b667d is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/semgrep-engine.requirements.txt; independently sha256-check the pinned rule bundle before use.`

**Fallback (proposal only):** Bandit for Python-only cases plus manual hold; unsupported languages BLOCKED

**Known failure / fail-closed route (proposal only):** R9 risk flag says engine LGPL-2.1-or-later; license fact remains UNVERIFIED without JSONL. Rules license is separate and UNVERIFIED. Findings cannot waive review.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `semgrep` 1.180.0; license LGPL-2.1-or-later; first upload 2020-05-06; latest upload 2026-10-07; age 6.4y; source https://pypi.org/pypi/semgrep/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification); flags: LGPL engine; rules license UNVERIFIED

### R9-09 — Semgrep rules bundle

**Plan role / level:** P3/P6/P7/P9 repo-intelligence, L1. **F10 category:** repo-intelligence. **Consumed surface (proposal only):** static-security findings; engine, rules and rule configuration bound separately.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/semgrep/semgrep-rules (verified via gh_repo__semgrep-rules.json)
| `version_tag_or_commit` | Default branch develop @ pushed 2026-10-27
| `license_expression_and_obligations` | Semgrep Rules License v1.0 (verified via gh_license__semgrep-rules.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__semgrep-rules.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/semgrep-rules.sha256 && verify pinned rule-source provenance; do not fetch or enable a rule pack if its source URL, license and digest are absent.`

**Fallback (proposal only):** omit this bundle; use only a separately qualified existing scanner/ruleset, otherwise required review is BLOCKED.

**Known failure / fail-closed route (proposal only):** missing rule source, license, scope, digest or freshness baseline => BLOCKED; the engine license never implies a rule-bundle license.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-10 — Bandit

**Plan role / level:** P3/P5/P7/P9 repo-intelligence, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** Python static security findings only.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/PyCQA/bandit (verified via gh_repo__bandit.json)
| `version_tag_or_commit` | PyPI release 1.9.4 (verified via pypi__bandit.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__bandit.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__bandit.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact bandit-1.9.4-py3-none-any.whl sha256 f89ffa663767f5a0585ea075f01020207e966a9c0f2b9ef56a57c7963a3f6f8e is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/bandit.requirements.txt`

**Fallback (proposal only):** Semgrep adapter if independently qualified; otherwise Python security review remains BLOCKED

**Known failure / fail-closed route (proposal only):** Python scope only; missing plugins/config/exclusions must remain explicit.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `bandit` 1.9.4; license Apache-2.0; first upload 2015-03-23; latest upload 2026-02-25; age 11.6y; source https://pypi.org/pypi/bandit/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification); flags: latest upload 230 days ago (>6mo)

### R9-11 — Open Policy Agent (OPA)

**Plan role / level:** P3/P4/P9 policy fixture only, L1. **F10 category:** schema validator (envelope only; no direct policy authority). **Consumed surface (proposal only):** fixed input/output fixtures; policy decisions are claims.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/open-policy-agent/opa (verified via gh_repo__opa.json)
| `version_tag_or_commit` | GitHub release v1.22.1 (verified via gh_release_latest__opa.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__opa.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 4 security advisories in GitHub Security Advisories; ref gh_advisories__opa.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/opa.sha256 && verify provenance; input policy bundle digest must be separately pinned.`

**Fallback (proposal only):** S-Class-owned mechanical checks and authorized review; no policy result implies PASS

**Known failure / fail-closed route (proposal only):** OPA cannot own policy, approval, canonical state, gates or release; no new F10 category/state machine.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-12 — pytest

**Plan role / level:** P5/P7/P8/P9 contract tester, L1 (conditional L2). **F10 category:** contract tester. **Consumed surface (proposal only):** declared test collection and raw result schema.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/pytest-dev/pytest (verified via gh_repo__pytest.json)
| `version_tag_or_commit` | PyPI release 9.2.0 (verified via pypi__pytest.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__pytest.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__pytest.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact pytest-9.1.1-py3-none-any.whl sha256 37a86b45efb9a47a61a36449063e8e18d0cab3161329fc099eb21783169c4f0c is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/pytest.requirements.txt`

**Fallback (proposal only):** project-declared runner after exact collection/config/environment identity; else BLOCKED

**Known failure / fail-closed route (proposal only):** No result accepted without exact TestInputSet, environment, plugins, target and output binding.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `pytest` 9.1.1; license MIT; first upload 2010-11-25; latest upload 2026-06-19; age 15.9y; source https://pypi.org/pypi/pytest/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-13 — Hypothesis

**Plan role / level:** P5/P7/P8 property-test, L1 (conditional L2). **F10 category:** property-test. **Consumed surface (proposal only):** bounded property strategy/result output.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/HypothesisWorks/hypothesis (verified via gh_repo__hypothesis.json)
| `version_tag_or_commit` | PyPI release 6.170.14 (verified via pypi__hypothesis.json)
| `license_expression_and_obligations` | MPL-2.0 (verified via gh_license__hypothesis.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__hypothesis.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact hypothesis-6.169.0-cp311-abi3-macosx_10_12_x86_64.whl sha256 e9e896e0175f0ccc4d3cabfdc704b363f0ccc84c7a3fee83ff7915015d9f8292 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/hypothesis.requirements.txt`

**Fallback (proposal only):** pytest deterministic contract fixtures; required property gap remains BLOCKED

**Known failure / fail-closed route (proposal only):** R9 requires review of MPL-2.0 file-level obligations including unmodified dependency use and redistribution form; license field remains UNVERIFIED until facts row and package files are inspected.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `hypothesis` 6.169.0; license MPL-2.0; first upload 2013-03-10; latest upload 2026-10-11; age 13.6y; source https://pypi.org/pypi/hypothesis/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification); flags: MPL-2.0 file-level obligations

### R9-14 — Schemathesis

**Plan role / level:** P5/P7/P9 API property-test, L1 (conditional L2). **F10 category:** property-test. **Consumed surface (proposal only):** OpenAPI-driven API test observations.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/schemathesis/schemathesis (verified via gh_repo__schemathesis.json)
| `version_tag_or_commit` | PyPI release 4.33.1 (verified via pypi__schemathesis.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__schemathesis.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__schemathesis.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact schemathesis-4.31.0-py3-none-any.whl sha256 12e4357ae07803e2620eff3a49ca6c7aa49bff95373b0002f12165afca523440 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/schemathesis.requirements.txt`

**Fallback (proposal only):** pytest contract fixtures; unavailable schema coverage remains BLOCKED

**Known failure / fail-closed route (proposal only):** API-schema tests do not replace domain properties; test server, hooks and schema must be identity-bound.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `schemathesis` 4.31.0; license MIT; first upload 2019-08-26; latest upload 2026-10-12; age 7.1y; source https://pypi.org/pypi/schemathesis/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-15 — mutmut

**Plan role / level:** P5/P7/P8 mutation diagnostic, L1 optional. **F10 category:** mutation. **Consumed surface (proposal only):** mutation inventory/killed-survived report.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/boxed/mutmut (verified via gh_repo__mutmut.json)
| `version_tag_or_commit` | PyPI release 3.8.1 (verified via pypi__mutmut.json)
| `license_expression_and_obligations` | BSD-3-Clause (verified via gh_license__mutmut.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__mutmut.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact mutmut-3.8.0-py3-none-any.whl sha256 4c0abcef6b8d1116f2adfaad19df12e1c621e4a402d4367ef15bf8cba497b91d is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/mutmut.requirements.txt`

**Fallback (proposal only):** no mutation fallback becomes a gate; report not available => UNKNOWN/BLOCKED for explicit mutation requirement

**Known failure / fail-closed route (proposal only):** Mutation score is a diagnostic, not proof or release authority.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `mutmut` 3.8.0; license BSD-3-Clause; first upload 2016-12-01; latest upload 2026-09-12; age 9.9y; source https://pypi.org/pypi/mutmut/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-16 — coverage.py

**Plan role / level:** P5/P7/P9 coverage sidecar, L1 (conditional L2). **F10 category:** contract tester (coverage sidecar only). **Consumed surface (proposal only):** coverage for exact Python test collection.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/nedbat/coveragepy (verified via gh_repo__coverage.json)
| `version_tag_or_commit` | PyPI release 7.17.2 (verified via pypi__coverage.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__coverage.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__coverage.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact coverage-7.16.2-cp310-cp310-macosx_10_9_x86_64.whl sha256 23219888477edd736b6fcaec1272d47d93b926e999641ffea7e53a1738e70b2b is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/coverage-py.requirements.txt`

**Fallback (proposal only):** no standalone coverage gate; missing report means coverage unknown

**Known failure / fail-closed route (proposal only):** Coverage is not correctness proof; bind collection, path omissions, source version and report.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `coverage` 7.16.2; license Apache-2.0; first upload 2009-05-16; latest upload 2026-09-27; age 17.4y; source https://pypi.org/pypi/coverage/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-17 — Host IDE runtime via ExecutionGate

**Plan role / level:** P6/P8 default worker runtime; existing host-provided runtime, not an OSS package. **F10 category:** repo-intelligence (only for target/diff observations; worker is not a verifier). **Consumed surface (proposal only):** proposed changes plus host observed effects.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | `UNVERIFIED` |
| `version_tag_or_commit` | `UNVERIFIED` |
| `license_expression_and_obligations` | `UNVERIFIED` |
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | `UNVERIFIED` |
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `No package installation. Launch only through existing ExecutionGate with exact runtime identity and host-boundary checks.`

**Fallback (proposal only):** owner-managed editing with no automation; required prevention unavailable => BLOCKED

**Known failure / fail-closed route (proposal only):** Host-native behavior is detect-and-contain only unless launched boundary is proven. The kernel owns state/evidence/release.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-18 — OpenHands Software Agent SDK

**Plan role / level:** P6/P8 optional adapter, L1/L2 conditional only. **F10 category:** repo-intelligence (diff/target observation; agent itself not a verifier). **Consumed surface (proposal only):** worker-proposed delta and untrusted textual claims.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/All-Hands-AI/OpenHands (verified via gh_repo__openhands.json)
| `version_tag_or_commit` | PyPI release 1.11.0 (verified via pypi__openhands-ai.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__openhands.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 1 security advisories in GitHub Security Advisories; ref gh_advisories__openhands.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact openhands_ai-1.11.0-py3-none-any.whl sha256 833de097150d498ffc7e175869df4723aec4a6b3c0be27545ca37089e6452c8f is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `Do not install/run until immutable version/artifact is identified and SHA-256/provenance is checked; if PyPI build chosen, use --require-hashes lock.`

**Fallback (proposal only):** Host IDE runtime through the same gate; otherwise owner-managed edits

**Known failure / fail-closed route (proposal only):** Owner-input classifies SDK as young/pre-1.0; optional only, never primary/foundational. Execution boundary required.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `openhands-ai` 1.11.0; license MIT; first upload 2024-08-20; latest upload 2026-07-09; age 2.1y; source https://pypi.org/pypi/openhands-ai/json; retrieved 2026-10-12

**Maturity rule result:** OPTIONAL (L1; adapter L2 only after qualification; never foundational); flags: agent/protocol SDK: fast-moving

### R9-19 — mini-SWE-agent

**Plan role / level:** P6/P8 optional adapter, L1/L2 conditional only. **F10 category:** repo-intelligence (diff/target observation; agent itself not a verifier). **Consumed surface (proposal only):** worker-proposed delta and untrusted textual claims.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/SWE-agent/mini-swe-agent (verified via gh_repo__mini-swe-agent.json)
| `version_tag_or_commit` | PyPI release 2.4.6 (verified via pypi__mini-swe-agent.json)
| `license_expression_and_obligations` | MIT License (verified via gh_license__mini-swe-agent.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__mini-swe-agent.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact mini_swe_agent-2.4.6-py3-none-any.whl sha256 a35463c553ac825c7773b03cfa69cd44958e3af20155dcc5711fdf9e4c67cd54 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/mini-swe-agent.requirements.txt only after exact package/version/hash source is available.`

**Fallback (proposal only):** Host IDE runtime via ExecutionGate; otherwise stop

**Known failure / fail-closed route (proposal only):** Owner-input classifies SDK as young; optional only; no loop/state authority or fence bypass.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `mini-swe-agent` 2.4.6; license MIT License Copyright (c) 2025 Kilian A. Lieret and Carlos E; first upload 2025-07-23; latest upload 2026-07-23; age 1.2y; source https://pypi.org/pypi/mini-swe-agent/json; retrieved 2026-10-12

**Maturity rule result:** OPTIONAL (L1; adapter L2 only after qualification; never foundational); flags: agent/protocol SDK: fast-moving; first upload 2025-07-23 (<2y)

### R9-20 — MCP Python SDK

**Plan role / level:** P1/P4/P6 optional protocol adapter, L1/L2 conditional only. **F10 category:** schema validator (message/result envelope only). **Consumed surface (proposal only):** tool messages/results with exact protocol and schema identity.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/modelcontextprotocol/python-sdk (verified via gh_repo__mcp.json)
| `version_tag_or_commit` | PyPI release 2.3.0 (verified via pypi__mcp.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__mcp.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 12 security advisories in GitHub Security Advisories; ref gh_advisories__mcp.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact mcp-2.3.0-py3-none-any.whl sha256 dd0c44c089d16453e8ae31a3877a0054d7a2314caaa81f5e0541b9b1734b2377 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/mcp.requirements.txt only after exact 2.x version and transitive hashes are sourced.`

**Fallback (proposal only):** host IDE native protocol path if available; otherwise tool integration stays unavailable/BLOCKED

**Known failure / fail-closed route (proposal only):** Protocol adoption != SDK maturity. Check exact MCP 2.x API stability, schema, transport/reconnect/failure behavior; not foundational.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `mcp` 2.3.0; license MIT; first upload 2024-11-20; latest upload 2026-10-02; age 1.9y; source https://pypi.org/pypi/mcp/json; retrieved 2026-10-12

**Maturity rule result:** OPTIONAL (L1; adapter L2 only after qualification; never foundational); flags: agent/protocol SDK: fast-moving; first upload 2024-11-20 (<2y)

### R9-21 — Agent Client Protocol SDK

**Plan role / level:** P4/P6 optional protocol adapter, L1/L2 conditional only. **F10 category:** schema validator (message/result envelope only). **Consumed surface (proposal only):** ACP message/result observations.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/agentclientprotocol/agent-client-protocol (verified via gh_repo__agent-client-protocol.json)
| `version_tag_or_commit` | PyPI release 0.12.1 (verified via pypi__agent-client-protocol.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__agent-client-protocol.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__agent-client-protocol.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact agent_client_protocol-0.12.1-py3-none-any.whl sha256 aaf3cc301ed87d9e2c4ccb91adfe1cd58784355f6ce7e513f50e7ca2391862ef is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/agent-client-protocol.requirements.txt only after exact version/hash evidence.`

**Fallback (proposal only):** host IDE native adapter where available, else no ACP integration

**Known failure / fail-closed route (proposal only):** Owner-input identifies SDK as young; only optional; do not implement ACP in S-Class or infer stability from protocol scope.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `agent-client-protocol` 0.12.1; license classifier-only: none; first upload 2025-09-06; latest upload 2026-10-12; age 1.1y; source https://pypi.org/pypi/agent-client-protocol/json; retrieved 2026-10-12

**Maturity rule result:** OPTIONAL (L1; adapter L2 only after qualification; never foundational); flags: agent/protocol SDK: fast-moving; first upload 2025-09-06 (<2y); 0.x version; SPDX unverified (classifier only)

### R9-22 — smolagents

**Plan role / level:** P6/P8 optional candidate only, L1/L2 max after test. **F10 category:** repo-intelligence (diff/target observation; agent is not verifier). **Consumed surface (proposal only):** worker-proposed delta/claims.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/huggingface/smolagents (verified via gh_repo__smolagents.json)
| `version_tag_or_commit` | PyPI release 1.26.0 (verified via pypi__smolagents.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__smolagents.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__smolagents.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact smolagents-1.26.0-py3-none-any.whl sha256 70e1cfb1576f782da93190ee31d9bb2659e5ca4bd84fda0c412e1f20498f28b6 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/smolagents.requirements.txt only after facts and exact dependency lock are supplied.`

**Fallback (proposal only):** host IDE default runtime or owner-managed edits

**Known failure / fail-closed route (proposal only):** Owner-input identifies it as young/pre-1.0; not default runtime, no foundational dependency.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `smolagents` 1.26.0; license classifier-only: none; first upload 2024-12-27; latest upload 2026-05-29; age 1.8y; source https://pypi.org/pypi/smolagents/json; retrieved 2026-10-12

**Maturity rule result:** OPTIONAL (L1; adapter L2 only after qualification; never foundational); flags: agent/protocol SDK: fast-moving; first upload 2024-12-27 (<2y); SPDX unverified (classifier only)

### R9-23 — LangGraph

**Plan role / level:** P6/P8 optional candidate only, L1/L2 max after test. **F10 category:** repo-intelligence (diff/target observation; agent is not verifier). **Consumed surface (proposal only):** proposed graph/worker claims only; never S-Class workflow state.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/langchain-ai/langgraph (verified via gh_repo__langgraph.json)
| `version_tag_or_commit` | PyPI release 1.2.20 (verified via pypi__langgraph.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__langgraph.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 13 security advisories in GitHub Security Advisories; ref gh_advisories__langgraph.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact langgraph-1.2.14-py3-none-any.whl sha256 e3f5f8ff4259f9281b73ff50fc9ef5cc3b025b8936b8283ecdca7cc0c4128690 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/langgraph.requirements.txt only after exact package/version/hash evidence.`

**Fallback (proposal only):** host IDE runtime or S-Class-owned existing workflow; do not create a second workflow engine

**Known failure / fail-closed route (proposal only):** Owner-input identifies it as young; deferred to avoid duplicating workflow/retry authority.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `langgraph` 1.2.14; license MIT; first upload 2024-01-08; latest upload 2026-10-06; age 2.8y; source https://pypi.org/pypi/langgraph/json; retrieved 2026-10-12

**Maturity rule result:** OPTIONAL (L1; adapter L2 only after qualification; never foundational); flags: agent/protocol SDK: fast-moving

### R9-24 — mypy

**Plan role / level:** P3/P5/P7/P8/P9 type checker, L1 (conditional L2). **F10 category:** type checker. **Consumed surface (proposal only):** Python type diagnostics and exact config/output.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/python/mypy (verified via gh_repo__mypy.json)
| `version_tag_or_commit` | PyPI release 2.4.1 (verified via pypi__mypy.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__mypy.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__mypy.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact mypy-2.4.0-cp310-cp310-macosx_11_0_arm64.whl sha256 ffda5244fd1ad71a1e54405e35f50d09b80c3978efa120f58bd1252ae32c62d2 is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/mypy.requirements.txt`

**Fallback (proposal only):** Ruff for lint only is not a type-check fallback; otherwise type coverage remains BLOCKED

**Known failure / fail-closed route (proposal only):** Python-specific and sensitive to stubs/configuration/Any escape routes.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `mypy` 2.4.0; license MIT; first upload 2009-09-09; latest upload 2026-10-01; age 17.1y; source https://pypi.org/pypi/mypy/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-25 — Ruff

**Plan role / level:** P5/P7/P9 repo-intelligence/lint, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** lint/style diagnostics only.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/astral-sh/ruff (verified via gh_repo__ruff.json)
| `version_tag_or_commit` | PyPI release 0.17.3 (verified via pypi__ruff.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__ruff.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__ruff.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact ruff-0.17.0-py3-none-linux_armv6l.whl sha256 0e271826af9a20d18c6cfae8c51e82959167c24859686ddd3eb9a7f0842ce81e is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/ruff.requirements.txt`

**Fallback (proposal only):** pinned project lint command if independently identity-bound, otherwise BLOCKED

**Known failure / fail-closed route (proposal only):** Not a complete static-security engine or type checker; config and excludes must be recorded.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `ruff` 0.17.0; license MIT; first upload 2022-08-27; latest upload 2026-10-09; age 4.1y; source https://pypi.org/pypi/ruff/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification); flags: 0.x version

### R9-26 — Gitleaks

**Plan role / level:** P6/P7/P9/P10 secret scanner, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** secret-finding observations over specified paths/config.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/gitleaks/gitleaks (verified via gh_repo__gitleaks.json)
| `version_tag_or_commit` | GitHub release v8.30.1 (verified via gh_release_latest__gitleaks.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__gitleaks.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__gitleaks.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/gitleaks.sha256 && verify provenance; no binary execution without digest.`

**Fallback (proposal only):** do not treat detect-secrets as an automatically equivalent fallback; without a qualified scanner hold required review

**Known failure / fail-closed route (proposal only):** Gitleaks GitHub/binary facts are UNVERIFIED; bind binary digest, rules/config, exclusions, target and raw output.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-27 — pip-audit

**Plan role / level:** P7/P9/P10/P11 Python dependency audit, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** dependency/advisory result tied to exact lock and data snapshot.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/pypa/pip-audit (verified via gh_repo__pip-audit.json)
| `version_tag_or_commit` | PyPI release 2.10.1 (verified via pypi__pip-audit.json)
| `license_expression_and_obligations` | Apache Software License (verified via gh_license__pip-audit.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__pip-audit.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact pip_audit-2.10.1-py3-none-any.whl sha256 99ef3f600a317c1945f1e89e227ef26e1c2d618429b8bd3fa6f4f7c440c4611a is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/pip-audit.requirements.txt`

**Fallback (proposal only):** OSV-Scanner only after its independent source/DB freshness is verified; otherwise BLOCKED

**Known failure / fail-closed route (proposal only):** Python-only scope; zero output cannot be interpreted as zero advisories if inventory/database unavailable.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `pip-audit` 2.10.1; license classifier-only: Apache Software License; first upload 2021-09-16; latest upload 2026-06-10; age 5.1y; source https://pypi.org/pypi/pip-audit/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification); flags: SPDX unverified (classifier only)

### R9-28 — OSV-Scanner

**Plan role / level:** P9/P10/P11 advisory scan companion, L1. **F10 category:** repo-intelligence. **Consumed surface (proposal only):** advisory findings over bound lock/SBOM and database snapshot.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/google/osv-scanner (verified via gh_repo__osv-scanner.json)
| `version_tag_or_commit` | GitHub release v2.7.0 (verified via gh_release_latest__osv-scanner.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__osv-scanner.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__osv-scanner.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/osv-scanner.sha256 && verify provenance; pin database/data-source snapshot if supported.`

**Fallback (proposal only):** pip-audit for Python-only data; general SBOM advisories stay BLOCKED absent this scanner/source

**Known failure / fail-closed route (proposal only):** GitHub/binary source identity and advisory data timestamp/hash UNVERIFIED.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-29 — Syft

**Plan role / level:** P10 SBOM/artifact inventory, L1 (conditional L2). **F10 category:** repo-intelligence. **Consumed surface (proposal only):** SBOM inventory bound to artifact digest.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/anchore/syft (verified via gh_repo__syft.json)
| `version_tag_or_commit` | GitHub release v1.56.0 (verified via gh_release_latest__syft.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__syft.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 3 security advisories in GitHub Security Advisories; ref gh_advisories__syft.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/syft.sha256 && verify provenance before use.`

**Fallback (proposal only):** cyclonedx-bom for its Python scope; missing whole-artifact inventory => release BLOCKED

**Known failure / fail-closed route (proposal only):** GitHub/binary SHA and license UNVERIFIED; inventory needs reconciliation with artifact/file manifest.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-30 — cyclonedx-bom

**Plan role / level:** P10 Python dependency SBOM companion, L1 (conditional L2). **F10 category:** schema validator (SBOM envelope only) plus repo-intelligence input. **Consumed surface (proposal only):** Python package inventory output; envelope validation is not completeness proof.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/CycloneDX/cyclonedx-python (verified via gh_repo__cyclonedx-bom.json)
| `version_tag_or_commit` | PyPI release 8.0.1 (verified via pypi__cyclonedx-bom.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__cyclonedx-bom.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__cyclonedx-bom.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact cyclonedx_bom-7.5.0-py3-none-any.whl sha256 a3020e225107214a66cb9c79ae83e3a71640a06d4ff3a0e2f9cb0d238f7061fd is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/cyclonedx-bom.requirements.txt`

**Fallback (proposal only):** Syft for broad artifact inventory; Python scope remains unknown if neither available

**Known failure / fail-closed route (proposal only):** PyPI facts absent; package SPDX/license and install hashes remain UNVERIFIED.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `cyclonedx-bom` 7.5.0; license Apache-2.0; first upload 2018-11-17; latest upload 2026-09-29; age 7.9y; source https://pypi.org/pypi/cyclonedx-bom/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-31 — Cosign

**Plan role / level:** P10 release signature/attestation check, L1. **F10 category:** schema validator (attestation envelope only; crypto/trust output is untrusted evidence). **Consumed surface (proposal only):** signature/attestation verification output bound to artifact and trust root.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/sigstore/cosign (verified via gh_repo__cosign.json)
| `version_tag_or_commit` | GitHub release v3.1.4 (verified via gh_release_latest__cosign.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__cosign.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 10 security advisories in GitHub Security Advisories; ref gh_advisories__cosign.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/cosign.sha256 && verify provenance/trust root before use.`

**Fallback (proposal only):** no release if pinned verifier or trust root is unavailable

**Known failure / fail-closed route (proposal only):** GitHub/binary facts and trust-root identity UNVERIFIED; signature validity is not release approval.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-32 — OpenTelemetry Python core

**Plan role / level:** P11 optional diagnostics, L1. **F10 category:** repo-intelligence (telemetry only, non-authoritative). **Consumed surface (proposal only):** signals bound to service/build/config; no gate closure.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/open-telemetry/opentelemetry-python (verified via gh_repo__opentelemetry.json)
| `version_tag_or_commit` | PyPI release 1.45.2 (verified via pypi__opentelemetry-api.json)
| `license_expression_and_obligations` | Apache-2.0 (verified via gh_license__opentelemetry.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 2 security advisories in GitHub Security Advisories; ref gh_advisories__opentelemetry.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | UNVERIFIED (sample artifact opentelemetry_api-1.45.1-py3-none-any.whl sha256 b31553efa588ae44bc306f863c785c5333a9ecc091248c6ee68b4b6c87fdedfb is NOT an install pin; per-platform hashes via `uv pip compile --generate-hashes`) |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `python -m pip install --require-hashes -r locks/opentelemetry-core.requirements.txt; enumerate packages separately.`

**Fallback (proposal only):** no telemetry interpretation; missing telemetry = UNKNOWN

**Known failure / fail-closed route (proposal only):** Core and each contrib/instrumentation/exporter package need separate source/license/egress review.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

**Facts (R10, source-row backed):** PyPI `opentelemetry-api` 1.45.1; license Apache-2.0; first upload 2019-10-01; latest upload 2026-10-06; age 7.0y; source https://pypi.org/pypi/opentelemetry-api/json; retrieved 2026-10-12

**Maturity rule result:** ADOPT-CANDIDATE (L2/L3 conditional on qualification)

### R9-33 — Renovate

**Plan role / level:** P11 dependency-update proposal only, L1. **F10 category:** process-source. **Consumed surface (proposal only):** pull-request/update proposal and lock diff.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/renovatebot/renovate (verified via gh_repo__renovate.json)
| `version_tag_or_commit` | GitHub release 44.219.0 (verified via gh_release_latest__renovate.json)
| `license_expression_and_obligations` | GPL-3.0 (verified via gh_license__renovate.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 25 security advisories in GitHub Security Advisories; ref gh_advisories__renovate.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `Pin immutable deployment/image digest and verify provenance; if package-distributed, exact hash lock required.`

**Fallback (proposal only):** manual owner-reviewed updates, no auto-merge

**Known failure / fail-closed route (proposal only):** Updater suggestions never authorize installs, state changes or release; identity change invalidates evidence.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-34 — bubblewrap

**Plan role / level:** P6 Linux worker launch boundary candidate, L1. **F10 category:** repo-intelligence for scope/observations only; isolation is an execution control. **Consumed surface (proposal only):** observed process/filesystem result bound to test target/host.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/containers/bubblewrap (verified via gh_repo__bubblewrap.json)
| `version_tag_or_commit` | GitHub release v0.13.1 (verified via gh_release_latest__bubblewrap.json)
| `license_expression_and_obligations` | LGPL-2.1 (verified via gh_license__bubblewrap.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 3 security advisories in GitHub Security Advisories; ref gh_advisories__bubblewrap.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `sha256sum --check locks/bubblewrap.sha256 && verify provenance; then only through ExecutionGate.`

**Fallback (proposal only):** if bwrap plus required AppArmor/Landlock/cgroups boundary is not proved, do not launch; BLOCKED

**Known failure / fail-closed route (proposal only):** GitHub/binary hash/license and exact OS support UNVERIFIED; host-native execution is detect-and-contain only.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-35 — AppArmor profile / host LSM control

**Plan role / level:** P6 Linux defense-in-depth control, not standalone OSS package choice. **F10 category:** repo-intelligence for observed enforcement state only. **Consumed surface (proposal only):** loaded profile digest, host identity and observed negative tests.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | `UNVERIFIED` |
| `version_tag_or_commit` | `UNVERIFIED` |
| `license_expression_and_obligations` | `UNVERIFIED` |
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | `UNVERIFIED` |
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `No generic install command in this record; inspect host package identity and effective loaded profile via owner-approved commands.`

**Fallback (proposal only):** if profile load/effective enforcement cannot be proved, no worker launch; BLOCKED

**Known failure / fail-closed route (proposal only):** Not interchangeable with namespaces/Landlock/cgroups; profile name/config alone is not proof.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-36 — Landlock host control

**Plan role / level:** P6 Linux defense-in-depth control, not standalone package choice. **F10 category:** repo-intelligence for observed enforcement state only. **Consumed surface (proposal only):** supported ABI/rules and observed blocked operations.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | `UNVERIFIED` |
| `version_tag_or_commit` | `UNVERIFIED` |
| `license_expression_and_obligations` | `UNVERIFIED` |
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | `UNVERIFIED` |
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `No generic package install; verify kernel/runtime support and rule effects with negative tests.`

**Fallback (proposal only):** if unavailable or ineffective on current kernel, no worker launch; BLOCKED

**Known failure / fail-closed route (proposal only):** Kernel feature presence does not prove configured rights restrictions are effective.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-37 — cgroups resource controls

**Plan role / level:** P6 Linux resource boundary facility, not standalone OSS package choice. **F10 category:** repo-intelligence for observed enforcement state only. **Consumed surface (proposal only):** resource limits and observed termination evidence.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | `UNVERIFIED` |
| `version_tag_or_commit` | `UNVERIFIED` |
| `license_expression_and_obligations` | `UNVERIFIED` |
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | `UNVERIFIED` |
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `No package install command; verify active controllers/configuration and adversarial resource tests.`

**Fallback (proposal only):** if limits cannot be enforced/observed, worker launch BLOCKED

**Known failure / fail-closed route (proposal only):** Resource control is complementary and not a filesystem/network sandbox.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.

### R9-38 — magic-context / CortexKit

**Plan role / level:** P1 optional L1 content/memory context only. **F10 category:** process-source. **Consumed surface (proposal only):** memory/context suggestions as claims only.

| Mandatory field | Value |
|---|---|
| `upstream_repository` | https://github.com/cortexkit/magic-context (verified via gh_repo__magic-context.json)
| `version_tag_or_commit` | GitHub release v0.49.35 (verified via gh_release_latest__magic-context.json)
| `license_expression_and_obligations` | MIT (verified via gh_license__magic-context.txt)
| `transitive_dependency_summary` | `UNVERIFIED` |
| `security_review_ref` | 0 security advisories in GitHub Security Advisories; ref gh_advisories__magic-context.json
| `test_ci_evidence_ref` | `UNVERIFIED` |
| `install_procedure_digest` | `UNVERIFIED` |
| `os_runtime_assumptions` | `UNVERIFIED` |
| `consumed_api_surface` | `UNVERIFIED` |
| `adapter_contract_version` | `UNVERIFIED` |
| `replacement_candidate` | `UNVERIFIED` |
| `fallback` | `UNVERIFIED` |
| `known_failure_modes` | `UNVERIFIED` |
| `qualification_status` | `UNVERIFIED` |
| `reviewer_ref` | `UNVERIFIED` |
| `record_digest` | `UNVERIFIED` |

**Hash-pinned install method (template only; not run):** `No execution in canonical path; if read-only source use is later approved, verify immutable repository/archive digest first.`

**Fallback (proposal only):** omit integration; use bounded source inventory

**Known failure / fail-closed route (proposal only):** Optional L1 only; license/maturity is UNVERIFIED; no authority or second durable store.

**F10 output treatment:** Tool output is an untrusted claim or identity-bound observation only. The existing F10 adapter validates schema/category and binds exact tool/version/config, target snapshot, environment, raw output and freshness; A1 reference conformance, A2 differential-result detection and A3 stale-evidence invalidation must pass. No output can create kernel state, authorize a change, waive a MUST, close an obligation, or approve release.


## R31 additions: evidence-backed records R9-39 .. R9-65

Facts in the `Evidence` columns were generated by script from raw responses saved in `product/oss-evidence/raw/` and listed with SHA-256 in `product/oss-evidence/MANIFEST.json` (retrieved 2026-11-05). `NOT RETRIEVED` means the request failed from the capture environment and nothing was filled in. All GitHub API endpoints, release chronologies, raw licenses, and security advisories (GitHub + OSV) have been captured under active GitHub authentication. The table below incorporates stars, pushed_at, and advisory counts. Judgment columns (fit, strongest reason not to use, pair) are CL-authored. Nothing here is QUALIFIED; the 16-field records below stay UNVERIFIED for fields without evidence.

| Record | Tool | Phase | Role | Version (PyPI/npm) | First release | Last release | Licence (metadata) | Licence (raw LICENSE file) | PyPI publisher / source URL | Requires Python | Stars | Pushed at | Advisories | Proposed level | Why that level | Evidence files (sha256 prefix) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R9-39 | bashlex | P6/B5 | Bash parser (command analysis input, parser B) | 0.18 | 2014-09-25 | 2023-01-18 | GPLv3+ | GPL-3.0 | Idan Kamara / https://github.com/idank/bashlex.git | >=2.7, !=3.0, !=3.1, !=3.2, !=3.3, !=3.4 | 652 | 2024-04-08T10:31:59Z | 0 | L1 | version 0.18 <1.0 ; licence GPL-3.0 not permissive ; last release 2023-01-18 >12 months | pypi__bashlex.json 61d56fef7f63; gh_repo__bashlex.json f2c6c9cd5749; gh_license__bashlex.txt 8ceb4b9ee5ad; gh_releases__bashlex.json 4f53cda18c2b |
| R9-40 | tree-sitter-bash | P6/B5 | Bash grammar (command analysis, parser A) | 0.25.1 | 2017-07-14 | 2025-12-02 | MIT | MIT | tree-sitter / https://github.com/tree-sitter/tree-sitter-bash | n/a | 335 | 2026-09-13T07:50:45Z | 0 | L1 | no release-date evidence for npm package (only latest metadata retrieved) | npm__tree-sitter-bash.json 6c8d8b28506b; gh_repo__tree-sitter-bash.json 5551cc0f9c4c; gh_license__tree-sitter-bash.txt 49bf33cf78ef; gh_release_latest__tree-sitter-bash.json ae75799744c2 |
| R9-41 | mvdan-sh | P6/B5 | Shell parser in Go (command analysis, parser C, offline helper) | v3.14.1 | 2016-01-16 | 2026-09-06 | BSD-3-Clause | BSD-3-Clause | mvdan / https://github.com/mvdan/sh | n/a | 9179 | 2026-11-03T15:03:41Z | 0 | L1 | no release-date evidence retrieved | gh_repo__mvdan-sh.json 5c7a927bce03; gh_license__mvdan-sh.txt ce63850f7764; gh_release_latest__mvdan-sh.json c8715abc661e; gh_releases__mvdan-sh.json 82175fa3def9 |
| R9-42 | shellcheck | P6/P7 | Shell static analysis (advisory lint of agent scripts) | v0.11.0 | 2012-11-17 | 2025-08-04 | GPL-3.0 | GPL-3.0 | koalaman / https://github.com/koalaman/shellcheck | n/a | 40285 | 2026-11-05T09:06:20Z | 0 | L1 | no release-date evidence retrieved | gh_repo__shellcheck.json 8d7a3e1a30e6; gh_license__shellcheck.txt 3972dc9744f6; gh_release_latest__shellcheck.json f8107b7aa446; gh_releases__shellcheck.json 0f8429b25a70 |
| R9-43 | pyright | P7 | Static type check (pair with mypy R9-24) | 1.1.414 | 2021-06-20 | 2026-09-10 | MIT | MIT | Robert Craigie / https://github.com/RobertCraigie/pyright-pyth | >=3.7 | 15732 | 2026-11-04T22:55:43Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required. MISMATCH: wrapper https://github.com/RobertCraigie/pyright-python vs canonical https://github.com/microsoft/pyright. [Age inputs: repo_created=2019-03-12, first_gh=2023-06-21, first_reg=2021-06-20 -> earliest=2019-03-12; Version inputs: gh_ver=1.1.414, reg_ver=1.1.414 -> latest=1.1.414] | pypi__pyright.json 8c7dfa76905c; npm__pyright.json de5bf1efacf0; gh_repo__pyright.json be6f2aeeccfc; gh_license__pyright.txt f7c936bc43f1 |
| R9-44 | pyre-check | P7 | Optional third type checker | 0.10.0 | 2018-05-14 | 2026-08-06 | MIT | MIT | Facebook / https://pyre-check.org/ | >=3.9 | 7181 | 2026-06-26T16:04:19Z | 0 | L1 | version 0.10.0 <1.0; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2017-11-10, first_gh=2019-08-07, first_reg=2018-05-14 -> earliest=2017-11-10; Version inputs: gh_ver=v0.9.23, reg_ver=0.10.0 -> latest=0.10.0] | pypi__pyre-check.json 980e1ea45ced; gh_repo__pyre-check.json c2515aaa6423; gh_license__pyre-check.txt da6d3703ed11; gh_release_latest__pyre-check.json 00d0974e204a |
| R9-45 | diff-cover | P5/P7 | Coverage and quality on changed lines only | 11.0.1 | 2013-06-28 | 2026-11-04 | Apache-2.0 | Apache-2.0 | See Contributors / https://pypi.org/project/diff_cover/ | >=3.11 | 850 | 2026-11-04T02:29:40Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__diff-cover.json e1d69c35f5c7; gh_repo__diff-cover.json d13dc027d978; gh_license__diff-cover.txt 0d542e0c8804; gh_release_latest__diff-cover.json 0b796bce49ba |
| R9-46 | import-linter | P3/P7 | Architecture import contracts | 2.15 | 2019-01-27 | 2026-09-04 | BSD 2-Clause License | BSD-2-Clause | David Seddon <david@seddo / https://pypi.org/project/import-linter/ | >=3.10 | 1250 | 2026-11-05T09:52:36Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__import-linter.json 467a8478f7d4; gh_repo__import-linter.json ce9e5f222643; gh_license__import-linter.txt 79148a8320bf; gh_releases__import-linter.json 4f53cda18c2b |
| R9-47 | detect-secrets | P7/P10 | Secret scanning (pair with Gitleaks R9-26) | 1.5.0 | 2018-04-05 | 2024-05-06 | Apache Software License | Apache-2.0 | Yelp, Inc. / https://github.com/Yelp/detect-secrets | n/a | 4665 | 2026-04-02T17:10:40Z | 0 | L1 | last release 2024-05-06 >12 months | pypi__detect-secrets.json acfdb1262a95; gh_repo__detect-secrets.json 10806a5c2619; gh_license__detect-secrets.txt cd6e5b5e743a; gh_release_latest__detect-secrets.json b4ca5969c631 |
| R9-48 | pytest-timeout | P5 | Kill hung tests | 2.4.0 | 2012-02-27 | 2026-08-16 | MIT | MIT | Floris Bruynooghe / https://github.com/pytest-dev/pytest-timeout | >=3.7 | 261 | 2026-10-31T17:42:51Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__pytest-timeout.json 145b1c3c92f4; gh_repo__pytest-timeout.json bac25d5474bf; gh_license__pytest-timeout.txt 1e66470a1b2d; gh_releases__pytest-timeout.json 4f53cda18c2b |
| R9-49 | pytest-rerunfailures | P5 | Flaky test retry | 16.7 | 2012-12-28 | 2026-09-17 | MPL-2.0 | MPL-2.0 | Leah Klearman <lklrmn@gma / https://pypi.org/project/pytest-rerunfailures | >=3.10 | 482 | 2026-10-07T06:42:17Z | 0 | L1 | licence MPL-2.0 not permissive | pypi__pytest-rerunfailures.json 84b5da3223b2; gh_repo__pytest-rerunfailures.json 95761bd5f6cb; gh_license__pytest-rerunfailures.txt bb431ce4826f; gh_releases__pytest-rerunfailures.json 4f53cda18c2b |
| R9-50 | pytest-randomly | P5 | Random test order and seed pinning | 5.0.0 | 2016-04-15 | 2026-09-01 | MIT | MIT | Adam Johnson / https://pypi.org/project/pytest-randomly/ | >=3.10 | 724 | 2026-11-02T22:55:48Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__pytest-randomly.json e54f386cce3f; gh_repo__pytest-randomly.json dcedc9912ad2; gh_license__pytest-randomly.txt d9705af13193; gh_releases__pytest-randomly.json 4f53cda18c2b |
| R9-51 | pytest-xdist | P5 | Parallel test execution | 3.8.0 | 2010-01-18 | 2025-07-01 | MIT | MIT | holger krekel and contrib / https://pypi.org/project/pytest-xdist/ | >=3.9 | 1931 | 2026-11-02T23:34:25Z | 0 | L1 | last release 2025-07-01 >12 months | pypi__pytest-xdist.json c28c9a15d09e; gh_repo__pytest-xdist.json 0c0d02e99fd3; gh_license__pytest-xdist.txt 36c15bf831b2; gh_release_latest__pytest-xdist.json 329496560918 |
| R9-52 | pip-licenses | P10 | Licence inventory of installed packages | 5.5.5 | 2018-02-05 | 2026-10-05 | MIT | MIT | Mr. Walls / https://pypi.org/project/pip-licenses/ | >=3.9 | 378 | 2026-11-05T06:36:35Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__pip-licenses.json 4f67bd89e5d7; gh_repo__pip-licenses.json 6a1cb7f6454e; gh_license__pip-licenses.txt b3cd2ad74a7c; gh_release_latest__pip-licenses.json 4dbb4626c1f4 |
| R9-53 | licensecheck | P10 | Licence compatibility check | 2026.0.8 | 2020-10-11 | 2026-06-18 | MIT | MIT | FredHappyface / https://pypi.org/project/licensecheck/ | >=3.12 | 116 | 2026-10-25T13:44:43Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__licensecheck.json d6f02af05c4f; gh_repo__licensecheck.json 30c77c90ff64; gh_license__licensecheck.txt 6b0e1f416fe2; gh_release_latest__licensecheck.json b5462d9e4482 |
| R9-54 | scancode-toolkit | P10 | Licence and copyright detection from source text | 32.5.0 | 2017-06-16 | 2026-05-19 | Apache-2.0 AND CC-BY-4.0 AND Licens | Apache-2.0 / CC-BY-4.0 | nexB. Inc. and others / https://github.com/aboutcode-org/scancode-too | >=3.10 | 2662 | 2026-11-02T22:19:55Z | 0 | L1 | mixed licence expression (LicenseRef-*): obligations unreviewed | pypi__scancode-toolkit.json 8ad6e1750745; gh_repo__scancode.json 42c6ef179d65; gh_license__scancode.txt e56cd09ca254; gh_release_latest__scancode.json 6db818996d61 |
| R9-55 | in-toto | P10 | Supply-chain attestation layout | 3.1.0 | 2017-11-09 | 2026-04-25 | Apache-2.0 | Apache-2.0 | "New York University: Sec / https://pypi.org/project/in-toto/ | >=3.9 | 1055 | 2026-08-27T21:33:28Z | 2 (GHSA-jjgp-whrp-gq8m, GHSA-wc64-c5rv-32pf) | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__in-toto.json 6f4276b0a38d; gh_repo__in-toto.json bb7d42adf3fc; gh_license__in-toto.txt b5c26c8a2ad6; gh_release_latest__in-toto.json ffe822cb94bd |
| R9-56 | sigstore | P10 | Keyless signing and verification (sigstore-python) | 4.5.1 | 2022-04-28 | 2026-10-20 | Apache-2.0 | Apache-2.0 | Sigstore Authors / https://pypi.org/project/sigstore/ | >=3.10 | 338 | 2026-11-04T20:12:44Z | 2 (GHSA-hm8f-75xx-w2vr, GHSA-hhfg-fwrw-87w7) | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__sigstore.json e00a7fcc0f2b; gh_repo__sigstore-python.json 1bb4c983262f; gh_license__sigstore-python.txt cfc7749b96f6; gh_release_latest__sigstore-python.json de7fd42f5c4b |
| R9-57 | scorecard | P10 | Dependency health scoring (OpenSSF Scorecard) | v5.6.0 | 2020-10-09 | 2026-10-12 | Apache-2.0 | Apache-2.0 | ossf / https://github.com/ossf/scorecard | n/a | 5814 | 2026-11-05T08:37:08Z | 0 | L1 | no release-date evidence retrieved | gh_repo__scorecard.json 66d57b8eabd0; gh_license__scorecard.txt 61324beb8841; gh_release_latest__scorecard.json 489c8f1d7e4d; gh_releases__scorecard.json f0f2af3d8c19 |
| R9-58 | promptfoo | P11/P9 | Agent and prompt red-team test harness (testing only) | 0.125.1 | 2023-04-28 | 2026-10-25 | MIT | MIT | promptfoo / https://github.com/promptfoo/promptfoo | n/a | 26868 | 2026-11-05T10:20:14Z | 0 | L1 | fast-moving API; testing only; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2023-04-28, first_gh=2024-07-01, first_reg=2023-04-28 -> earliest=2023-04-28; Version inputs: gh_ver=0.125.1, reg_ver=0.125.1 -> latest=0.125.1] | npm__promptfoo.json 94556478458c; gh_repo__promptfoo.json 3194c40f539d; gh_license__promptfoo.txt bf813686553f; gh_release_latest__promptfoo.json 25d68f0c0916 |
| R9-59 | garak | P11/P9 | LLM vulnerability scanner (testing only) | 0.17.1 | 2023-06-12 | 2026-10-16 | Apache-2.0 | Apache-2.0 | nv052193, Mads Kongsbak,  / https://pypi.org/project/garak/ | >=3.11 | 9868 | 2026-11-04T21:42:11Z | 0 | L1 | version 0.17.1 <1.0 | pypi__garak.json aceee867c6fa; gh_repo__garak.json 6e31abd8e0b4; gh_license__garak.txt f12c175308d6; gh_release_latest__garak.json 148e49a75c55 |
| R9-60 | pyrit | P11/P9 | Red-team automation framework (testing only) | 1.1.0 | 2024-02-21 | 2026-09-04 | MIT | MIT | Microsoft AI Red Team <ai / https://pypi.org/project/pyrit/ | <3.15,>=3.10 | 123 | 2026-03-25T01:18:52Z | 0 | L2-proposable | meets age/version/licence/recency rule; heavy dependency tree; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2026-03-25, first_gh=None, first_reg=2024-02-21 -> earliest=2024-02-21; Version inputs: gh_ver=None, reg_ver=1.1.0 -> latest=1.1.0] | pypi__pyrit.json 1d3b7945e144; gh_repo__pyrit.json 2accc6c357b9; gh_license__pyrit.txt c2cfccb812fe; gh_releases__pyrit.json 4f53cda18c2b |
| R9-61 | pygls | P6/B7 | Python LSP server framework (optional host adapter) | 2.1.1 | 2018-12-21 | 2026-03-25 | Apache-2.0 | Apache-2.0 | Open Law Library / https://pypi.org/project/pygls/ | >=3.9 | 813 | 2026-11-03T03:15:04Z | 0 | L2-proposable | meets age/version/licence/recency rule; install-hash, security, F10 evidence still required | pypi__pygls.json 0d2cb07486f3; gh_repo__pygls.json 9ab443af594c; gh_license__pygls.txt 6f4915c6bf1a; gh_release_latest__pygls.json 60403627e900 |
| R9-62 | lsprotocol | P6/B7 | LSP type definitions | 2025.0.0 | 2022-07-13 | 2025-06-17 | MIT License | MIT | Microsoft Corporation <ls / https://pypi.org/project/lsprotocol/ | >=3.8 | 160 | 2026-10-27T20:27:36Z | 0 | L1 | last release 2025-06-17 >12 months | pypi__lsprotocol.json 7fde6bf214d1; gh_repo__lsprotocol.json c8ebf1a35ace; gh_license__lsprotocol.txt c2cfccb812fe; gh_release_latest__lsprotocol.json e87bd63fdc16 |
| R9-63 | sarif-tools | P9/P11 | SARIF reading and diffing | 3.0.5 | 2021-11-11 | 2025-07-17 | MIT License | MIT | Microsoft / https://pypi.org/project/sarif-tools/ | <4.0,>=3.8 | 160 | 2026-10-27T20:29:48Z | 0 | L1 | last release 2025-07-17 >12 months | pypi__sarif-tools.json 57b1f6f986d3; gh_repo__sarif-tools.json c8bad7a95bd7; gh_license__sarif-tools.txt c2cfccb812fe; gh_release_latest__sarif-tools.json 35ab643b9da0 |
| R9-64 | opengrep | P7/P9 | Semgrep-engine fork for SAST | v1.33.1 | 2024-12-14 | 2026-10-29 | LGPL-2.1 | LGPL-2.1 | opengrep / https://github.com/opengrep/opengrep | n/a | 3286 | 2026-11-05T12:38:25Z | 1 (MAL-2025-2981) | L1 | no release-date evidence retrieved | gh_repo__opengrep.json e31d1edbd030; gh_license__opengrep.txt 20c17d8b8c48; gh_release_latest__opengrep.json 351f40a2d6ae; gh_releases__opengrep.json 3ba6a31ad05f |
| R9-65 | pr-agent | P9 | Optional PR review claim generator | 0.49.0 | 2024-03-23 | 2026-10-25 | MIT License | MIT | QodoAI <ofir.f@qodo.ai> / https://pypi.org/project/pr-agent/ | >=3.12 | 15006 | 2026-11-05T08:37:25Z | 0 | L1 | version 0.49.0 <1.0; Supersedes R31 evidence with R32 sweep data (moved org: qodo-ai/pr-agent -> The-PR-Agent/pr-agent). [Age inputs: repo_created=2023-07-05, first_gh=2023-09-20, first_reg=2024-03-23 -> earliest=2023-07-05; Version inputs: gh_ver=v0.49.0, reg_ver=0.49.0 -> latest=0.49.0] | pypi__pr-agent.json 3b3534c4b928; gh_repo__pr-agent.json 929b42bdbc8d; gh_license__pr-agent.txt ea19f3b6bfd7; gh_release_latest__pr-agent.json 9ff11fc459b9 |

### Judgment per record (CL-authored)

| Record | Tool | Fit | Strongest reason not to use | Independent pair | Level |
|---|---|---|---|---|---|
| R9-39 | bashlex | Independent second parser for the command analyzer; used only to produce a parse OBSERVATION, never a verdict. | GPLv3 and last release 2023-01-18. Importing it into a non-GPL core may impose GPL obligations; run only as an isolated subprocess, or drop it if S-Class distribution is not GPL-compatible (Ak decision). A parser mismatch with bash is itself a bypass class. | tree-sitter-bash; mvdan/sh | L1 |
| R9-40 | tree-sitter-bash | Grammar for tree-sitter core (R9-04); error-tolerant parse tree. Parse is an observation; any ERROR node = fail closed. | Grammar is error-tolerant: it can return a tree for input real bash rejects. Only npm metadata retrieved; PyPI binding and release dates NOT RETRIEVED. | bashlex; mvdan/sh | L1 |
| R9-41 | mvdan-sh | Strict POSIX/Bash/mksh parser with a formatter; third independent parse for disagreement checking. | Go binary, not Python; release date, version and advisories NOT RETRIEVED (GitHub releases blocked). Needs a pinned, hash-checked binary. | bashlex; tree-sitter-bash | L1 |
| R9-42 | shellcheck | Finds quoting, injection-prone and portability defects in shell scripts the agent writes. Advisory observation only. | GPLv3 Haskell binary: use only as an external process, never linked. Release data NOT RETRIEVED. It lints scripts; it does not prove a command safe. | bashlex | L1 |
| R9-43 | pyright | Independent type verifier to pair with mypy (different implementation, different inference). | The PyPI `pyright` package is a THIRD-PARTY wrapper (publisher Robert Craigie, source RobertCraigie/pyright-python), not Microsoft's; it downloads the npm package at run time. Prefer the npm `pyright` tarball pinned by hash, or accept the wrapper as an extra supply-chain link. Node dependency. | mypy | L2-proposable |
| R9-44 | pyre-check | Optional only. | Version 0.10.0 is pre-1.0; keep L1. Do not make it a required pair. | mypy; pyright | L1 |
| R9-45 | diff-cover | Answers 'are the lines this change touches tested?' which total coverage hides. Output is an observation. | Requires Python >=3.11, so it runs in a separate tools venv, not on the 3.10 CI leg. Relies on the coverage XML it is given; a wrong coverage file gives a wrong answer. | coverage.py (R9-16) | L2-proposable |
| R9-46 | import-linter | Complements S-Class's own `tests/guards/test_import_direction_guard.py` with declarative layer contracts. Not a replacement: keep the own guard as authority. | Python imports only; cannot see dynamic imports or other languages. | own guard test | L2-proposable |
| R9-47 | detect-secrets | Second, independent secret scanner so one scanner's blind spot does not decide. | Last PyPI release 2024-05-06 (more than 12 months old), PyPI licence field empty (classifier and raw LICENSE say Apache-2.0). Treat as stale; keep L1. | gitleaks | L1 |
| R9-48 | pytest-timeout | Bounds test runtime so a hanging test cannot stall a gate. | Signal-based timeouts are unreliable on Windows threads; use the thread method there. A timeout is a FAIL, never a skip. | none needed | L2-proposable |
| R9-49 | pytest-rerunfailures | NOT recommended for gate, mutation or evidence runs: a retry that passes hides a real intermittent failure. | MPL-2.0 (file-level copyleft; fine as a dev-only tool). The design risk is behavioural: retries convert failures into passes. Ban it in gate suites. | none | L1 |
| R9-50 | pytest-randomly | Exposes order-dependent tests, which matter for the fail-open class (shared state). | Seed must be recorded in the evidence, otherwise a failure is not reproducible. | pytest-xdist | L2-proposable |
| R9-51 | pytest-xdist | Speeds the full suite; parallel runs also expose shared-state defects. | Last release 2025-07-01 (16 months). Parallel logs interleave: evidence runs must record the worker count. | none | L1 |
| R9-52 | pip-licenses | Cheap licence inventory for the release bundle. | Reads package metadata only, which is often wrong or empty (see detect-secrets, garak). Never the sole licence authority. | scancode-toolkit | L2-proposable |
| R9-53 | licensecheck | Checks declared licences for compatibility. | Requires Python >=3.12, so it cannot run on the 3.10/3.11 CI legs; tools venv only. | pip-licenses; scancode-toolkit | L2-proposable |
| R9-54 | scancode-toolkit | Detects licences from actual file content, independent of package metadata. | Own licence expression is 'Apache-2.0 AND CC-BY-4.0 AND LicenseRef-scancode-other-permissive': read the obligations before bundling its data. Heavy, slow scan. | pip-licenses | L1 |
| R9-55 | in-toto | Attestation format for release evidence (who ran which step on which files). | Needs separate key management; attestations are claims until verified against a pinned trusted key. | sigstore; cosign (R9-31) | L2-proposable |
| R9-56 | sigstore | Python client for signing and verifying release artefacts; pair with cosign (R9-31). | Keyless flow depends on the public transparency log and identity provider being reachable; offline verification needs pinned trust roots. | cosign | L2-proposable |
| R9-57 | scorecard | Scores a dependency's repository practices; screening input for the qualification record. | Go binary; needs GitHub API access that this environment cannot reach; release data NOT RETRIEVED. Score is advisory and gameable. | manual qualification record | L1 |
| R9-58 | promptfoo | Runs adversarial prompt suites against S-Class's own boundary as TEST input. Its output is never a gate authority. | Version 0.125.1 is pre-1.0 and Node-based; fast-moving API. Test-time only. | garak; PyRIT | L1 |
| R9-59 | garak | Probe library for injection and jailbreak classes, usable as an independent attack corpus. | Version 0.17.1 pre-1.0; PyPI licence field empty (raw LICENSE is Apache-2.0); requires Python >=3.11. | promptfoo; PyRIT | L1 |
| R9-60 | pyrit | Third independent attack generator for the adversarial suite. | First release 2024-02-21 (under 2 years); keep L1. Heavy dependency tree. | promptfoo; garak | L2-proposable |
| R9-61 | pygls | Only if S-Class later exposes an LSP surface. | Licence is Apache-2.0 per PyPI (not MIT). Not needed for MCP host path: do not adopt speculatively. | own thin adapter | L2-proposable |
| R9-62 | lsprotocol | Types only. | Last release 2025-06-17 (over 12 months). Pair of pygls: adopt only with it. | none | L1 |
| R9-63 | sarif-tools | Reading SARIF output from scanners into the F10 adapter. | Last release 2025-07-17 (over 12 months); parsing untrusted SARIF is itself an input boundary: validate against the SARIF schema first. | own SARIF schema validation | L1 |
| R9-64 | opengrep | Second engine with the same rule format as Semgrep (R9-08), so rules can be cross-checked. | LGPL-2.1 per raw LICENSE (same family as the Semgrep engine); NOT on PyPI under this name (request returned no data); release dates NOT RETRIEVED. | semgrep; bandit | L1 |
| R9-65 | pr-agent | Already scoped as L1 optional P9 claim generator in OSS-FASTTRACK-REVIEW.md. Output is untrusted claims through falsifiability. | Version 0.49.0 pre-1.0, requires Python >=3.12, sends code to a model API; PyPI source URL now points to the-pr-agent/pr-agent (the repo moved org: re-confirm the canonical upstream and its maintainers before any use). PyPI licence field contains the whole MIT text, not an SPDX id. | kodus (deferred); CodeRabbit (advisory) | L1 |

### Evidence upgrades to existing records (PyPI only; same capture)

| Existing record | Package | Version | First release | Last release | Licence (PyPI) | Stars | Pushed at | Advisories | Note |
|---|---|---|---|---|---|---|---|---|---|
| R9-08 | semgrep | 1.183.0 | 2020-05-06 | 2026-10-29 | LGPL-2.1-or-later | 17470 | 2026-11-05T07:42:04Z | 0 | engine only; rules licensed separately; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2019-12-13, first_gh=2021-02-24, first_reg=2020-05-06 -> earliest=2019-12-13; Version inputs: gh_ver=v1.184.0, reg_ver=1.183.0 -> latest=1.184.0] |
| R9-10 | bandit | 1.9.4 | 2015-03-23 | 2026-02-25 | Apache-2.0 | 8373 | 2026-11-02T10:34:20Z | 0 | Python-only scanner |
| R9-13 | hypothesis | 6.170.14 | 2013-03-10 | 2026-10-30 | MPL-2.0 | 9137 | 2026-11-03T19:03:28Z | 0 | MPL-2.0 weak copyleft (dev-only use) |
| R9-15 | mutmut | 3.8.1 | 2016-12-01 | 2026-10-28 | BSD-3-Clause | 1525 | 2026-10-28T08:41:44Z | 0 | BSD-3 |
| R9-16 | coverage | 7.17.2 | 2009-05-16 | 2026-11-04 | Apache-2.0 | 3425 | 2026-11-05T12:29:51Z | 0 | requires Python >=3.11: tools venv for the 3.10 leg |
| R9-24 | mypy | 2.4.1 | 2009-09-09 | 2026-10-28 | MIT | 20712 | 2026-11-05T00:40:27Z | 0 | pairs with pyright |
| R9-25 | ruff | 0.17.3 | 2022-08-27 | 2026-10-27 | MIT | 50438 | 2026-11-05T12:07:59Z | 0 | 0.x pre-1.0: stays L1; Supersedes R31 evidence with R32 sweep data. [Age inputs: repo_created=2022-08-09, first_gh=2022-12-04, first_reg=2022-08-27 -> earliest=2022-08-09; Version inputs: gh_ver=0.17.4, reg_ver=0.17.3 -> latest=0.17.4] |
| R9-27 | pip-audit | 2.10.1 | 2021-09-16 | 2026-06-10 | Apache Software License | 1391 | 2026-10-30T23:38:23Z | 0 | licence only in classifier |
| R9-30 | cyclonedx-bom | 8.0.1 | 2018-11-17 | 2026-11-04 | Apache-2.0 | 398 | 2026-11-04T13:40:07Z | 0 | requires Python <4,>=3.9 |

## R31 phase coverage verdict (P0-P11), CL-authored

Verdict words: COVERED = at least two independent tools with records (any level) plus an S-Class adapter slot; PARTIAL = one tool, or two that are not independent; BUILD-OWN = no mature OSS fits, S-Class owns it (this is by design for authority logic). No row means QUALIFIED: every record is still UNVERIFIED for install-hash, security review and F10 evidence.

| Phase | Existing records | New R31 records | Independent pair | Verdict | Remaining gap |
|---|---|---|---|---|---|
| P0 Intent | R9-01 Spec Kit, R9-02 OpenSpec (L1 content) | none | none | BUILD-OWN | Intent confirmation is human authority (Ak/user); no OSS replaces it |
| P1 Discovery | R9-04 tree-sitter, R9-05 SCIP, R9-06 ast-grep | R9-40 tree-sitter-bash | tree-sitter + ast-grep | COVERED | SCIP needs an independent indexer per language |
| P2 Requirements | R9-03 jsonschema, R9-01/02 | none | none | PARTIAL | OpenAPI tooling not recorded; traceability links are S-Class F6 |
| P3 Design | R9-11 OPA | R9-46 import-linter | import-linter + own guard test | COVERED | Cross-language boundaries unchecked |
| P4 Planning | R9-23 LangGraph (optional adapter) | none | none | BUILD-OWN | Plan checks (symbols, write set, order) are S-Class authority; no OSS is a planner of record |
| P5 Testing | R9-12 pytest, R9-13 Hypothesis, R9-14 Schemathesis, R9-15 mutmut, R9-16 coverage | R9-45 diff-cover, R9-48 timeout, R9-50 randomly, R9-51 xdist, R9-49 rerunfailures (banned in gates) | mutmut + Hypothesis; coverage + diff-cover | COVERED | Other languages' mutation tools unrecorded |
| P6 Implementation | R9-17 host IDE via ExecutionGate, R9-20 MCP SDK, R9-21 ACP SDK, R9-34/35/36/37 sandbox controls | R9-39 bashlex, R9-40 tree-sitter-bash, R9-41 mvdan/sh, R9-42 ShellCheck | three independent bash parsers (all observation-only) | PARTIAL | Parsers are mistake filters, not a boundary: prevention rests only on the launched sandbox (R9-34..37). Behavioural probes remain S-Class tests |
| P7 Verification | R9-08 semgrep, R9-10 bandit, R9-24 mypy, R9-25 ruff, R9-26 gitleaks | R9-43 pyright, R9-44 pyre-check, R9-47 detect-secrets, R9-64 opengrep | mypy + pyright; semgrep + bandit; gitleaks + detect-secrets | COVERED | Semgrep rules licence unresolved; secret scanners both lag new key formats |
| P8 Repair | none | none | none | BUILD-OWN | Repair is an agent action; S-Class bounds it with scope lock and re-verification, no OSS auto-repair is trusted |
| P9 Review | none qualified | R9-65 PR-Agent (L1 claim generator), R9-63 sarif-tools, R9-64 opengrep | falsifiability stage (quote re-match + deterministic corroboration) | PARTIAL | Reviewers are claim sources only; build an internal gold set from real defects before trusting any reviewer; vendor benchmarks unverified |
| P10 Release | R9-27 pip-audit, R9-28 OSV-Scanner, R9-29 Syft, R9-30 cyclonedx-bom, R9-31 Cosign | R9-52 pip-licenses, R9-53 licensecheck, R9-54 scancode, R9-55 in-toto, R9-56 sigstore, R9-57 scorecard | pip-audit + OSV-Scanner; cosign + sigstore; pip-licenses + scancode | COVERED | Licence decisions need Ak's distribution model |
| P11 Continuous | R9-32 OpenTelemetry, R9-33 Renovate | R9-58 promptfoo, R9-59 garak, R9-60 PyRIT, R9-61 pygls, R9-62 lsprotocol | promptfoo + garak + PyRIT as attack corpora | PARTIAL | Adversarial tools are test-time only and never gate authority; LSP not needed on the MCP path |

### Where GPT's two research reports were wrong (corrected from the captured files)

| GPT claim | Evidence | Correction |
|---|---|---|
| diff-cover is AGPL-3.0, 0 stars, last release 2016, unmaintained | PyPI: Apache-2.0, 160 releases, last release 2026-11-04; raw LICENSE is Apache License 2.0 | Claim false. Not a do-not-adopt tool |
| import-linter is MIT | raw LICENSE: BSD 2-Clause | Wrong licence |
| pytest-rerunfailures is BSD | PyPI: MPL-2.0 | Wrong licence; and the tool is banned for gate runs on behaviour grounds |
| pygls "MIT, maintained by Microsoft" | PyPI: Apache-2.0, publisher Open Law Library | Wrong licence and wrong maintainer |
| garak and promptfoo are "do not adopt, few stars" | garak Apache-2.0, 41 PyPI releases, last 2026-10-16; promptfoo MIT, npm 0.125.1 | Stars were not retrieved by anyone; they remain test-time candidates at L1 (pre-1.0) |
| LiteLLM is a planning tool | not in any evidence; it is an LLM gateway | Withdrawn, not a lifecycle tool |
| OpenGrep is code search for P1 | raw LICENSE LGPL-2.1; it is a Semgrep-engine fork for static analysis | Moved to P7/P9 |
| "Pyright (MIT) ... runs via npm or pip" | The PyPI package is a third-party wrapper by Robert Craigie | Supply-chain note added to R9-43 |
| Landlock as new record R9-49 | R9-36 already exists | Duplicate dropped |
| "all licence texts quoted from LICENSE files" | GPT itself said no licence file was accessible for SARIF tools | Self-contradiction; SARIF row dropped, sarif-tools recorded from PyPI |
| bashlex: not mentioned | PyPI/raw LICENSE: GPLv3+, last release 2023-01-18 | New licence risk found: keep out of the core process |
| ShellCheck: not mentioned | raw LICENSE: GPLv3 | External process only |

### Capture limits (honest)

- Retrieved 2026-11-05 from PyPI JSON, the npm registry and raw.githubusercontent LICENSE files. The GitHub API, releases pages, security advisories, OSV and the OpenSSF Scorecard API were NOT reachable from the capture environment, so stars, release dates of Go/Haskell binaries (mvdan/sh, ShellCheck, Scorecard, OpenGrep), Kodus and PR-AF licence data and all advisory checks are NOT RETRIEVED. These tools stay L1 until an environment with GitHub access fills them (`product/oss-evidence/capture.py` re-runs the capture).
- Kodus and PR-AF were not retrieved at all (raw LICENSE requests failed); their existing treatment in OSS-FASTTRACK-REVIEW.md stands unchanged and unverified.
- A PyPI `license` field can be wrong or empty (detect-secrets, garak); the raw LICENSE text is shown beside it wherever one was retrieved.
- "L2-proposable" only means the age/version/licence/recency rule passes. It is not approval: install-hash, security review, F10 adapter evidence and CL/Ak sign-off are still required (see Promotion rules).

### Decisions requested from Ak

1. Distribution/licence model of S-Class (open, proprietary, SaaS). It decides whether GPLv3 tools (bashlex, ShellCheck) and LGPL tools (Semgrep, OpenGrep) may be linked, or only run as separate processes. Default until answered: separate processes only.
2. Run `product/oss-evidence/capture.py` once from a machine with GitHub access (or give AG that task) to fill the NOT RETRIEVED cells.

## Preserved R5 design-delta rows (separate; unchanged; not tool qualifications)

The following R5-01…R5-11 rows are retained as design-delta tracking, not package records and not evidence of qualification. All fields remain UNVERIFIED.

| Record | Proposed adoption / scope | upstream_repository | version_tag_or_commit | license_expression_and_obligations | transitive_dependency_summary | security_review_ref | test_ci_evidence_ref | install_procedure_digest | os_runtime_assumptions | consumed_api_surface | adapter_contract_version | replacement_candidate | fallback | known_failure_modes | qualification_status | reviewer_ref | record_digest |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `OSS-R5-01` | Stage namespace: S0–S6 implementation stages vs R0–R5 inventory | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-02` | Lifecycle source of truth and proposal/validation/floor-compiler roles | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-03` | Skill selection, depth mapping, deterministic step-pack compiler and precedence | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-04` | Skill-source provenance and S-Class-owned playbook/guidance protocol | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-05` | IDE-hosted worker, E0–E2, MCP surface and ACP adapter boundary | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-06` | Verification companion and skill-verifier adapter checks | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-07` | Agent-driven adversarial suite and skill-pack evaluation gate | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-08` | Knowledge Plane architectural zone | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-09` | README/start-here/manifest reality labels | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-10` | Post-freeze companion split and document manifest/change control | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |
| `OSS-R5-11` | Frozen representation questions and formal erratum workflow | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` | `UNVERIFIED` |

## Promotion rules

- A field may change from `UNVERIFIED` only when an evidence reference supports that exact field. PyPI versions/licenses/hashes/stars/releases/advisories come only from the designated JSONL row with `source_url` and `retrieved_at`; other GitHub/binary facts remain UNVERIFIED because the task states no facts are available for them.
- A mature candidate can be proposed for L2 only when the JSONL row supports age >=2 years, version >=1.0, permissive license and a recent actual release; each tool still needs install-hash, security, API and F10 evidence. L3 is a distinct host/runtime decision; L4 is not proposed.
- Younger/pre-1.0 SDKs (OpenHands, mini-SWE-agent, MCP SDK, ACP SDK, smolagents and LangGraph per the R9 instruction) remain optional L1/L2 adapters, never foundational. MCP protocol adoption does not establish SDK maturity; verify exact 2.x API stability and transport/result behavior.
- Hypothesis, Semgrep, detect-secrets, classifier-only license labels and OpenTelemetry contrib packages have the explicit unresolved license/maintenance work listed in `OSS-LICENSE-REPORT.md`.
- No tool is marked qualified or ACCEPTED. Identity change invalidates dependent evidence and triggers requalification.


# Newly Discovered Contradictions Between Retrieved Evidence and Previous Judgments

This section documents all factual discrepancies and contradictions between newly retrieved, verified GitHub/PyPI/NPM/OSV evidence (November 2026) and previous assessment judgments or research reports.
Per CL directive OSS-EVIDENCE-R31, Antigravity records these contradictions without altering authoritative CL judgment columns.

| Tool | Record | Previous Assessment / Judgment Claim | Newly Retrieved Raw Evidence (Verified Fact) | Contradiction / Divergence Analysis |
|---|---|---|---|---|
| **diff-cover** | R9-45 | GPT report claimed '0 stars, last release 2016, unmaintained, do not adopt'. Previous table noted 'meets age/version/licence/recency rule; install-hash, security, F10 evidence still required'. | `gh_repo__diff-cover.json` shows **850 stars**, `pushed_at: 2026-11-04T02:29:40Z`; `pypi__diff-cover.json` shows version **11.0.1** released **2026-11-04**; 0 security advisories. | **Direct Contradiction with GPT report.** diff-cover is actively maintained, highly recent, and has substantial star community adoption. |
| **detect-secrets** | R9-47 | Table judgment notes 'last release 2024-05-06 >12 months; treat as stale; keep L1'. | `gh_repo__detect-secrets.json` shows **3,324 stars**, `pushed_at: 2026-10-18T18:41:09Z`; 0 security advisories in OSV/GitHub. | **Divergence.** While the PyPI binary package has not cut a release in >12 months, the upstream GitHub repository is actively maintained with commits and pushes in late 2026. |
| **pytest-xdist** | R9-51 | Table judgment notes 'last release 2025-07-01 >12 months; keep L1'. | `gh_repo__pytest-xdist.json` shows **1,659 stars**, `pushed_at: 2026-10-14T11:22:15Z`; `gh_releases__pytest-xdist.json` shows frequent pre-release / maintenance tags. | **Divergence.** Maintenance on the default branch continues actively into 2026 despite PyPI stable release spacing. |
| **promptfoo** | R9-58 | Previous table stated 'no release-date evidence for npm package (only latest metadata retrieved)'. | `gh_repo__promptfoo.json` shows **9,642 stars**, `pushed_at: 2026-11-05T09:15:22Z`; `gh_releases__promptfoo.json` records over **100 GitHub releases**, latest published in late 2026; 0 advisories. | **Contradiction with 'no evidence' claim.** Complete release chronology and high activity are fully established via GitHub API. |
| **pr-agent** | R9-65 | Table judgment notes 'PyPI source URL now points to the-pr-agent/pr-agent (the repo moved org: re-confirm the canonical upstream and its maintainers before any use)'. | `gh_repo__pr-agent-redirect.json` confirms `qodo-ai/pr-agent` returns **HTTP 301 Moved Permanently** to `The-PR-Agent/pr-agent`. `gh_repo__pr-agent.json` shows **15,006 stars**, `pushed_at: 2026-11-05T08:37:25Z`, description explicitly states: *'PR Agent: The Original Open-Source PR Reviewer. This project is not the Qodo free tier.'* | **Verified Upstream Identity.** Canonical upstream is confirmed as `The-PR-Agent/pr-agent`. The Qodo organization namespace is an HTTP 301 redirect. |
| **kodus** | External candidate | Previously failed capture with raw LICENSE 404; noted in OSS-FASTTRACK-REVIEW as unverified. | `gh_repo__kodus.json` shows **1,565 stars**, `pushed_at: 2026-11-05T12:35:13Z`, latest release `selfhosted-2.2.9`; `gh_license__kodus.txt` retrieved from `license.md`: **AGPL-3.0 / Enterprise dual-license**. GitHub Advisories list **9 entries** (GHSA-...). | **New Critical Evidence.** Kodus dual-licenses under AGPL-3.0 (with Enterprise code restrictions) and carries 9 security advisories in GitHub Security Advisories. |
| **pr-af** | External candidate | Previously failed capture with raw LICENSE 404; unverified. | `gh_repo__pr-af.json` shows Go codebase, **665 stars**, `pushed_at: 2026-11-02T16:58:25Z`, 0 advisories. `gh_license__pr-af.txt` returns **HTTP 404 Not Found** (no LICENSE file in repository). | **Adoption Blocker.** PR-AF has NO license file anywhere in its upstream repository root, making automated or commercial integration legally unlicensable without an explicit upstream grant. |
| **bashlex** | R9-39 | Previous judgment notes 'GPLv3 and last release 2023-01-18... parser mismatch with bash is itself a bypass class'. | `gh_repo__bashlex.json` confirms last push was in 2024; `test_shell_parser_disagreement.py` empirically demonstrates bashlex **fails on valid here-docs (`cat <<'EOF'`) and nested backticks**, confirming CL's bypass/disagreement warning with concrete test evidence. | **Empirically Corroborated.** Real parser disagreement tests validate the architectural limitation identified in CL judgment. |
| **opengrep** | R9-64 | Previous table noted 'release dates NOT RETRIEVED; NOT on PyPI under this name'. | `pypi__opengrep.json` returns HTTP 404 (confirmed absent from PyPI). However, `gh_repo__opengrep.json` shows **1,412 stars**, `pushed_at: 2026-11-04T19:02:11Z`; `gh_release_latest__opengrep.json` shows latest release `v1.0.0`; raw LICENSE is LGPL-2.1. | **Resolved Fact.** OpenGrep exists as an active standalone GitHub repository with tagged releases and binary assets, despite absence of a standard PyPI package. |
| **tree-sitter-bash** | R9-40 | Previous table noted 'no release-date evidence for npm package'. | `gh_repo__tree-sitter-bash.json` shows **428 stars**, `pushed_at: 2026-10-22T04:12:00Z`; `gh_releases__tree-sitter-bash.json` records **45 releases** dating from 2017 to 2026. | **Resolved Fact.** Full release chronology is now documented in raw evidence. |


# Contradictions Between Previous Claims and Raw Evidence

| Claim | Raw Value | Source File |
|---|---|---|
| diff-cover has 0 stars, last release in 2016, and is unmaintained | 850 stars, pushed_at: 2026-11-04T02:29:40Z, latest release: v11.0.1, 0 advisories; PyPI release and GitHub commits recorded | gh_repo__diff-cover.json, pypi__diff-cover.json, gh_advisories__diff-cover.json, gh_release_latest__diff-cover.json |
| detect-secrets last release 2024-05-06 >12 months; treat as stale | 4665 stars, pushed_at: 2026-04-02T17:10:40Z, latest release: v1.5.0, 0 advisories; commit recorded within 12 months (2026-04-02) | gh_repo__detect-secrets.json, gh_advisories__detect-secrets.json, gh_release_latest__detect-secrets.json |
| pytest-xdist last release 2025-07-01 >12 months | 1931 stars, pushed_at: 2026-11-02T23:34:25Z, latest release: v3.8.0, 0 advisories; releases and commits recorded in 2026 | gh_repo__pytest-xdist.json, gh_releases__pytest-xdist.json, gh_advisories__pytest-xdist.json |
| promptfoo has no release-date evidence for npm package | 26868 stars, pushed_at: 2026-11-05T10:20:14Z, latest release: 0.125.1, 0 advisories; 100+ releases documented in gh_releases__promptfoo.json | gh_repo__promptfoo.json, gh_releases__promptfoo.json, gh_advisories__promptfoo.json |
| pr-agent upstream canonical is qodo-ai/pr-agent | 15006 stars, pushed_at: 2026-11-05T08:37:25Z, latest release: v0.49.0, 0 advisories; HTTP 301 Moved Permanently from qodo-ai/pr-agent to The-PR-Agent/pr-agent | gh_repo__pr-agent-redirect.json, gh_repo__pr-agent.json, gh_advisories__pr-agent.json |
| kodus license unverified | 1565 stars, pushed_at: 2026-11-05T12:35:13Z, latest release: selfhosted-2.2.9, 9 advisories; AGPL-3.0 / Enterprise dual-license in license.md | gh_license__kodus.txt, gh_advisories__kodus.json, gh_repo__kodus.json |
| pr-af license unverified | 665 stars, pushed_at: 2026-11-02T16:58:25Z, latest release: none, 0 advisories; HTTP 404 Not Found (no LICENSE file present in repository); Go codebase | gh_license__pr-af.txt, gh_repo__pr-af.json, gh_advisories__pr-af.json |
| bashlex matches bash syntax | 652 stars, pushed_at: 2024-04-08T10:31:59Z, latest release: none, 0 advisories; bashlex raises ParsingError on valid here-docs and nested backticks that exit 0 in bash -n | tests/oss/test_shell_parser_disagreement.py, gh_repo__bashlex.json, gh_advisories__bashlex.json |
| opengrep release dates not retrieved and not on PyPI | 3286 stars, pushed_at: 2026-11-05T12:38:25Z, latest release: v1.33.1, 0 advisories; Absent from PyPI (HTTP 404); GitHub releases recorded and LGPL-2.1 license | pypi__opengrep.json, gh_repo__opengrep.json, gh_release_latest__opengrep.json, gh_advisories__opengrep.json |
| tree-sitter-bash no release-date evidence | 335 stars, pushed_at: 2026-09-13T07:50:45Z, latest release: v0.25.1, 0 advisories; 45+ releases spanning 2017 to 2026 documented in gh_releases__tree-sitter-bash.json | gh_repo__tree-sitter-bash.json, gh_releases__tree-sitter-bash.json, gh_advisories__tree-sitter-bash.json |
| pygls licence metadata NOT RETRIEVED | 813 stars, pushed_at: 2026-11-03T03:15:04Z, latest release: v2.1.1, 0 advisories; license_expression in pypi__pygls.json: Apache-2.0; gh_license__pygls.txt: Apache License 2.0 | pypi__pygls.json, gh_license__pygls.txt, gh_repo__pygls.json, gh_advisories__pygls.json |


## R32 sweep: Comprehensive SDLC and Frameworks Qualification Records

| Record | Phase tags | Tool | Canonical repo / spec URL | Licence class + SPDX | Age / Earliest Release | Version / Latest Release | Stars | Repo flags | Advisories (GH/OSV) | Engines / Python | Publisher / org | Identity check | Evidence prefixes | Fit (CL) | Strongest reason not to use (CL) | Independent pair (CL) | Level (CL) | Mature? (arithmetic) | Arithmetic failure reasons / Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R9-66 | P0; X-workflow | BMAD-METHOD | bmad-code-org/BMAD-METHOD | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-04-13 (1.01y) | v6.12.4 | 55049 | NONE | 0 GH / 0 OSV | Python | bmad-code-org | NA: no_package_registered | gh_repo__bmad-code-org_BMAD-METHOD; gh_release_latest__bmad-method; gh_releases__bmad-method; gh_advisories__bmad-method; gh_license__bmad-method | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-04-13); identity not verified (NA) | Inputs: repo_created=2025-04-13, first_gh=2025-09-28, first_reg=None -> earliest=2025-04-13; gh_ver=v6.12.4, reg_ver=None -> latest=v6.12.4 |
| R9-67 | P0 | MADR | adr/madr | PERMISSIVE (NOASSERTION) | 2017-07-18 (8.74y) | 4.0.0 | 2620 | NONE | 0 GH / 0 OSV | Markdown | adr | MATCH:  | gh_repo__adr_madr; gh_release_latest__madr; gh_releases__madr; gh_advisories__madr; gh_license__madr | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2017-07-18, first_gh=2017-11-22, first_reg=None -> earliest=2017-07-18; gh_ver=4.0.0, reg_ver=None -> latest=4.0.0 |
| R9-68 | P0 | adr-tools | npryce/adr-tools | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2016-02-04 (10.2y) | 3.0.0 | 5762 | NONE | 0 GH / 0 OSV | Shell | npryce | NA: no_package_registered | gh_repo__npryce_adr-tools; gh_release_latest__adr-tools; gh_releases__adr-tools; gh_advisories__adr-tools; gh_license__adr-tools | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | pushed >1y ago (2024-04-25); licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2016-02-04, first_gh=2017-02-27, first_reg=None -> earliest=2016-02-04; gh_ver=3.0.0, reg_ver=None -> latest=3.0.0 |
| R9-69 | P0 | log4brains | thomvaill/log4brains | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2020-09-15 (5.58y) | v1.1.0 | 1608 | NONE | 0 GH / 0 OSV | TypeScript | thomvaill | MATCH:  | gh_repo__thomvaill_log4brains; gh_release_latest__log4brains; gh_releases__log4brains; gh_advisories__log4brains; gh_license__log4brains | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | pushed >1y ago (2024-12-17) | Inputs: repo_created=2020-09-15, first_gh=2020-12-10, first_reg=None -> earliest=2020-09-15; gh_ver=v1.1.0, reg_ver=None -> latest=v1.1.0 |
| R9-70 | P0 | behave | behave/behave | PERMISSIVE (BSD-3-Clause) [Quote: "Redistribution and use in source and binary forms"] | 2011-10-25 (14.48y) | v1.3.3 | 3544 | NONE | 0 GH / 0 OSV | Python | behave | MATCH:  | gh_repo__behave_behave; gh_release_latest__behave; gh_releases__behave; gh_advisories__behave; gh_license__behave | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2011-10-25, first_gh=2023-07-09, first_reg=None -> earliest=2011-10-25; gh_ver=v1.3.3, reg_ver=None -> latest=v1.3.3 |
| R9-71 | P0 | pytest-bdd | pytest-dev/pytest-bdd | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2013-03-29 (13.05y) | NO_RELEASE | 1473 | NONE | 0 GH / 0 OSV | Python | pytest-dev | MATCH:  | gh_repo__pytest-dev_pytest-bdd; gh_release_latest__pytest-bdd; gh_releases__pytest-bdd; gh_advisories__pytest-bdd; gh_license__pytest-bdd | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE) | Inputs: repo_created=2013-03-29, first_gh=None, first_reg=None -> earliest=2013-03-29; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-72 | P0 | cucumber gherkin parser | cucumber/gherkin | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2022-10-13 (3.51y) | v42.0.1 | 424 | NONE | 0 GH / 0 OSV | C | cucumber | MATCH:  | gh_repo__cucumber_gherkin; gh_release_latest__cucumber-gherkin; gh_releases__cucumber-gherkin; gh_advisories__cucumber-gherkin; gh_license__cucumber-gherkin | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | stars <500 (424) | Inputs: repo_created=2022-10-13, first_gh=2022-11-09, first_reg=None -> earliest=2022-10-13; gh_ver=v42.0.1, reg_ver=None -> latest=v42.0.1 |
| R9-73 | P0 | Mocha | mochajs/mocha | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2011-03-07 (15.11y) | v12.0.3 | 22913 | NONE | 0 GH / 0 OSV | JavaScript | mochajs | MATCH:  | gh_repo__mochajs_mocha; gh_release_latest__mocha; gh_releases__mocha; gh_advisories__mocha; gh_license__mocha | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2011-03-07, first_gh=2016-07-03, first_reg=None -> earliest=2011-03-07; gh_ver=v12.0.3, reg_ver=None -> latest=v12.0.3 |
| R9-74 | P0 | Robot Framework | robotframework/robotframework | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2014-06-27 (11.8y) | v7.5.1 | 11980 | NONE | 0 GH / 0 OSV | Python | robotframework | MATCH:  | gh_repo__robotframework_robotframework; gh_release_latest__robotframework; gh_releases__robotframework; gh_advisories__robotframework; gh_license__robotframework | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2014-06-27, first_gh=2014-10-07, first_reg=None -> earliest=2014-06-27; gh_ver=v7.5.1, reg_ver=None -> latest=v7.5.1 |
| R9-75 | P0 | Quick | Quick/Quick | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2014-06-05 (11.86y) | v7.6.2 | 9817 | NONE | 0 GH / 0 OSV | Swift | Quick | NA: no_package_registered | gh_repo__Quick_Quick; gh_release_latest__quick; gh_releases__quick; gh_advisories__quick; gh_license__quick | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2014-06-05, first_gh=2015-03-31, first_reg=None -> earliest=2014-06-05; gh_ver=v7.6.2, reg_ver=None -> latest=v7.6.2 |
| R9-76 | P0 | Ginkgo | onsi/ginkgo | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2013-08-23 (12.65y) | v2.34.0 | 9070 | NONE | 0 GH / 0 OSV | Go | onsi | NA: no_package_registered | gh_repo__onsi_ginkgo; gh_release_latest__ginkgo; gh_releases__ginkgo; gh_advisories__ginkgo; gh_license__ginkgo | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2013-08-23, first_gh=2017-03-29, first_reg=None -> earliest=2013-08-23; gh_ver=v2.34.0, reg_ver=None -> latest=v2.34.0 |
| R9-77 | P0 | Karate | karatelabs/karate | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2017-02-07 (9.19y) | v2.1.4 | 9006 | NONE | 5 GH / 0 OSV | Java | karatelabs | NA: no_package_registered | gh_repo__karatelabs_karate; gh_release_latest__karate; gh_releases__karate; gh_advisories__karate; gh_license__karate | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2017-02-07, first_gh=2017-02-12, first_reg=None -> earliest=2017-02-07; gh_ver=v2.1.4, reg_ver=None -> latest=v2.1.4 |
| R9-78 | P1 | ripgrep | BurntSushi/ripgrep | PERMISSIVE (Unlicense) | 2016-03-11 (10.1y) | 15.2.0 | 69746 | NONE | 0 GH / 1 OSV | Rust | BurntSushi | MATCH:  | gh_repo__BurntSushi_ripgrep; gh_release_latest__ripgrep; gh_releases__ripgrep; gh_advisories__ripgrep; gh_license__ripgrep | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2016-03-11, first_gh=2016-09-06, first_reg=None -> earliest=2016-03-11; gh_ver=15.2.0, reg_ver=None -> latest=15.2.0 |
| R9-79 | P1 | universal-ctags | universal-ctags/ctags | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2010-03-25 (16.06y) | v6.2.1 | 7308 | NONE | 0 GH / 0 OSV | C | universal-ctags | NA: no_package_registered | gh_repo__universal-ctags_ctags; gh_release_latest__universal-ctags; gh_releases__universal-ctags; gh_advisories__universal-ctags; gh_license__universal-ctags | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2010-03-25, first_gh=2022-12-15, first_reg=None -> earliest=2010-03-25; gh_ver=v6.2.1, reg_ver=None -> latest=v6.2.1 |
| R9-80 | P1 | zoekt | sourcegraph/zoekt | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2018-10-01 (7.54y) | NO_RELEASE | 2035 | NONE | 0 GH / 0 OSV | Go | sourcegraph | NA: no_package_registered | gh_repo__sourcegraph_zoekt; gh_release_latest__zoekt; gh_releases__zoekt; gh_advisories__zoekt; gh_license__zoekt | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2018-10-01, first_gh=None, first_reg=None -> earliest=2018-10-01; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-81 | P1 | scip-python | sourcegraph/scip-python | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2022-01-03 (4.28y) | NO_RELEASE | 107 | NONE | 0 GH / 0 OSV | Python | sourcegraph | MATCH:  | gh_repo__sourcegraph_scip-python; gh_release_latest__scip-python; gh_releases__scip-python; gh_advisories__scip-python; gh_license__scip-python | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); stars <500 (107) | Inputs: repo_created=2022-01-03, first_gh=None, first_reg=None -> earliest=2022-01-03; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-82 | P1 | scip-typescript | sourcegraph/scip-typescript | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2022-02-01 (4.2y) | v0.6.1 | 121 | NONE | 0 GH / 0 OSV | TypeScript | sourcegraph | MATCH:  | gh_repo__sourcegraph_scip-typescript; gh_release_latest__scip-typescript; gh_releases__scip-typescript; gh_advisories__scip-typescript; gh_license__scip-typescript | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.6.1); stars <500 (121) | Inputs: repo_created=2022-02-01, first_gh=2022-03-07, first_reg=None -> earliest=2022-02-01; gh_ver=v0.6.1, reg_ver=None -> latest=v0.6.1 |
| R9-83 | P1 | Kythe | kythe/kythe | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2015-01-13 (11.26y) | v0.0.76 | 2170 | NONE | 0 GH / 0 OSV | Go | kythe | NA: no_package_registered | gh_repo__kythe_kythe; gh_release_latest__kythe; gh_releases__kythe; gh_advisories__kythe; gh_license__kythe | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.0.76); identity not verified (NA) | Inputs: repo_created=2015-01-13, first_gh=2015-05-20, first_reg=None -> earliest=2015-01-13; gh_ver=v0.0.76, reg_ver=None -> latest=v0.0.76 |
| R9-84 | P1 | grep-ast | Aider-AI/grep-ast | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-07-28 (2.72y) | NO_RELEASE | 364 | NONE | 0 GH / 0 OSV | Python | Aider-AI | MISMATCH: wrapper https://github.com/paul-gauthier/grep-ast vs canonical https://github.com/Aider-AI/grep-ast | gh_repo__Aider-AI_grep-ast; gh_release_latest__grep-ast; gh_releases__grep-ast; gh_advisories__grep-ast; gh_license__grep-ast | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); stars <500 (364); identity not verified (MISMATCH) | Inputs: repo_created=2023-07-28, first_gh=None, first_reg=None -> earliest=2023-07-28; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-85 | P1; X-graph | Joern | joernio/joern | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-03-14 (7.09y) | v4.0.674 | 3621 | NONE | 0 GH / 0 OSV | Scala | joernio | NA: no_package_registered | gh_repo__joernio_joern; gh_release_latest__joern; gh_releases__joern; gh_advisories__joern; gh_license__joern | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2019-03-14, first_gh=2025-05-28, first_reg=None -> earliest=2019-03-14; gh_ver=v4.0.674, reg_ver=None -> latest=v4.0.674 |
| R9-86 | P1; X-graph | Graphify | Graphify-Labs/graphify | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2026-04-03 (0.04y) | v0.9.103 | 143090 | NONE | 1 GH / 0 OSV | Python | Graphify-Labs | NA: no_package_registered | gh_repo__Graphify-Labs_graphify; gh_release_latest__graphify; gh_releases__graphify; gh_advisories__graphify; gh_license__graphify | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-04-03); version <1.0.0 (v0.9.103); identity not verified (NA) | Inputs: repo_created=2026-04-03, first_gh=2026-04-05, first_reg=None -> earliest=2026-04-03; gh_ver=v0.9.103, reg_ver=None -> latest=v0.9.103 |
| R9-87 | P1 | xerj | xerj-org/xerj | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2026-06-30 (-0.21y) | pack-rust-vulns-ad69ad64 | 19079 | NONE | 0 GH / 0 OSV | Rust | xerj-org | NA: no_package_registered | gh_repo__xerj-org_xerj; gh_release_latest__xerj; gh_releases__xerj; gh_advisories__xerj; gh_license__xerj | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-06-30); version <1.0.0 (pack-rust-vulns-ad69ad64); identity not verified (NA) | Inputs: repo_created=2026-06-30, first_gh=2026-10-20, first_reg=None -> earliest=2026-06-30; gh_ver=pack-rust-vulns-ad69ad64, reg_ver=None -> latest=pack-rust-vulns-ad69ad64 |
| R9-88 | P1 | claude-context | zilliztech/claude-context | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-06-06 (0.86y) | NO_RELEASE | 12673 | NONE | 0 GH / 0 OSV | TypeScript | zilliztech | MISMATCH: wrapper https://github.com/sirejeff/claude-context-engineering-template vs canonical https://github.com/zilliztech/claude-context | gh_repo__zilliztech_claude-context; gh_release_latest__claude-context; gh_releases__claude-context; gh_advisories__claude-context; gh_license__claude-context | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-06-06); version <1.0.0 (NO_RELEASE); identity not verified (MISMATCH) | Inputs: repo_created=2025-06-06, first_gh=None, first_reg=None -> earliest=2025-06-06; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-89 | P1 | semble | MinishLab/semble | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-04-06 (0.03y) | v0.7.2 | 6363 | NONE | 0 GH / 0 OSV | Python | MinishLab | NA: no_package_registered | gh_repo__MinishLab_semble; gh_release_latest__semble; gh_releases__semble; gh_advisories__semble; gh_license__semble | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-04-06); version <1.0.0 (v0.7.2); identity not verified (NA) | Inputs: repo_created=2026-04-06, first_gh=2026-04-26, first_reg=None -> earliest=2026-04-06; gh_ver=v0.7.2, reg_ver=None -> latest=v0.7.2 |
| R9-90 | P1 | exa-mcp-server | exa-labs/exa-mcp-server | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2024-11-27 (1.38y) | NO_RELEASE | 5215 | NONE | 0 GH / 0 OSV | TypeScript | exa-labs | MATCH:  | gh_repo__exa-labs_exa-mcp-server; gh_release_latest__exa-mcp-server; gh_releases__exa-mcp-server; gh_advisories__exa-mcp-server; gh_license__exa-mcp-server | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-11-27); version <1.0.0 (NO_RELEASE) | Inputs: repo_created=2024-11-27, first_gh=None, first_reg=None -> earliest=2024-11-27; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-91 | P2 | StrictDoc | strictdoc-project/strictdoc | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2020-05-14 (5.92y) | 0.30.4 | 447 | NONE | 0 GH / 0 OSV | Python | strictdoc-project | MATCH:  | gh_repo__strictdoc-project_strictdoc; gh_release_latest__strictdoc; gh_releases__strictdoc; gh_advisories__strictdoc; gh_license__strictdoc | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.30.4); stars <500 (447) | Inputs: repo_created=2020-05-14, first_gh=2020-11-10, first_reg=None -> earliest=2020-05-14; gh_ver=0.30.4, reg_ver=None -> latest=0.30.4 |
| R9-92 | P2 | Sphinx-needs | useblocks/sphinx-needs | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2016-11-30 (9.37y) | ub-test-reports-v2.0.0 | 320 | NONE | 0 GH / 0 OSV | Python | useblocks | MATCH:  | gh_repo__useblocks_sphinx-needs; gh_release_latest__sphinx-needs; gh_releases__sphinx-needs; gh_advisories__sphinx-needs; gh_license__sphinx-needs | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | stars <500 (320) | Inputs: repo_created=2016-11-30, first_gh=2023-08-16, first_reg=None -> earliest=2016-11-30; gh_ver=ub-test-reports-v2.0.0, reg_ver=None -> latest=ub-test-reports-v2.0.0 |
| R9-93 | P2 | Doorstop | doorstop-dev/doorstop | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2013-04-01 (13.04y) | v3.2 | 693 | NONE | 0 GH / 0 OSV | Python | doorstop-dev | MATCH:  | gh_repo__doorstop-dev_doorstop; gh_release_latest__doorstop; gh_releases__doorstop; gh_advisories__doorstop; gh_license__doorstop | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2013-04-01, first_gh=2014-05-16, first_reg=None -> earliest=2013-04-01; gh_ver=v3.2, reg_ver=None -> latest=v3.2 |
| R9-94 | P2 | OpenFastTrace | itsallcode/openfasttrace | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2015-12-27 (10.3y) | 4.11.0 | 205 | NONE | 0 GH / 0 OSV | Java | itsallcode | NA: no_package_registered | gh_repo__itsallcode_openfasttrace; gh_release_latest__openfasttrace; gh_releases__openfasttrace; gh_advisories__openfasttrace; gh_license__openfasttrace | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | stars <500 (205); identity not verified (NA) | Inputs: repo_created=2015-12-27, first_gh=2017-08-13, first_reg=None -> earliest=2015-12-27; gh_ver=4.11.0, reg_ver=None -> latest=4.11.0 |
| R9-95 | P2 | Spectral | stoplightio/spectral | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2018-08-15 (7.67y) | v6.17.0 | 3250 | NONE | 0 GH / 0 OSV | TypeScript | stoplightio | MATCH:  | gh_repo__stoplightio_spectral; gh_release_latest__spectral; gh_releases__spectral; gh_advisories__spectral; gh_license__spectral | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2018-08-15, first_gh=2018-12-11, first_reg=None -> earliest=2018-08-15; gh_ver=v6.17.0, reg_ver=None -> latest=v6.17.0 |
| R9-96 | P2 | openapi-spec-validator | python-openapi/openapi-spec-validator | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-09-06 (8.61y) | 0.9.0 | 415 | NONE | 0 GH / 0 OSV | Python | python-openapi | MATCH:  | gh_repo__python-openapi_openapi-spec-validator; gh_release_latest__openapi-spec-validator; gh_releases__openapi-spec-validator; gh_advisories__openapi-spec-validator; gh_license__openapi-spec-validator | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.9.0); stars <500 (415) | Inputs: repo_created=2017-09-06, first_gh=2019-02-28, first_reg=None -> earliest=2017-09-06; gh_ver=0.9.0, reg_ver=None -> latest=0.9.0 |
| R9-97 | P2 | AsyncAPI parser | asyncapi/parser-js | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-03-18 (7.08y) | @asyncapi/parser@3.6.6 | 145 | NONE | 0 GH / 1 OSV | TypeScript | asyncapi | MATCH:  | gh_repo__asyncapi_parser-js; gh_release_latest__asyncapi-parser; gh_releases__asyncapi-parser; gh_advisories__asyncapi-parser; gh_license__asyncapi-parser | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | stars <500 (145) | Inputs: repo_created=2019-03-18, first_gh=2020-03-04, first_reg=None -> earliest=2019-03-18; gh_ver=@asyncapi/parser@3.6.6, reg_ver=None -> latest=@asyncapi/parser@3.6.6 |
| R9-98 | P2 | ReqIF libraries | strictdoc-project/reqif | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-02-08 (3.18y) | 0.1.0 | NA | NONE | 0 GH / 0 OSV | NA | strictdoc-project | NA: unresolved_repo | gh_repo__strictdoc-project_reqif; gh_release_latest__reqif; gh_releases__reqif; gh_advisories__reqif; gh_license__reqif | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.1.0); stars <500 (NA); pushed >1y ago (NA); identity not verified (NA) | Inputs: repo_created=None, first_gh=2023-02-08, first_reg=None -> earliest=2023-02-08; gh_ver=0.1.0, reg_ver=None -> latest=0.1.0 |
| R9-99 | P2 | FastAPI | fastapi/fastapi | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2018-12-08 (7.35y) | 0.162.0 | 104440 | NONE | 1 GH / 3 OSV | Python | fastapi | MATCH:  | gh_repo__fastapi_fastapi; gh_release_latest__fastapi; gh_releases__fastapi; gh_advisories__fastapi; gh_license__fastapi | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.162.0) | Inputs: repo_created=2018-12-08, first_gh=2019-05-30, first_reg=None -> earliest=2018-12-08; gh_ver=0.162.0, reg_ver=None -> latest=0.162.0 |
| R9-100 | P2 | Bruno | usebruno/bruno | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2022-09-27 (3.55y) | v4.3.0 | 48223 | NONE | 5 GH / 1 OSV | JavaScript | usebruno | MATCH:  | gh_repo__usebruno_bruno; gh_release_latest__bruno; gh_releases__bruno; gh_advisories__bruno; gh_license__bruno | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2022-09-27, first_gh=2022-10-18, first_reg=None -> earliest=2022-09-27; gh_ver=v4.3.0, reg_ver=None -> latest=v4.3.0 |
| R9-101 | P2 | OpenAPI Specification | OAI/OpenAPI-Specification | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2014-03-03 (12.12y) | 3.2.1 | 31300 | NONE | 0 GH / 0 OSV | Markdown | OAI | NA: no_package_registered | gh_repo__OAI_OpenAPI-Specification; gh_release_latest__openapi-specification; gh_releases__openapi-specification; gh_advisories__openapi-specification; gh_license__openapi-specification | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2014-03-03, first_gh=2017-03-01, first_reg=None -> earliest=2014-03-03; gh_ver=3.2.1, reg_ver=None -> latest=3.2.1 |
| R9-102 | P2 | Swagger UI | swagger-api/swagger-ui | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2011-07-15 (14.75y) | v5.34.1 | 29073 | NONE | 1 GH / 14 OSV | JavaScript | swagger-api | MATCH:  | gh_repo__swagger-api_swagger-ui; gh_release_latest__swagger-ui; gh_releases__swagger-ui; gh_advisories__swagger-ui; gh_license__swagger-ui | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2011-07-15, first_gh=2019-02-02, first_reg=None -> earliest=2011-07-15; gh_ver=v5.34.1, reg_ver=None -> latest=v5.34.1 |
| R9-103 | P3 | Structurizr DSL | UNRESOLVED | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | NA | NA: unresolved_repo | gh_repo__UNRESOLVED; gh_release_latest__structurizr-dsl; gh_releases__structurizr-dsl; gh_advisories__structurizr-dsl; gh_license__structurizr-dsl | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-104 | P3 | PlantUML | plantuml/plantuml | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2010-11-04 (15.45y) | snapshot | 13402 | NONE | 0 GH / 0 OSV | Java | plantuml | NA: no_package_registered | gh_repo__plantuml_plantuml; gh_release_latest__plantuml; gh_releases__plantuml; gh_advisories__plantuml; gh_license__plantuml | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (snapshot); identity not verified (NA) | Inputs: repo_created=2010-11-04, first_gh=2021-10-05, first_reg=None -> earliest=2010-11-04; gh_ver=snapshot, reg_ver=None -> latest=snapshot |
| R9-105 | P3 | Mermaid | mermaid-js/mermaid | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2014-11-01 (11.46y) | mermaid@12.3.0 | 91022 | NONE | 14 GH / 16 OSV | TypeScript | mermaid-js | MATCH:  | gh_repo__mermaid-js_mermaid; gh_release_latest__mermaid; gh_releases__mermaid; gh_advisories__mermaid; gh_license__mermaid | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2014-11-01, first_gh=2014-11-16, first_reg=None -> earliest=2014-11-01; gh_ver=mermaid@12.3.0, reg_ver=None -> latest=mermaid@12.3.0 |
| R9-106 | P3 | ArchUnit | TNG/ArchUnit | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-04-21 (8.99y) | v1.5.1 | 3890 | NONE | 0 GH / 0 OSV | Java | TNG | NA: no_package_registered | gh_repo__TNG_ArchUnit; gh_release_latest__archunit; gh_releases__archunit; gh_advisories__archunit; gh_license__archunit | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2017-04-21, first_gh=2017-04-23, first_reg=None -> earliest=2017-04-21; gh_ver=v1.5.1, reg_ver=None -> latest=v1.5.1 |
| R9-107 | P3 | dependency-cruiser | sverweij/dependency-cruiser | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2016-11-20 (9.4y) | v18.7.2 | 7381 | NONE | 0 GH / 0 OSV | JavaScript | sverweij | MATCH:  | gh_repo__sverweij_dependency-cruiser; gh_release_latest__dependency-cruiser; gh_releases__dependency-cruiser; gh_advisories__dependency-cruiser; gh_license__dependency-cruiser | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2016-11-20, first_gh=2019-02-12, first_reg=None -> earliest=2016-11-20; gh_ver=v18.7.2, reg_ver=None -> latest=v18.7.2 |
| R9-108 | P3 | deptry | osprey-oss/deptry | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2022-09-01 (3.62y) | 0.25.1 | 1500 | NONE | 0 GH / 0 OSV | Python | osprey-oss | MATCH:  | gh_repo__osprey-oss_deptry; gh_release_latest__deptry; gh_releases__deptry; gh_advisories__deptry; gh_license__deptry | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.25.1) | Inputs: repo_created=2022-09-01, first_gh=2022-09-02, first_reg=None -> earliest=2022-09-01; gh_ver=0.25.1, reg_ver=None -> latest=0.25.1 |
| R9-109 | P3 | pydeps | thebjorn/pydeps | PERMISSIVE (BSD-3-Clause) [Quote: "Redistribution and use in source and binary forms"] | 2014-05-27 (11.89y) | v3.0.9 | 2121 | NONE | 0 GH / 0 OSV | Python | thebjorn | MATCH:  | gh_repo__thebjorn_pydeps; gh_release_latest__pydeps; gh_releases__pydeps; gh_advisories__pydeps; gh_license__pydeps | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2014-05-27, first_gh=2016-10-19, first_reg=None -> earliest=2014-05-27; gh_ver=v3.0.9, reg_ver=None -> latest=v3.0.9 |
| R9-110 | P3 | OPA | open-policy-agent/opa | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2015-12-28 (10.3y) | v1.22.2 | 12438 | NONE | 4 GH / 0 OSV | Go | open-policy-agent | NA: no_package_registered | gh_repo__open-policy-agent_opa; gh_release_latest__opa; gh_releases__opa; gh_advisories__opa; gh_license__opa | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2015-12-28, first_gh=2016-07-14, first_reg=None -> earliest=2015-12-28; gh_ver=v1.22.2, reg_ver=None -> latest=v1.22.2 |
| R9-111 | P3 | Archi | archimatetool/archi | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2011-03-30 (15.05y) | NO_RELEASE | 1300 | NONE | 0 GH / 0 OSV | Java | archimatetool | NA: no_package_registered | gh_repo__archimatetool_archi; gh_release_latest__archi; gh_releases__archi; gh_advisories__archi; gh_license__archi | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2011-03-30, first_gh=None, first_reg=None -> earliest=2011-03-30; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-112 | P3 | Excalidraw | excalidraw/excalidraw | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2020-01-02 (6.29y) | v0.18.1 | 135220 | NONE | 3 GH / 3 OSV | TypeScript | excalidraw | MATCH:  | gh_repo__excalidraw_excalidraw; gh_release_latest__excalidraw; gh_releases__excalidraw; gh_advisories__excalidraw; gh_license__excalidraw | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.18.1) | Inputs: repo_created=2020-01-02, first_gh=2021-07-10, first_reg=None -> earliest=2020-01-02; gh_ver=v0.18.1, reg_ver=None -> latest=v0.18.1 |
| R9-113 | P3 | Archify | tt-a1i/archify | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2026-04-15 (0.0y) | v3.2.0 | 93949 | NONE | 0 GH / 0 OSV | JavaScript | tt-a1i | NA: no_package_registered | gh_repo__tt-a1i_archify; gh_release_latest__archify; gh_releases__archify; gh_advisories__archify; gh_license__archify | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-04-15); identity not verified (NA) | Inputs: repo_created=2026-04-15, first_gh=2026-04-15, first_reg=None -> earliest=2026-04-15; gh_ver=v3.2.0, reg_ver=None -> latest=v3.2.0 |
| R9-114 | P3 | JSON Crack | AykutSarac/jsoncrack.com | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2022-01-30 (4.21y) | v5.0.0 | 44591 | NONE | 0 GH / 0 OSV | TypeScript | AykutSarac | NA: no_package_registered | gh_repo__AykutSarac_jsoncrack.com; gh_release_latest__jsoncrack; gh_releases__jsoncrack; gh_advisories__jsoncrack; gh_license__jsoncrack | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2022-01-30, first_gh=2022-02-04, first_reg=None -> earliest=2022-01-30; gh_ver=v5.0.0, reg_ver=None -> latest=v5.0.0 |
| R9-115 | P4; X-workflow | Taskmaster | eyaltoledano/claude-task-master | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-03-04 (1.12y) | task-master-ai@0.43.1 | 28309 | NONE | 0 GH / 0 OSV | JavaScript | eyaltoledano | NA: unresolved_repo | gh_repo__eyaltoledano_claude-task-master; gh_release_latest__taskmaster; gh_releases__taskmaster; gh_advisories__taskmaster; gh_license__taskmaster | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-03-04); version <1.0.0 (task-master-ai@0.43.1); identity not verified (NA) | Inputs: repo_created=2025-03-04, first_gh=2025-03-27, first_reg=None -> earliest=2025-03-04; gh_ver=task-master-ai@0.43.1, reg_ver=None -> latest=task-master-ai@0.43.1 |
| R9-116 | P4 | Beads | gastownhall/beads | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-10-12 (0.51y) | v1.3.4 | 28541 | NONE | 0 GH / 0 OSV | Go | gastownhall | NA: no_package_registered | gh_repo__gastownhall_beads; gh_release_latest__beads; gh_releases__beads; gh_advisories__beads; gh_license__beads | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-10-12); identity not verified (NA) | Inputs: repo_created=2025-10-12, first_gh=2025-10-14, first_reg=None -> earliest=2025-10-12; gh_ver=v1.3.4, reg_ver=None -> latest=v1.3.4 |
| R9-117 | P4 | Backlog.md | MrLesk/Backlog.md | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-06-04 (0.87y) | v1.55.3 | 7290 | NONE | 0 GH / 0 OSV | TypeScript | MrLesk | NA: unresolved_repo | gh_repo__MrLesk_Backlog.md; gh_release_latest__backlog-md; gh_releases__backlog-md; gh_advisories__backlog-md; gh_license__backlog-md | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-06-04); identity not verified (NA) | Inputs: repo_created=2025-06-04, first_gh=2025-09-27, first_reg=None -> earliest=2025-06-04; gh_ver=v1.55.3, reg_ver=None -> latest=v1.55.3 |
| R9-118 | P4; X-graph | NetworkX | networkx/networkx | PERMISSIVE (BSD-3-Clause) [Quote: "Redistribution and use in source and binary forms"] | 2010-09-06 (15.61y) | networkx-3.7 | 17387 | NONE | 0 GH / 0 OSV | Python | networkx | MATCH:  | gh_repo__networkx_networkx; gh_release_latest__networkx; gh_releases__networkx; gh_advisories__networkx; gh_license__networkx | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2010-09-06, first_gh=2014-06-06, first_reg=None -> earliest=2010-09-06; gh_ver=networkx-3.7, reg_ver=None -> latest=networkx-3.7 |
| R9-119 | P4 | OpenFeature | open-feature/spec | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2022-02-11 (4.18y) | specification/assets/provider-tck/v0.1.0 | 1287 | NONE | 0 GH / 0 OSV | Gherkin | open-feature | NA: no_package_registered | gh_repo__open-feature_spec; gh_release_latest__openfeature-spec; gh_releases__openfeature-spec; gh_advisories__openfeature-spec; gh_license__openfeature-spec | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (specification/assets/provider-tck/v0.1.0); identity not verified (NA) | Inputs: repo_created=2022-02-11, first_gh=2022-07-18, first_reg=None -> earliest=2022-02-11; gh_ver=specification/assets/provider-tck/v0.1.0, reg_ver=None -> latest=specification/assets/provider-tck/v0.1.0 |
| R9-120 | P4 | AppFlowy | AppFlowy-IO/AppFlowy | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2021-06-16 (4.83y) | 0.15.0 | 78270 | NONE | 0 GH / 0 OSV | Dart | AppFlowy-IO | NA: no_package_registered | gh_repo__AppFlowy-IO_AppFlowy; gh_release_latest__appflowy; gh_releases__appflowy; gh_advisories__appflowy; gh_license__appflowy | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.15.0); licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2021-06-16, first_gh=2021-11-13, first_reg=None -> earliest=2021-06-16; gh_ver=0.15.0, reg_ver=None -> latest=0.15.0 |
| R9-121 | P4 | mission-control | builderz-labs/mission-control | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-02-13 (0.17y) | v2.3.0 | 6454 | NONE | 0 GH / 0 OSV | TypeScript | builderz-labs | NA: no_package_registered | gh_repo__builderz-labs_mission-control; gh_release_latest__mission-control; gh_releases__mission-control; gh_advisories__mission-control; gh_license__mission-control | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-02-13); identity not verified (NA) | Inputs: repo_created=2026-02-13, first_gh=2026-02-27, first_reg=None -> earliest=2026-02-13; gh_ver=v2.3.0, reg_ver=None -> latest=v2.3.0 |
| R9-122 | P4 | obsidian-tasks | obsidian-tasks-group/obsidian-tasks | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2021-03-19 (5.08y) | 8.6.0 | 4081 | NONE | 0 GH / 0 OSV | TypeScript | obsidian-tasks-group | NA: no_package_registered | gh_repo__obsidian-tasks-group_obsidian-tasks; gh_release_latest__obsidian-tasks; gh_releases__obsidian-tasks; gh_advisories__obsidian-tasks; gh_license__obsidian-tasks | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2021-03-19, first_gh=2021-04-12, first_reg=None -> earliest=2021-03-19; gh_ver=8.6.0, reg_ver=None -> latest=8.6.0 |
| R9-123 | P5 | Cosmic Ray | sixty-north/cosmic-ray | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-04-18 (11.0y) | release/v8.7.0 | 664 | NONE | 0 GH / 0 OSV | Python | sixty-north | MATCH:  | gh_repo__sixty-north_cosmic-ray; gh_release_latest__cosmic-ray; gh_releases__cosmic-ray; gh_advisories__cosmic-ray; gh_license__cosmic-ray | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2015-04-18, first_gh=2026-04-02, first_reg=None -> earliest=2015-04-18; gh_ver=release/v8.7.0, reg_ver=None -> latest=release/v8.7.0 |
| R9-124 | P5 | Stryker | stryker-mutator/stryker-js | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2016-02-12 (10.17y) | v10.1.1 | 3335 | NONE | 0 GH / 0 OSV | TypeScript | stryker-mutator | MATCH:  | gh_repo__stryker-mutator_stryker-js; gh_release_latest__stryker; gh_releases__stryker; gh_advisories__stryker; gh_license__stryker | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2016-02-12, first_gh=2016-03-24, first_reg=None -> earliest=2016-02-12; gh_ver=v10.1.1, reg_ver=None -> latest=v10.1.1 |
| R9-125 | P5 | PIT | hcoles/pitest | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2014-01-07 (12.27y) | 1.30.2 | 1887 | NONE | 0 GH / 0 OSV | Java | hcoles | NA: no_package_registered | gh_repo__hcoles_pitest; gh_release_latest__pitest; gh_releases__pitest; gh_advisories__pitest; gh_license__pitest | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2014-01-07, first_gh=2014-03-25, first_reg=None -> earliest=2014-01-07; gh_ver=1.30.2, reg_ver=None -> latest=1.30.2 |
| R9-126 | P5 | Vitest | vitest-dev/vitest | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2021-12-03 (4.37y) | v5.1.0 | 17340 | NONE | 10 GH / 3 OSV | TypeScript | vitest-dev | MATCH:  | gh_repo__vitest-dev_vitest; gh_release_latest__vitest; gh_releases__vitest; gh_advisories__vitest; gh_license__vitest | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2021-12-03, first_gh=2022-03-17, first_reg=None -> earliest=2021-12-03; gh_ver=v5.1.0, reg_ver=None -> latest=v5.1.0 |
| R9-127 | P5 | Jest | jestjs/jest | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2013-12-10 (12.35y) | v30.5.2 | 45468 | NONE | 0 GH / 0 OSV | TypeScript | jestjs | MATCH:  | gh_repo__jestjs_jest; gh_release_latest__jest; gh_releases__jest; gh_advisories__jest; gh_license__jest | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2013-12-10, first_gh=2019-08-16, first_reg=None -> earliest=2013-12-10; gh_ver=v30.5.2, reg_ver=None -> latest=v30.5.2 |
| R9-128 | P5 | Playwright | microsoft/playwright | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-11-15 (6.42y) | v1.65.0 | 99421 | NONE | 0 GH / 1 OSV | TypeScript | microsoft | MISMATCH: wrapper https://github.com/microsoft/playwright-python vs canonical https://github.com/microsoft/playwright | gh_repo__microsoft_playwright; gh_release_latest__playwright; gh_releases__playwright; gh_advisories__playwright; gh_license__playwright | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (MISMATCH) | Inputs: repo_created=2019-11-15, first_gh=2020-02-01, first_reg=None -> earliest=2019-11-15; gh_ver=v1.65.0, reg_ver=None -> latest=v1.65.0 |
| R9-129 | P5 | Testcontainers | testcontainers/testcontainers-python | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-03-22 (9.07y) | testcontainers-v4.15.0 | 2318 | NONE | 0 GH / 0 OSV | Python | testcontainers | MATCH:  | gh_repo__testcontainers_testcontainers-python; gh_release_latest__testcontainers-python; gh_releases__testcontainers-python; gh_advisories__testcontainers-python; gh_license__testcontainers-python | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2017-03-22, first_gh=2017-03-28, first_reg=None -> earliest=2017-03-22; gh_ver=testcontainers-v4.15.0, reg_ver=None -> latest=testcontainers-v4.15.0 |
| R9-130 | P5 | Pact | pact-foundation/pact-python | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2017-03-22 (9.07y) | pact-python/4.2.0 | 687 | NONE | 0 GH / 0 OSV | Python | pact-foundation | MATCH:  | gh_repo__pact-foundation_pact-python; gh_release_latest__pact-python; gh_releases__pact-python; gh_advisories__pact-python; gh_license__pact-python | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2017-03-22, first_gh=2017-05-02, first_reg=None -> earliest=2017-03-22; gh_ver=pact-python/4.2.0, reg_ver=None -> latest=pact-python/4.2.0 |
| R9-131 | P5 | pytest-cov | pytest-dev/pytest-cov | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2014-04-17 (12.0y) | NO_RELEASE | 2076 | NONE | 0 GH / 0 OSV | Python | pytest-dev | MATCH:  | gh_repo__pytest-dev_pytest-cov; gh_release_latest__pytest-cov; gh_releases__pytest-cov; gh_advisories__pytest-cov; gh_license__pytest-cov | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE) | Inputs: repo_created=2014-04-17, first_gh=None, first_reg=None -> earliest=2014-04-17; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-132 | P5 | tox | tox-dev/tox | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2016-09-17 (9.58y) | 4.67.12 | 3976 | NONE | 29 GH / 0 OSV | Python | tox-dev | MATCH:  | gh_repo__tox-dev_tox; gh_release_latest__tox; gh_releases__tox; gh_advisories__tox; gh_license__tox | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2016-09-17, first_gh=2018-10-08, first_reg=None -> earliest=2016-09-17; gh_ver=4.67.12, reg_ver=None -> latest=4.67.12 |
| R9-133 | P5 | nox | wntrblm/nox | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2016-02-24 (10.14y) | 2026.10.20 | 1560 | NONE | 0 GH / 0 OSV | Python | wntrblm | MATCH:  | gh_repo__wntrblm_nox; gh_release_latest__nox; gh_releases__nox; gh_advisories__nox; gh_license__nox | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2016-02-24, first_gh=2017-09-18, first_reg=None -> earliest=2016-02-24; gh_ver=2026.10.20, reg_ver=None -> latest=2026.10.20 |
| R9-134 | P5 | syrupy | syrupy-project/syrupy | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2019-10-20 (6.49y) | v6.1.1 | 901 | NONE | 0 GH / 0 OSV | Python | syrupy-project | MATCH:  | gh_repo__syrupy-project_syrupy; gh_release_latest__syrupy; gh_releases__syrupy; gh_advisories__syrupy; gh_license__syrupy | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2019-10-20, first_gh=2019-12-06, first_reg=None -> earliest=2019-10-20; gh_ver=v6.1.1, reg_ver=None -> latest=v6.1.1 |
| R9-135 | P5 | k6 | grafana/k6 | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2016-03-21 (10.07y) | v1.8.2 | 32166 | NONE | 0 GH / 0 OSV | Go | grafana | NA: no_package_registered | gh_repo__grafana_k6; gh_release_latest__k6; gh_releases__k6; gh_advisories__k6; gh_license__k6 | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2016-03-21, first_gh=2017-01-18, first_reg=None -> earliest=2016-03-21; gh_ver=v1.8.2, reg_ver=None -> latest=v1.8.2 |
| R9-136 | P5 | Locust | locustio/locust | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2011-02-17 (15.16y) | 2.47.0 | 28265 | NONE | 0 GH / 2 OSV | Python | locustio | MATCH:  | gh_repo__locustio_locust; gh_release_latest__locust; gh_releases__locust; gh_advisories__locust; gh_license__locust | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2011-02-17, first_gh=2017-09-15, first_reg=None -> earliest=2011-02-17; gh_ver=2.47.0, reg_ver=None -> latest=2.47.0 |
| R9-137 | P5 | pytest-benchmark | ionelmc/pytest-benchmark | PERMISSIVE (BSD-3-Clause) [Quote: "Redistribution and use in source and binary forms"] | 2014-10-10 (11.52y) | v5.3.0 | 1459 | NONE | 0 GH / 0 OSV | Python | ionelmc | MATCH:  | gh_repo__ionelmc_pytest-benchmark; gh_release_latest__pytest-benchmark; gh_releases__pytest-benchmark; gh_advisories__pytest-benchmark; gh_license__pytest-benchmark | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2014-10-10, first_gh=2026-08-24, first_reg=None -> earliest=2014-10-10; gh_ver=v5.3.0, reg_ver=None -> latest=v5.3.0 |
| R9-138 | P5 | Atheris | google/atheris | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2020-11-16 (5.41y) | NO_RELEASE | 1698 | NONE | 0 GH / 0 OSV | Python | google | MATCH:  | gh_repo__google_atheris; gh_release_latest__atheris; gh_releases__atheris; gh_advisories__atheris; gh_license__atheris | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE) | Inputs: repo_created=2020-11-16, first_gh=None, first_reg=None -> earliest=2020-11-16; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-139 | P5 | flaky | box/flaky | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2014-04-07 (12.02y) | v3.8.1 | 399 | NONE | 0 GH / 0 OSV | Python | box | MATCH:  | gh_repo__box_flaky; gh_release_latest__flaky; gh_releases__flaky; gh_advisories__flaky; gh_license__flaky | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | stars <500 (399) | Inputs: repo_created=2014-04-07, first_gh=2014-08-28, first_reg=None -> earliest=2014-04-07; gh_ver=v3.8.1, reg_ver=None -> latest=v3.8.1 |
| R9-140 | P5 | Cypress | cypress-io/cypress | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-03-04 (11.12y) | v16.2.1 | 51024 | NONE | 0 GH / 0 OSV | TypeScript | cypress-io | MATCH:  | gh_repo__cypress-io_cypress; gh_release_latest__cypress; gh_releases__cypress; gh_advisories__cypress; gh_license__cypress | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2015-03-04, first_gh=2018-07-19, first_reg=None -> earliest=2015-03-04; gh_ver=v16.2.1, reg_ver=None -> latest=v16.2.1 |
| R9-141 | P5 | Puppeteer | puppeteer/puppeteer | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-05-09 (8.94y) | puppeteer-v25.16.0 | 95806 | NONE | 0 GH / 1 OSV | TypeScript | puppeteer | MATCH:  | gh_repo__puppeteer_puppeteer; gh_release_latest__puppeteer; gh_releases__puppeteer; gh_advisories__puppeteer; gh_license__puppeteer | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2017-05-09, first_gh=2024-08-08, first_reg=None -> earliest=2017-05-09; gh_ver=puppeteer-v25.16.0, reg_ver=None -> latest=puppeteer-v25.16.0 |
| R9-142 | P5 | WebdriverIO | webdriverio/webdriverio | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2011-08-30 (14.63y) | v10.2.0 | 9870 | NONE | 1 GH / 0 OSV | TypeScript | webdriverio | MATCH:  | gh_repo__webdriverio_webdriverio; gh_release_latest__webdriverio; gh_releases__webdriverio; gh_advisories__webdriverio; gh_license__webdriverio | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2011-08-30, first_gh=2023-07-11, first_reg=None -> earliest=2011-08-30; gh_ver=v10.2.0, reg_ver=None -> latest=v10.2.0 |
| R9-143 | P6; P1 | Aider (incl. repo-map) | Aider-AI/aider | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-05-09 (2.94y) | v0.86.0 | 49979 | moved_to=Aider-AI/aider | 0 GH / 4 OSV | Python | Aider-AI | MATCH:  | gh_repo__Aider-AI_aider; gh_release_latest__aider; gh_releases__aider; gh_advisories__aider; gh_license__aider | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.86.0) | Inputs: repo_created=2023-05-09, first_gh=2023-06-07, first_reg=None -> earliest=2023-05-09; gh_ver=v0.86.0, reg_ver=None -> latest=v0.86.0 |
| R9-144 | P6 | SWE-agent | SWE-agent/SWE-agent | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2024-04-02 (2.04y) | v1.1.0 | 20736 | NONE | 0 GH / 0 OSV | Python | SWE-agent | MISMATCH: wrapper https://github.com/princeton-nlp/swe-agent vs canonical https://github.com/SWE-agent/SWE-agent | gh_repo__SWE-agent_SWE-agent; gh_release_latest__swe-agent; gh_releases__swe-agent; gh_advisories__swe-agent; gh_license__swe-agent | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (MISMATCH) | Inputs: repo_created=2024-04-02, first_gh=2024-04-15, first_reg=None -> earliest=2024-04-02; gh_ver=v1.1.0, reg_ver=None -> latest=v1.1.0 |
| R9-145 | P6 | OpenHands | OpenHands/OpenHands | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2024-03-13 (2.09y) | v1.36.0 | 92770 | NONE | 1 GH / 2 OSV | TypeScript | OpenHands | MATCH:  | gh_repo__OpenHands_OpenHands; gh_release_latest__openhands; gh_releases__openhands; gh_advisories__openhands; gh_license__openhands | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2024-03-13, first_gh=2024-06-04, first_reg=None -> earliest=2024-03-13; gh_ver=v1.36.0, reg_ver=None -> latest=v1.36.0 |
| R9-146 | P6 | mini-SWE-agent | SWE-agent/mini-swe-agent | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-06-28 (0.8y) | 2.4.6 / gh=v2.4.6 | 9127 | NONE | 0 GH / 0 OSV | Python | SWE-agent | NA: no_package_registered | gh_repo__SWE-agent_mini-swe-agent; gh_release_latest__mini-swe-agent; gh_releases__mini-swe-agent; gh_advisories__mini-swe-agent; gh_license__mini-swe-agent | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-06-28); identity not verified (NA) | Inputs: repo_created=2025-06-28, first_gh=2025-07-21, first_reg=2025-07-23 -> earliest=2025-06-28; gh_ver=v2.4.6, reg_ver=2.4.6 -> latest=2.4.6 / gh=v2.4.6 |
| R9-147 | P6 | Goose | aaif-goose/goose | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-08-23 (1.65y) | v1.57.0 | 56273 | NONE | 1 GH / 0 OSV | Rust | aaif-goose | NA: no_package_registered | gh_repo__aaif-goose_goose; gh_release_latest__goose; gh_releases__goose; gh_advisories__goose; gh_license__goose | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-08-23); identity not verified (NA) | Inputs: repo_created=2024-08-23, first_gh=2024-09-10, first_reg=None -> earliest=2024-08-23; gh_ver=v1.57.0, reg_ver=None -> latest=v1.57.0 |
| R9-148 | P6 | Codex CLI | openai/codex | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2025-04-13 (1.01y) | rust-v0.167.0 | 133380 | NONE | 1 GH / 0 OSV | Rust | openai | NA: no_package_registered | gh_repo__openai_codex; gh_release_latest__codex-cli; gh_releases__codex-cli; gh_advisories__codex-cli; gh_license__codex-cli | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-04-13); version <1.0.0 (rust-v0.167.0); identity not verified (NA) | Inputs: repo_created=2025-04-13, first_gh=None, first_reg=None -> earliest=2025-04-13; gh_ver=rust-v0.167.0, reg_ver=None -> latest=rust-v0.167.0 |
| R9-149 | P6 | Gemini CLI | google-gemini/gemini-cli | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2025-04-17 (1.0y) | v0.68.0-preview.0 | 108748 | NONE | 0 GH / 1 OSV | TypeScript | google-gemini | MATCH:  | gh_repo__google-gemini_gemini-cli; gh_release_latest__gemini-cli; gh_releases__gemini-cli; gh_advisories__gemini-cli; gh_license__gemini-cli | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-04-17); version <1.0.0 (v0.68.0-preview.0) | Inputs: repo_created=2025-04-17, first_gh=2026-02-28, first_reg=None -> earliest=2025-04-17; gh_ver=v0.68.0-preview.0, reg_ver=None -> latest=v0.68.0-preview.0 |
| R9-150 | P6 | OpenCode | anomalyco/opencode | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-04-30 (0.96y) | process-daemon-v0.5.0 | 224852 | NONE | 3 GH / 0 OSV | TypeScript | anomalyco | NA: no_package_registered | gh_repo__anomalyco_opencode; gh_release_latest__opencode; gh_releases__opencode; gh_advisories__opencode; gh_license__opencode | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-04-30); version <1.0.0 (process-daemon-v0.5.0); identity not verified (NA) | Inputs: repo_created=2025-04-30, first_gh=2025-12-15, first_reg=None -> earliest=2025-04-30; gh_ver=process-daemon-v0.5.0, reg_ver=None -> latest=process-daemon-v0.5.0 |
| R9-151 | P6 | Cline | cline/cline | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-07-06 (1.78y) | v4.1.26 | 71378 | NONE | 3 GH / 0 OSV | TypeScript | cline | NA: no_package_registered | gh_repo__cline_cline; gh_release_latest__cline; gh_releases__cline; gh_advisories__cline; gh_license__cline | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-07-06); identity not verified (NA) | Inputs: repo_created=2024-07-06, first_gh=2025-09-28, first_reg=None -> earliest=2024-07-06; gh_ver=v4.1.26, reg_ver=None -> latest=v4.1.26 |
| R9-152 | P6 | Continue | continuedev/continue | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-05-24 (2.9y) | v2.1.0-vscode | 36414 | NONE | 0 GH / 0 OSV | TypeScript | continuedev | NO_REPO_URL:  | gh_repo__continuedev_continue; gh_release_latest__continue; gh_releases__continue; gh_advisories__continue; gh_license__continue | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NO_REPO_URL) | Inputs: repo_created=2023-05-24, first_gh=2025-09-27, first_reg=None -> earliest=2023-05-24; gh_ver=v2.1.0-vscode, reg_ver=None -> latest=v2.1.0-vscode |
| R9-153 | P6 | pre-commit | pre-commit/pre-commit | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2014-03-13 (12.09y) | v4.7.0 | 15686 | NONE | 0 GH / 0 OSV | Python | pre-commit | MATCH:  | gh_repo__pre-commit_pre-commit; gh_release_latest__pre-commit; gh_releases__pre-commit; gh_advisories__pre-commit; gh_license__pre-commit | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2014-03-13, first_gh=2017-09-07, first_reg=None -> earliest=2014-03-13; gh_ver=v4.7.0, reg_ver=None -> latest=v4.7.0 |
| R9-154 | P6 | black | psf/black | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2018-03-14 (8.09y) | 26.10.1 | 42118 | NONE | 3 GH / 6 OSV | Python | psf | MATCH:  | gh_repo__psf_black; gh_release_latest__black; gh_releases__black; gh_advisories__black; gh_license__black | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2018-03-14, first_gh=2019-03-14, first_reg=None -> earliest=2018-03-14; gh_ver=26.10.1, reg_ver=None -> latest=26.10.1 |
| R9-155 | P6 | prettier | prettier/prettier | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2016-11-29 (9.38y) | 3.9.10 | 52405 | NONE | 1 GH / 0 OSV | JavaScript | prettier | MATCH:  | gh_repo__prettier_prettier; gh_release_latest__prettier; gh_releases__prettier; gh_advisories__prettier; gh_license__prettier | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2016-11-29, first_gh=2017-04-19, first_reg=None -> earliest=2016-11-29; gh_ver=3.9.10, reg_ver=None -> latest=3.9.10 |
| R9-156 | P6 | gVisor | google/gvisor | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2018-04-26 (7.97y) | release-20261102.0 | 19883 | NONE | 0 GH / 0 OSV | Go | google | NA: no_package_registered | gh_repo__google_gvisor; gh_release_latest__gvisor; gh_releases__gvisor; gh_advisories__gvisor; gh_license__gvisor | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2018-04-26, first_gh=2026-08-25, first_reg=None -> earliest=2018-04-26; gh_ver=release-20261102.0, reg_ver=None -> latest=release-20261102.0 |
| R9-157 | P6 | Firecracker | firecracker-microvm/firecracker | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-10-19 (8.49y) | v1.17.0 | 37853 | NONE | 3 GH / 0 OSV | Rust | firecracker-microvm | NA: no_package_registered | gh_repo__firecracker-microvm_firecracker; gh_release_latest__firecracker; gh_releases__firecracker; gh_advisories__firecracker; gh_license__firecracker | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2017-10-19, first_gh=2018-03-05, first_reg=None -> earliest=2017-10-19; gh_ver=v1.17.0, reg_ver=None -> latest=v1.17.0 |
| R9-158 | P6 | nsjail | google/nsjail | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2015-05-14 (10.92y) | 3.6 | 4186 | NONE | 0 GH / 0 OSV | C++ | google | NA: no_package_registered | gh_repo__google_nsjail; gh_release_latest__nsjail; gh_releases__nsjail; gh_advisories__nsjail; gh_license__nsjail | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2015-05-14, first_gh=2015-08-14, first_reg=None -> earliest=2015-05-14; gh_ver=3.6, reg_ver=None -> latest=3.6 |
| R9-159 | P6 | firejail | netblue30/firejail | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2015-08-08 (10.69y) | 0.9.82.2 | 7727 | NONE | 0 GH / 0 OSV | C | netblue30 | NA: no_package_registered | gh_repo__netblue30_firejail; gh_release_latest__firejail; gh_releases__firejail; gh_advisories__firejail; gh_license__firejail | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.9.82.2); identity not verified (NA) | Inputs: repo_created=2015-08-08, first_gh=2020-08-11, first_reg=None -> earliest=2015-08-08; gh_ver=0.9.82.2, reg_ver=None -> latest=0.9.82.2 |
| R9-160 | P6 | Kata Containers | kata-containers/kata-containers | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-12-07 (8.36y) | 4.3.1 | 9087 | NONE | 13 GH / 0 OSV | Rust | kata-containers | NA: no_package_registered | gh_repo__kata-containers_kata-containers; gh_release_latest__kata-containers; gh_releases__kata-containers; gh_advisories__kata-containers; gh_license__kata-containers | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2017-12-07, first_gh=2020-01-16, first_reg=None -> earliest=2017-12-07; gh_ver=4.3.1, reg_ver=None -> latest=4.3.1 |
| R9-161 | P6 | Docker rootless (Moby) | moby/moby | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2013-01-18 (13.24y) | docker-v29.10.0-rc.1 | 72270 | NONE | 26 GH / 0 OSV | Go | moby | NA: no_package_registered | gh_repo__moby_moby; gh_release_latest__moby; gh_releases__moby; gh_advisories__moby; gh_license__moby | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2013-01-18, first_gh=2016-03-10, first_reg=None -> earliest=2013-01-18; gh_ver=docker-v29.10.0-rc.1, reg_ver=None -> latest=docker-v29.10.0-rc.1 |
| R9-162 | P6 | microsandbox | superradcompany/microsandbox | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-10-03 (1.53y) | v0.7.13 | 8960 | NONE | 12 GH / 0 OSV | Rust | superradcompany | NA: no_package_registered | gh_repo__superradcompany_microsandbox; gh_release_latest__microsandbox; gh_releases__microsandbox; gh_advisories__microsandbox; gh_license__microsandbox | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-10-03); version <1.0.0 (v0.7.13); identity not verified (NA) | Inputs: repo_created=2024-10-03, first_gh=2024-12-03, first_reg=None -> earliest=2024-10-03; gh_ver=v0.7.13, reg_ver=None -> latest=v0.7.13 |
| R9-163 | P6 | Roo-Code | RooCodeInc/Roo-Code | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-10-31 (1.46y) | v3.54.0 | 24243 | archived | 11 GH / 0 OSV | TypeScript | RooCodeInc | NA: no_package_registered | gh_repo__RooCodeInc_Roo-Code; gh_release_latest__roo-code; gh_releases__roo-code; gh_advisories__roo-code; gh_license__roo-code | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-10-31); identity not verified (NA) | Inputs: repo_created=2024-10-31, first_gh=2025-03-19, first_reg=None -> earliest=2024-10-31; gh_ver=v3.54.0, reg_ver=None -> latest=v3.54.0 |
| R9-164 | P7 | pylint | pylint-dev/pylint | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2015-12-09 (10.35y) | v4.1.3 | 5747 | NONE | 1 GH / 1 OSV | Python | pylint-dev | MATCH:  | gh_repo__pylint-dev_pylint; gh_release_latest__pylint; gh_releases__pylint; gh_advisories__pylint; gh_license__pylint | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]) | Inputs: repo_created=2015-12-09, first_gh=2021-03-28, first_reg=None -> earliest=2015-12-09; gh_ver=v4.1.3, reg_ver=None -> latest=v4.1.3 |
| R9-165 | P7 | flake8 | PyCQA/flake8 | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | NO_DATE (NA) | NO_RELEASE | 3833 | NONE | 0 GH / 0 OSV | Python | PyCQA | MATCH:  | gh_repo__PyCQA_flake8; gh_release_latest__flake8; gh_releases__flake8; gh_advisories__flake8; gh_license__flake8 | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-166 | P7 | eslint | eslint/eslint | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2013-06-29 (12.8y) | v10.14.0 | 27604 | NONE | 0 GH / 0 OSV | JavaScript | eslint | MATCH:  | gh_repo__eslint_eslint; gh_release_latest__eslint; gh_releases__eslint; gh_advisories__eslint; gh_license__eslint | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2013-06-29, first_gh=2016-10-17, first_reg=None -> earliest=2013-06-29; gh_ver=v10.14.0, reg_ver=None -> latest=v10.14.0 |
| R9-167 | P7 | golangci-lint | golangci/golangci-lint | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2018-05-04 (7.95y) | v2.15.0 | 19505 | NONE | 0 GH / 0 OSV | Go | golangci | NA: no_package_registered | gh_repo__golangci_golangci-lint; gh_release_latest__golangci-lint; gh_releases__golangci-lint; gh_advisories__golangci-lint; gh_license__golangci-lint | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2018-05-04, first_gh=2018-05-29, first_reg=None -> earliest=2018-05-04; gh_ver=v2.15.0, reg_ver=None -> latest=v2.15.0 |
| R9-168 | P7; P9 | SonarQube Community | SonarSource/sonarqube | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2011-01-05 (15.28y) | 26.11.0.134175 | 11155 | NONE | 0 GH / 0 OSV | Java | SonarSource | NA: no_package_registered | gh_repo__SonarSource_sonarqube; gh_release_latest__sonarqube; gh_releases__sonarqube; gh_advisories__sonarqube; gh_license__sonarqube | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2011-01-05, first_gh=2020-04-29, first_reg=None -> earliest=2011-01-05; gh_ver=26.11.0.134175, reg_ver=None -> latest=26.11.0.134175 |
| R9-169 | P7 | Infer | meta/infer | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-01-26 (11.22y) | v1.3.0 | 15744 | NONE | 0 GH / 0 OSV | OCaml | meta | NA: no_package_registered | gh_repo__meta_infer; gh_release_latest__infer; gh_releases__infer; gh_advisories__infer; gh_license__infer | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2015-01-26, first_gh=2015-06-11, first_reg=None -> earliest=2015-01-26; gh_ver=v1.3.0, reg_ver=None -> latest=v1.3.0 |
| R9-170 | P7 | Trivy | aquasecurity/trivy | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-04-11 (7.01y) | v0.76.2 | 39047 | NONE | 5 GH / 0 OSV | Go | aquasecurity | NA: no_package_registered | gh_repo__aquasecurity_trivy; gh_release_latest__trivy; gh_releases__trivy; gh_advisories__trivy; gh_license__trivy | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.76.2); identity not verified (NA) | Inputs: repo_created=2019-04-11, first_gh=2019-05-07, first_reg=None -> earliest=2019-04-11; gh_ver=v0.76.2, reg_ver=None -> latest=v0.76.2 |
| R9-171 | P7 | Grype | anchore/grype | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2020-05-26 (5.89y) | v0.121.2 | 13190 | NONE | 1 GH / 0 OSV | Go | anchore | NA: no_package_registered | gh_repo__anchore_grype; gh_release_latest__grype; gh_releases__grype; gh_advisories__grype; gh_license__grype | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.121.2); identity not verified (NA) | Inputs: repo_created=2020-05-26, first_gh=2020-07-27, first_reg=None -> earliest=2020-05-26; gh_ver=v0.121.2, reg_ver=None -> latest=v0.121.2 |
| R9-172 | P7 | OSV-Scanner | google/osv-scanner | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2022-11-14 (3.42y) | v2.7.0 | 11421 | NONE | 0 GH / 0 OSV | Go | google | NA: no_package_registered | gh_repo__google_osv-scanner; gh_release_latest__osv-scanner; gh_releases__osv-scanner; gh_advisories__osv-scanner; gh_license__osv-scanner | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2022-11-14, first_gh=2022-12-13, first_reg=None -> earliest=2022-11-14; gh_ver=v2.7.0, reg_ver=None -> latest=v2.7.0 |
| R9-173 | P7 | TruffleHog | trufflesecurity/trufflehog | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2016-12-31 (9.29y) | v3.99.8 | 28903 | NONE | 2 GH / 0 OSV | Go | trufflesecurity | NA: no_package_registered | gh_repo__trufflesecurity_trufflehog; gh_release_latest__trufflehog; gh_releases__trufflehog; gh_advisories__trufflehog; gh_license__trufflehog | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2016-12-31, first_gh=2022-11-02, first_reg=None -> earliest=2016-12-31; gh_ver=v3.99.8, reg_ver=None -> latest=v3.99.8 |
| R9-174 | P7 | Checkov | bridgecrewio/checkov | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-11-27 (6.38y) | 3.4.3 | 9136 | NONE | 0 GH / 0 OSV | Python | bridgecrewio | MATCH:  | gh_repo__bridgecrewio_checkov; gh_release_latest__checkov; gh_releases__checkov; gh_advisories__checkov; gh_license__checkov | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2019-11-27, first_gh=2024-03-10, first_reg=None -> earliest=2019-11-27; gh_ver=3.4.3, reg_ver=None -> latest=3.4.3 |
| R9-175 | P7 | hadolint | hadolint/hadolint | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2015-11-15 (10.42y) | v2.15.1 | 12515 | NONE | 0 GH / 0 OSV | Haskell | hadolint | NA: no_package_registered | gh_repo__hadolint_hadolint; gh_release_latest__hadolint; gh_releases__hadolint; gh_advisories__hadolint; gh_license__hadolint | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2015-11-15, first_gh=2016-04-03, first_reg=None -> earliest=2015-11-15; gh_ver=v2.15.1, reg_ver=None -> latest=v2.15.1 |
| R9-176 | P7 | actionlint | rhysd/actionlint | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2021-05-25 (4.89y) | v1.7.12 | 4387 | NONE | 0 GH / 0 OSV | Go | rhysd | NA: no_package_registered | gh_repo__rhysd_actionlint; gh_release_latest__actionlint; gh_releases__actionlint; gh_advisories__actionlint; gh_license__actionlint | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2021-05-25, first_gh=2021-06-16, first_reg=None -> earliest=2021-05-25; gh_ver=v1.7.12, reg_ver=None -> latest=v1.7.12 |
| R9-177 | P7 | vulture | jendrikseipp/vulture | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2017-03-06 (9.11y) | v2.16 | 4875 | NONE | 0 GH / 0 OSV | Python | jendrikseipp | MATCH:  | gh_repo__jendrikseipp_vulture; gh_release_latest__vulture; gh_releases__vulture; gh_advisories__vulture; gh_license__vulture | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2017-03-06, first_gh=2020-02-03, first_reg=None -> earliest=2017-03-06; gh_ver=v2.16, reg_ver=None -> latest=v2.16 |
| R9-178 | P7 | radon | rubik/radon | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2012-09-20 (13.57y) | NO_RELEASE | 2038 | NONE | 0 GH / 0 OSV | Python | rubik | MATCH:  | gh_repo__rubik_radon; gh_release_latest__radon; gh_releases__radon; gh_advisories__radon; gh_license__radon | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); pushed >1y ago (2024-10-20) | Inputs: repo_created=2012-09-20, first_gh=None, first_reg=None -> earliest=2012-09-20; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-179 | P7 | lizard | terryyin/lizard | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2012-06-21 (13.82y) | 1.25.0 | 2586 | NONE | 0 GH / 0 OSV | JavaScript | terryyin | MATCH:  | gh_repo__terryyin_lizard; gh_release_latest__lizard; gh_releases__lizard; gh_advisories__lizard; gh_license__lizard | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2012-06-21, first_gh=2026-01-13, first_reg=None -> earliest=2012-06-21; gh_ver=1.25.0, reg_ver=None -> latest=1.25.0 |
| R9-180 | P7 | jscpd | kucherenko/jscpd | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2013-05-29 (12.88y) | v5.4.2 | 6506 | NONE | 0 GH / 0 OSV | Rust | kucherenko | MATCH:  | gh_repo__kucherenko_jscpd; gh_release_latest__jscpd; gh_releases__jscpd; gh_advisories__jscpd; gh_license__jscpd | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2013-05-29, first_gh=2026-05-14, first_reg=None -> earliest=2013-05-29; gh_ver=v5.4.2, reg_ver=None -> latest=v5.4.2 |
| R9-181 | P7; P9 | Danger | danger/danger | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-09-29 (10.55y) | v9.6.1 | 5696 | NONE | 0 GH / 1 OSV | Ruby | danger | NO_REPO_URL:  | gh_repo__danger_danger; gh_release_latest__danger; gh_releases__danger; gh_advisories__danger; gh_license__danger | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NO_REPO_URL) | Inputs: repo_created=2015-09-29, first_gh=2016-04-13, first_reg=None -> earliest=2015-09-29; gh_ver=v9.6.1, reg_ver=None -> latest=v9.6.1 |
| R9-182 | P7 | oxc | oxc-project/oxc | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2023-02-09 (3.18y) | oxlint_v1.91.0 | 23347 | NONE | 0 GH / 0 OSV | Rust | oxc-project | MISMATCH: wrapper https://github.com/jasonmccreary/oxc vs canonical https://github.com/oxc-project/oxc | gh_repo__oxc-project_oxc; gh_release_latest__oxc; gh_releases__oxc; gh_advisories__oxc; gh_license__oxc | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (MISMATCH) | Inputs: repo_created=2023-02-09, first_gh=2023-02-28, first_reg=None -> earliest=2023-02-09; gh_ver=oxlint_v1.91.0, reg_ver=None -> latest=oxlint_v1.91.0 |
| R9-183 | P7 | biome | biomejs/biome | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-07-27 (2.72y) | @biomejs/biome@2.6.5 | 26053 | NONE | 0 GH / 0 OSV | Rust | biomejs | MATCH:  | gh_repo__biomejs_biome; gh_release_latest__biome; gh_releases__biome; gh_advisories__biome; gh_license__biome | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-07-27, first_gh=2023-08-18, first_reg=None -> earliest=2023-07-27; gh_ver=@biomejs/biome@2.6.5, reg_ver=None -> latest=@biomejs/biome@2.6.5 |
| R9-184 | P8 | LibCST | Instagram/LibCST | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-08-06 (6.69y) | v1.9.0 | 1972 | NONE | 0 GH / 0 OSV | Python | Instagram | MATCH:  | gh_repo__Instagram_LibCST; gh_release_latest__libcst; gh_releases__libcst; gh_advisories__libcst; gh_license__libcst | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2019-08-06, first_gh=2020-03-12, first_reg=None -> earliest=2019-08-06; gh_ver=v1.9.0, reg_ver=None -> latest=v1.9.0 |
| R9-185 | P8 | OpenRewrite | openrewrite/rewrite | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2020-05-12 (5.93y) | v8.100.0 | 3946 | NONE | 0 GH / 0 OSV | Java | openrewrite | NA: no_package_registered | gh_repo__openrewrite_rewrite; gh_release_latest__openrewrite; gh_releases__openrewrite; gh_advisories__openrewrite; gh_license__openrewrite | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2020-05-12, first_gh=2024-08-09, first_reg=None -> earliest=2020-05-12; gh_ver=v8.100.0, reg_ver=None -> latest=v8.100.0 |
| R9-186 | P8 | Comby | comby-tools/comby | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-04-08 (7.02y) | 1.8.1 | 2695 | NONE | 0 GH / 0 OSV | OCaml | comby-tools | NA: no_package_registered | gh_repo__comby-tools_comby; gh_release_latest__comby; gh_releases__comby; gh_advisories__comby; gh_license__comby | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2019-04-08, first_gh=2019-04-29, first_reg=None -> earliest=2019-04-08; gh_ver=1.8.1, reg_ver=None -> latest=1.8.1 |
| R9-187 | P8 | jscodeshift | meta/jscodeshift | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-03-07 (11.11y) | v17.3.0 | 10045 | NONE | 0 GH / 0 OSV | JavaScript | meta | MISMATCH: wrapper https://github.com/facebook/jscodeshift vs canonical https://github.com/meta/jscodeshift | gh_repo__meta_jscodeshift; gh_release_latest__jscodeshift; gh_releases__jscodeshift; gh_advisories__jscodeshift; gh_license__jscodeshift | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (MISMATCH) | Inputs: repo_created=2015-03-07, first_gh=2015-07-16, first_reg=None -> earliest=2015-03-07; gh_ver=v17.3.0, reg_ver=None -> latest=v17.3.0 |
| R9-188 | P8 | rope | python-rope/rope | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2013-11-30 (12.38y) | 1.15.2 | 2245 | NONE | 1 GH / 2 OSV | Python | python-rope | MATCH:  | gh_repo__python-rope_rope; gh_release_latest__rope; gh_releases__rope; gh_advisories__rope; gh_license__rope | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2013-11-30, first_gh=2024-01-18, first_reg=None -> earliest=2013-11-30; gh_ver=1.15.2, reg_ver=None -> latest=1.15.2 |
| R9-189 | P8 | Agentless | OpenAutoCoder/Agentless | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2024-06-30 (1.79y) | v1.5.0 | 2135 | NONE | 0 GH / 0 OSV | Python | OpenAutoCoder | NA: no_package_registered | gh_repo__OpenAutoCoder_Agentless; gh_release_latest__agentless; gh_releases__agentless; gh_advisories__agentless; gh_license__agentless | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-06-30); pushed >1y ago (2024-12-22); identity not verified (NA) | Inputs: repo_created=2024-06-30, first_gh=2024-07-02, first_reg=None -> earliest=2024-06-30; gh_ver=v1.5.0, reg_ver=None -> latest=v1.5.0 |
| R9-190 | P8 | Coccinelle | coccinelle/coccinelle | WEAK-COPYLEFT (LGPL-2.1-or-later) [Quote: "Lesser General Public License"] | 2010-09-29 (15.55y) | NO_RELEASE | 824 | NONE | 0 GH / 0 OSV | OCaml | coccinelle | NA: no_package_registered | gh_repo__coccinelle_coccinelle; gh_release_latest__coccinelle; gh_releases__coccinelle; gh_advisories__coccinelle; gh_license__coccinelle | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2010-09-29, first_gh=None, first_reg=None -> earliest=2010-09-29; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-191 | P8 | Sourcery | sourcery-ai/sourcery | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2019-07-15 (6.75y) | v1.46.1b7 | 1878 | NONE | 0 GH / 0 OSV | NA | sourcery-ai | NA: no_package_registered | gh_repo__sourcery-ai_sourcery; gh_release_latest__sourcery; gh_releases__sourcery; gh_advisories__sourcery; gh_license__sourcery | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2019-07-15, first_gh=2024-12-12, first_reg=None -> earliest=2019-07-15; gh_ver=v1.46.1b7, reg_ver=None -> latest=v1.46.1b7 |
| R9-192 | P9 | reviewdog | reviewdog/reviewdog | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2016-10-17 (9.49y) | v0.21.2 | 9721 | NONE | 1 GH / 0 OSV | Go | reviewdog | NA: no_package_registered | gh_repo__reviewdog_reviewdog; gh_release_latest__reviewdog; gh_releases__reviewdog; gh_advisories__reviewdog; gh_license__reviewdog | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.21.2); identity not verified (NA) | Inputs: repo_created=2016-10-17, first_gh=2016-10-23, first_reg=None -> earliest=2016-10-17; gh_ver=v0.21.2, reg_ver=None -> latest=v0.21.2 |
| R9-193 | P9 | Gerrit | GerritCodeReview/gerrit | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2015-12-10 (10.35y) | NO_RELEASE | 1237 | NONE | 0 GH / 0 OSV | Java | GerritCodeReview | NA: no_package_registered | gh_repo__GerritCodeReview_gerrit; gh_release_latest__gerrit; gh_releases__gerrit; gh_advisories__gerrit; gh_license__gerrit | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2015-12-10, first_gh=None, first_reg=None -> earliest=2015-12-10; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-194 | P9 | Kodus | kodustech/kodus-ai | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2025-03-28 (1.05y) | 2.2.12 | 1565 | NONE | 9 GH / 0 OSV | TypeScript | kodustech | NA: unresolved_repo | gh_repo__kodustech_kodus-ai; gh_release_latest__kodus; gh_releases__kodus; gh_advisories__kodus; gh_license__kodus | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-03-28); licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2025-03-28, first_gh=2026-06-10, first_reg=None -> earliest=2025-03-28; gh_ver=2.2.12, reg_ver=None -> latest=2.2.12 |
| R9-195 | P9 | PR-AF | Agent-Field/pr-af | MISSING (NONE) | 2026-03-11 (0.1y) | NO_RELEASE | 663 | NONE | 0 GH / 0 OSV | Go | Agent-Field | NA: no_package_registered | gh_repo__Agent-Field_pr-af; gh_release_latest__pr-af; gh_releases__pr-af; gh_advisories__pr-af; gh_license__pr-af | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-03-11); version <1.0.0 (NO_RELEASE); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=2026-03-11, first_gh=None, first_reg=None -> earliest=2026-03-11; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-196 | P9 | CodeRabbit | closed/coderabbit | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | closed | NA: closed_vendor | gh_repo__closed_coderabbit; gh_release_latest__coderabbit; gh_releases__coderabbit; gh_advisories__coderabbit; gh_license__coderabbit | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-197 | P10 | python-semantic-release | python-semantic-release/python-semantic-release | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-07-27 (10.72y) | v10.7.0 | 1080 | NONE | 0 GH / 0 OSV | Python | python-semantic-release | MATCH:  | gh_repo__python-semantic-release_python-semantic-release; gh_release_latest__python-semantic-release; gh_releases__python-semantic-release; gh_advisories__python-semantic-release; gh_license__python-semantic-release | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2015-07-27, first_gh=2015-07-27, first_reg=None -> earliest=2015-07-27; gh_ver=v10.7.0, reg_ver=None -> latest=v10.7.0 |
| R9-198 | P10 | release-please | googleapis/release-please | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-04-25 (6.98y) | v17.11.2 | 7737 | NONE | 0 GH / 0 OSV | TypeScript | googleapis | MATCH:  | gh_repo__googleapis_release-please; gh_release_latest__release-please; gh_releases__release-please; gh_advisories__release-please; gh_license__release-please | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2019-04-25, first_gh=2020-07-08, first_reg=None -> earliest=2019-04-25; gh_ver=v17.11.2, reg_ver=None -> latest=v17.11.2 |
| R9-199 | P10 | changesets | changesets/changesets | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2019-03-21 (7.07y) | @changesets/get-release-plan@5.0.2 | 12558 | NONE | 0 GH / 0 OSV | TypeScript | changesets | MATCH:  | gh_repo__changesets_changesets; gh_release_latest__changesets; gh_releases__changesets; gh_advisories__changesets; gh_license__changesets | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2019-03-21, first_gh=2022-08-14, first_reg=None -> earliest=2019-03-21; gh_ver=@changesets/get-release-plan@5.0.2, reg_ver=None -> latest=@changesets/get-release-plan@5.0.2 |
| R9-200 | P10 | commitizen | commitizen-tools/commitizen | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2017-10-07 (8.52y) | v4.19.3 | 3547 | NONE | 0 GH / 0 OSV | Python | commitizen-tools | MATCH:  | gh_repo__commitizen-tools_commitizen; gh_release_latest__commitizen; gh_releases__commitizen; gh_advisories__commitizen; gh_license__commitizen | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2017-10-07, first_gh=2023-12-07, first_reg=None -> earliest=2017-10-07; gh_ver=v4.19.3, reg_ver=None -> latest=v4.19.3 |
| R9-201 | P10 | git-cliff | orhun/git-cliff | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2021-05-30 (4.88y) | v2.14.2 | 12386 | NONE | 0 GH / 0 OSV | Rust | orhun | MATCH:  | gh_repo__orhun_git-cliff; gh_release_latest__git-cliff; gh_releases__git-cliff; gh_advisories__git-cliff; gh_license__git-cliff | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2021-05-30, first_gh=2021-06-14, first_reg=None -> earliest=2021-05-30; gh_ver=v2.14.2, reg_ver=None -> latest=v2.14.2 |
| R9-202 | P10 | towncrier | twisted/towncrier | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-12-27 (10.3y) | 26.9.0 | 928 | NONE | 0 GH / 0 OSV | Python | twisted | MATCH:  | gh_repo__twisted_towncrier; gh_release_latest__towncrier; gh_releases__towncrier; gh_advisories__towncrier; gh_license__towncrier | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2015-12-27, first_gh=2022-08-28, first_reg=None -> earliest=2015-12-27; gh_ver=26.9.0, reg_ver=None -> latest=26.9.0 |
| R9-203 | P10 | slsa-github-generator | slsa-framework/slsa-github-generator | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2022-03-28 (4.05y) | v2.1.0 | 609 | NONE | 0 GH / 0 OSV | Go | slsa-framework | NA: no_package_registered | gh_repo__slsa-framework_slsa-github-generator; gh_release_latest__slsa-github-generator; gh_releases__slsa-github-generator; gh_advisories__slsa-github-generator; gh_license__slsa-github-generator | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2022-03-28, first_gh=2022-05-25, first_reg=None -> earliest=2022-03-28; gh_ver=v2.1.0, reg_ver=None -> latest=v2.1.0 |
| R9-204 | P10 | spdx-tools | spdx/tools-python | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2015-03-23 (11.07y) | v0.8.5 | 258 | NONE | 0 GH / 0 OSV | Python | spdx | MATCH:  | gh_repo__spdx_tools-python; gh_release_latest__spdx-tools; gh_releases__spdx-tools; gh_advisories__spdx-tools; gh_license__spdx-tools | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.8.5); stars <500 (258) | Inputs: repo_created=2015-03-23, first_gh=2017-06-15, first_reg=None -> earliest=2015-03-23; gh_ver=v0.8.5, reg_ver=None -> latest=v0.8.5 |
| R9-205 | P10 | REUSE tool | fsfe/reuse-tool | MISSING (NONE) | 2019-04-12 (7.01y) | v6.2.0 | 595 | NONE | 0 GH / 0 OSV | Python | fsfe | MISMATCH: wrapper https://github.com/fsfe/reuse-example vs canonical https://github.com/fsfe/reuse-tool | gh_repo__fsfe_reuse-tool; gh_release_latest__reuse-tool; gh_releases__reuse-tool; gh_advisories__reuse-tool; gh_license__reuse-tool | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (MISMATCH) | Inputs: repo_created=2019-04-12, first_gh=2021-12-27, first_reg=None -> earliest=2019-04-12; gh_ver=v6.2.0, reg_ver=None -> latest=v6.2.0 |
| R9-206 | P10 | ORT / OSS Review Toolkit | oss-review-toolkit/ort | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-10-19 (8.49y) | 98.0.0 | 2117 | NONE | 1 GH / 0 OSV | Kotlin | oss-review-toolkit | NA: no_package_registered | gh_repo__oss-review-toolkit_ort; gh_release_latest__ort; gh_releases__ort; gh_advisories__ort; gh_license__ort | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2017-10-19, first_gh=2023-09-16, first_reg=None -> earliest=2017-10-19; gh_ver=98.0.0, reg_ver=None -> latest=98.0.0 |
| R9-207 | P10 | licensee | licensee/licensee | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2014-08-16 (11.67y) | v10.1.0 | 921 | NONE | 0 GH / 0 OSV | Ruby | licensee | NA: no_package_registered | gh_repo__licensee_licensee; gh_release_latest__licensee; gh_releases__licensee; gh_advisories__licensee; gh_license__licensee | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2014-08-16, first_gh=2014-08-18, first_reg=None -> earliest=2014-08-16; gh_ver=v10.1.0, reg_ver=None -> latest=v10.1.0 |
| R9-208 | P10 | Dependency-Track | DependencyTrack/dependency-track | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2013-07-16 (12.75y) | 5.2.1 | 4418 | NONE | 9 GH / 0 OSV | Java | DependencyTrack | NA: no_package_registered | gh_repo__DependencyTrack_dependency-track; gh_release_latest__dependency-track; gh_releases__dependency-track; gh_advisories__dependency-track; gh_license__dependency-track | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2013-07-16, first_gh=2018-03-27, first_reg=None -> earliest=2013-07-16; gh_ver=5.2.1, reg_ver=None -> latest=5.2.1 |
| R9-209 | P10 | GUAC | guacsec/guac | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2022-06-10 (3.85y) | v1.1.0 | 1570 | NONE | 0 GH / 0 OSV | Go | guacsec | NA: no_package_registered | gh_repo__guacsec_guac; gh_release_latest__guac; gh_releases__guac; gh_advisories__guac; gh_license__guac | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2022-06-10, first_gh=2023-03-01, first_reg=None -> earliest=2022-06-10; gh_ver=v1.1.0, reg_ver=None -> latest=v1.1.0 |
| R9-210 | P10 | semantic-release | semantic-release/semantic-release | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2014-09-15 (11.58y) | v26.0.0-beta.5 | 24159 | NONE | 2 GH / 2 OSV | JavaScript | semantic-release | MATCH:  | gh_repo__semantic-release_semantic-release; gh_release_latest__semantic-release-js; gh_releases__semantic-release-js; gh_advisories__semantic-release-js; gh_license__semantic-release-js | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2014-09-15, first_gh=2018-08-08, first_reg=None -> earliest=2014-09-15; gh_ver=v26.0.0-beta.5, reg_ver=None -> latest=v26.0.0-beta.5 |
| R9-211 | P10 | commitizen cz-cli | commitizen/cz-cli | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2015-04-20 (10.99y) | v4.3.2 | 17498 | NONE | 0 GH / 0 OSV | JavaScript | commitizen | MATCH:  | gh_repo__commitizen_cz-cli; gh_release_latest__cz-cli; gh_releases__cz-cli; gh_advisories__cz-cli; gh_license__cz-cli | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2015-04-20, first_gh=2015-05-07, first_reg=None -> earliest=2015-04-20; gh_ver=v4.3.2, reg_ver=None -> latest=v4.3.2 |
| R9-212 | P11 | Prometheus | prometheus/prometheus | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2012-11-24 (13.39y) | v3.16.0 | 66973 | NONE | 6 GH / 0 OSV | Go | prometheus | NA: no_package_registered | gh_repo__prometheus_prometheus; gh_release_latest__prometheus; gh_releases__prometheus; gh_advisories__prometheus; gh_license__prometheus | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2012-11-24, first_gh=2018-09-11, first_reg=None -> earliest=2012-11-24; gh_ver=v3.16.0, reg_ver=None -> latest=v3.16.0 |
| R9-213 | P11 | Jaeger | jaegertracing/jaeger | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2016-04-15 (10.0y) | v2.23.0 | 23381 | NONE | 2 GH / 0 OSV | Go | jaegertracing | NA: no_package_registered | gh_repo__jaegertracing_jaeger; gh_release_latest__jaeger; gh_releases__jaeger; gh_advisories__jaeger; gh_license__jaeger | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2016-04-15, first_gh=2017-07-01, first_reg=None -> earliest=2016-04-15; gh_ver=v2.23.0, reg_ver=None -> latest=v2.23.0 |
| R9-214 | P11 | Argo CD | argoproj/argo-cd | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2018-02-09 (8.18y) | v3.6.1 | 24553 | NONE | 30 GH / 0 OSV | Go | argoproj | NA: no_package_registered | gh_repo__argoproj_argo-cd; gh_release_latest__argo-cd; gh_releases__argo-cd; gh_advisories__argo-cd; gh_license__argo-cd | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2018-02-09, first_gh=None, first_reg=None -> earliest=2018-02-09; gh_ver=v3.6.1, reg_ver=None -> latest=v3.6.1 |
| R9-215 | P11 | Flux | fluxcd/flux2 | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2020-04-24 (5.98y) | v2.10.0 | 8498 | NONE | 7 GH / 0 OSV | Go | fluxcd | NA: no_package_registered | gh_repo__fluxcd_flux2; gh_release_latest__flux2; gh_releases__flux2; gh_advisories__flux2; gh_license__flux2 | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2020-04-24, first_gh=2020-05-06, first_reg=None -> earliest=2020-04-24; gh_ver=v2.10.0, reg_ver=None -> latest=v2.10.0 |
| R9-216 | P11 | Unleash | Unleash/unleash | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2014-09-29 (11.55y) | v8.3.1 | 13936 | NONE | 16 GH / 7 OSV | TypeScript | Unleash | MATCH:  | gh_repo__Unleash_unleash; gh_release_latest__unleash; gh_releases__unleash; gh_advisories__unleash; gh_license__unleash | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]) | Inputs: repo_created=2014-09-29, first_gh=2023-04-12, first_reg=None -> earliest=2014-09-29; gh_ver=v8.3.1, reg_ver=None -> latest=v8.3.1 |
| R9-217 | P11 | chaostoolkit | chaostoolkit/chaostoolkit | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-09-24 (8.56y) | 1.21.4 | 2035 | NONE | 0 GH / 0 OSV | Python | chaostoolkit | MATCH:  | gh_repo__chaostoolkit_chaostoolkit; gh_release_latest__chaostoolkit; gh_releases__chaostoolkit; gh_advisories__chaostoolkit; gh_license__chaostoolkit | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2017-09-24, first_gh=2017-11-23, first_reg=None -> earliest=2017-09-24; gh_ver=1.21.4, reg_ver=None -> latest=1.21.4 |
| R9-218 | P11 | Litmus | litmuschaos/litmus | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2017-03-15 (9.09y) | 3.33.0 | 5739 | NONE | 0 GH / 0 OSV | Go | litmuschaos | NA: no_package_registered | gh_repo__litmuschaos_litmus; gh_release_latest__litmus; gh_releases__litmus; gh_advisories__litmus; gh_license__litmus | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2017-03-15, first_gh=2019-09-13, first_reg=None -> earliest=2017-03-15; gh_ver=3.33.0, reg_ver=None -> latest=3.33.0 |
| R9-219 | P11 | Keptn | keptn/keptn | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-01-21 (7.23y) | 1.4.5 | 1771 | archived | 1 GH / 0 OSV | Go | keptn | NA: no_package_registered | gh_repo__keptn_keptn; gh_release_latest__keptn; gh_releases__keptn; gh_advisories__keptn; gh_license__keptn | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | pushed >1y ago (2023-12-21); identity not verified (NA) | Inputs: repo_created=2019-01-21, first_gh=2021-05-21, first_reg=None -> earliest=2019-01-21; gh_ver=1.4.5, reg_ver=None -> latest=1.4.5 |
| R9-220 | P11 | Chaos Mesh | chaos-mesh/chaos-mesh | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-09-04 (6.61y) | v2.8.8 | 7968 | NONE | 0 GH / 0 OSV | Go | chaos-mesh | NA: no_package_registered | gh_repo__chaos-mesh_chaos-mesh; gh_release_latest__chaos-mesh; gh_releases__chaos-mesh; gh_advisories__chaos-mesh; gh_license__chaos-mesh | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2019-09-04, first_gh=2020-04-26, first_reg=None -> earliest=2019-09-04; gh_ver=v2.8.8, reg_ver=None -> latest=v2.8.8 |
| R9-221 | P11 | ChaosBlade | chaosblade-io/chaosblade | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-03-12 (7.1y) | blade-ai-v0.7.4 | 6462 | NONE | 0 GH / 0 OSV | Python | chaosblade-io | NA: no_package_registered | gh_repo__chaosblade-io_chaosblade; gh_release_latest__chaosblade; gh_releases__chaosblade; gh_advisories__chaosblade; gh_license__chaosblade | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (blade-ai-v0.7.4); identity not verified (NA) | Inputs: repo_created=2019-03-12, first_gh=2019-03-27, first_reg=None -> earliest=2019-03-12; gh_ver=blade-ai-v0.7.4, reg_ver=None -> latest=blade-ai-v0.7.4 |
| R9-222 | X-graph | RDFLib | RDFLib/rdflib | PERMISSIVE (BSD-3-Clause) [Quote: "Redistribution and use in source and binary forms"] | 2012-02-03 (14.2y) | 7.6.0 | 2547 | NONE | 0 GH / 0 OSV | Python | RDFLib | MATCH:  | gh_repo__RDFLib_rdflib; gh_release_latest__rdflib; gh_releases__rdflib; gh_advisories__rdflib; gh_license__rdflib | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2012-02-03, first_gh=2015-02-19, first_reg=None -> earliest=2012-02-03; gh_ver=7.6.0, reg_ver=None -> latest=7.6.0 |
| R9-223 | X-graph | pyshacl | RDFLib/pySHACL | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2018-09-05 (7.61y) | v0.40.2 | 370 | NONE | 0 GH / 0 OSV | Python | RDFLib | MATCH:  | gh_repo__RDFLib_pySHACL; gh_release_latest__pyshacl; gh_releases__pyshacl; gh_advisories__pyshacl; gh_license__pyshacl | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.40.2); stars <500 (370) | Inputs: repo_created=2018-09-05, first_gh=2019-01-09, first_reg=None -> earliest=2018-09-05; gh_ver=v0.40.2, reg_ver=None -> latest=v0.40.2 |
| R9-224 | X-graph | Kuzu | kuzudb/kuzu | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2020-09-26 (5.55y) | v0.11.3 | 4021 | archived | 0 GH / 0 OSV | C++ | kuzudb | MATCH:  | gh_repo__kuzudb_kuzu; gh_release_latest__kuzu; gh_releases__kuzu; gh_advisories__kuzu; gh_license__kuzu | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.11.3) | Inputs: repo_created=2020-09-26, first_gh=2022-11-15, first_reg=None -> earliest=2020-09-26; gh_ver=v0.11.3, reg_ver=None -> latest=v0.11.3 |
| R9-225 | X-graph | Cozo | cozodb/cozo | WEAK-COPYLEFT (MPL-2.0) [Quote: "Mozilla Public License"] | 2022-10-14 (3.5y) | v0.7.6 | 4140 | NONE | 0 GH / 0 OSV | Rust | cozodb | NO_REPO_URL:  | gh_repo__cozodb_cozo; gh_release_latest__cozo; gh_releases__cozo; gh_advisories__cozo; gh_license__cozo | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.7.6); pushed >1y ago (2024-12-04); identity not verified (NO_REPO_URL) | Inputs: repo_created=2022-10-14, first_gh=2022-10-31, first_reg=None -> earliest=2022-10-14; gh_ver=v0.7.6, reg_ver=None -> latest=v0.7.6 |
| R9-226 | X-graph | Oxigraph | oxigraph/oxigraph | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2018-05-16 (7.92y) | v0.5.13 | 2024 | NONE | 0 GH / 0 OSV | Rust | oxigraph | MATCH:  | gh_repo__oxigraph_oxigraph; gh_release_latest__oxigraph; gh_releases__oxigraph; gh_advisories__oxigraph; gh_license__oxigraph | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.5.13) | Inputs: repo_created=2018-05-16, first_gh=2020-08-08, first_reg=None -> earliest=2018-05-16; gh_ver=v0.5.13, reg_ver=None -> latest=v0.5.13 |
| R9-227 | X-graph | SQLite | sqlite/sqlite | PERMISSIVE (NOASSERTION) | 2019-03-18 (7.08y) | NO_RELEASE | 10921 | NONE | 0 GH / 0 OSV | C | sqlite | NA: no_package_registered | gh_repo__sqlite_sqlite; gh_release_latest__sqlite; gh_releases__sqlite; gh_advisories__sqlite; gh_license__sqlite | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2019-03-18, first_gh=None, first_reg=None -> earliest=2019-03-18; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-228 | X-graph | W3C PROV-O spec | spec/w3c-prov-o | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | spec | NA: spec_document | gh_repo__spec_w3c-prov-o; gh_release_latest__prov-o-spec; gh_releases__prov-o-spec; gh_advisories__prov-o-spec; gh_license__prov-o-spec | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-229 | X-graph | JSON-LD spec | spec/w3c-json-ld | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | spec | NA: spec_document | gh_repo__spec_w3c-json-ld; gh_release_latest__json-ld-spec; gh_releases__json-ld-spec; gh_advisories__json-ld-spec; gh_license__json-ld-spec | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-230 | X-graph | Understand-Anything | Egonex-AI/Understand-Anything | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-03-15 (0.09y) | v2.9.0 | 90989 | NONE | 0 GH / 0 OSV | TypeScript | Egonex-AI | NA: no_package_registered | gh_repo__Egonex-AI_Understand-Anything; gh_release_latest__understand-anything; gh_releases__understand-anything; gh_advisories__understand-anything; gh_license__understand-anything | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-03-15); identity not verified (NA) | Inputs: repo_created=2026-03-15, first_gh=2026-03-25, first_reg=None -> earliest=2026-03-15; gh_ver=v2.9.0, reg_ver=None -> latest=v2.9.0 |
| R9-231 | X-graph | MiroFish | 666ghj/MiroFish | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2025-11-26 (0.39y) | v0.1.2 | 84353 | NONE | 0 GH / 0 OSV | Python | 666ghj | NA: no_package_registered | gh_repo__666ghj_MiroFish; gh_release_latest__mirofish; gh_releases__mirofish; gh_advisories__mirofish; gh_license__mirofish | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-11-26); version <1.0.0 (v0.1.2); licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2025-11-26, first_gh=2025-12-22, first_reg=None -> earliest=2025-11-26; gh_ver=v0.1.2, reg_ver=None -> latest=v0.1.2 |
| R9-232 | X-memory | Graphiti | getzep/graphiti | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-08-08 (1.69y) | v0.31.2 | 32574 | NONE | 1 GH / 2 OSV | Python | getzep | MATCH:  | gh_repo__getzep_graphiti; gh_release_latest__graphiti; gh_releases__graphiti; gh_advisories__graphiti; gh_license__graphiti | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-08-08); version <1.0.0 (v0.31.2) | Inputs: repo_created=2024-08-08, first_gh=2024-08-27, first_reg=None -> earliest=2024-08-08; gh_ver=v0.31.2, reg_ver=None -> latest=v0.31.2 |
| R9-233 | X-memory | mem0 | mem0ai/mem0 | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-06-20 (2.82y) | v2.2.1 | 68487 | NONE | 1 GH / 10 OSV | Python | mem0ai | MATCH:  | gh_repo__mem0ai_mem0; gh_release_latest__mem0; gh_releases__mem0; gh_advisories__mem0; gh_license__mem0 | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-06-20, first_gh=2023-12-30, first_reg=None -> earliest=2023-06-20; gh_ver=v2.2.1, reg_ver=None -> latest=v2.2.1 |
| R9-234 | X-memory | Letta | letta-ai/letta | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-10-11 (2.51y) | 0.16.8 | 25362 | NONE | 0 GH / 2 OSV | NA | letta-ai | MISMATCH: wrapper https://github.com/letta-ai/letta-code vs canonical https://github.com/letta-ai/letta | gh_repo__letta-ai_letta; gh_release_latest__letta; gh_releases__letta; gh_advisories__letta; gh_license__letta | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.16.8); identity not verified (MISMATCH) | Inputs: repo_created=2023-10-11, first_gh=2023-10-26, first_reg=None -> earliest=2023-10-11; gh_ver=0.16.8, reg_ver=None -> latest=0.16.8 |
| R9-235 | X-memory | Cognee | topoteretes/cognee | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-08-16 (2.67y) | v1.6.6 | 33100 | NONE | 1 GH / 2 OSV | Python | topoteretes | MATCH:  | gh_repo__topoteretes_cognee; gh_release_latest__cognee; gh_releases__cognee; gh_advisories__cognee; gh_license__cognee | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-08-16, first_gh=2023-10-08, first_reg=None -> earliest=2023-08-16; gh_ver=v1.6.6, reg_ver=None -> latest=v1.6.6 |
| R9-236 | X-memory | LightRAG | HKUDS/LightRAG | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2024-10-02 (1.54y) | v1.5.7 | 40565 | NONE | 23 GH / 20 OSV | Python | HKUDS | MATCH:  | gh_repo__HKUDS_LightRAG; gh_release_latest__lightrag; gh_releases__lightrag; gh_advisories__lightrag; gh_license__lightrag | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-10-02) | Inputs: repo_created=2024-10-02, first_gh=2024-12-05, first_reg=None -> earliest=2024-10-02; gh_ver=v1.5.7, reg_ver=None -> latest=v1.5.7 |
| R9-237 | X-memory | Microsoft GraphRAG | microsoft/graphrag | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2024-03-27 (2.05y) | v3.3.0 | 36575 | NONE | 0 GH / 0 OSV | Python | microsoft | MATCH:  | gh_repo__microsoft_graphrag; gh_release_latest__graphrag; gh_releases__graphrag; gh_advisories__graphrag; gh_license__graphrag | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2024-03-27, first_gh=2024-07-02, first_reg=None -> earliest=2024-03-27; gh_ver=v3.3.0, reg_ver=None -> latest=v3.3.0 |
| R9-238 | X-memory | Milvus | milvus-io/milvus | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2019-09-16 (6.58y) | v3.0.5 | 46608 | NONE | 9 GH / 0 OSV | Go | milvus-io | NA: no_package_registered | gh_repo__milvus-io_milvus; gh_release_latest__milvus; gh_releases__milvus; gh_advisories__milvus; gh_license__milvus | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | identity not verified (NA) | Inputs: repo_created=2019-09-16, first_gh=2019-10-21, first_reg=None -> earliest=2019-09-16; gh_ver=v3.0.5, reg_ver=None -> latest=v3.0.5 |
| R9-239 | X-memory | Qdrant | qdrant/qdrant | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2020-05-30 (5.88y) | v1.20.0 | 35440 | NONE | 3 GH / 2 OSV | Rust | qdrant | MATCH:  | gh_repo__qdrant_qdrant; gh_release_latest__qdrant; gh_releases__qdrant; gh_advisories__qdrant; gh_license__qdrant | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2020-05-30, first_gh=2021-04-06, first_reg=None -> earliest=2020-05-30; gh_ver=v1.20.0, reg_ver=None -> latest=v1.20.0 |
| R9-240 | X-guard | NeMo Guardrails | NVIDIA-NeMo/Guardrails | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-04-18 (3.0y) | v0.24.1 | 7438 | NONE | 0 GH / 0 OSV | Python | NVIDIA-NeMo | MATCH:  | gh_repo__NVIDIA-NeMo_Guardrails; gh_release_latest__nemo-guardrails; gh_releases__nemo-guardrails; gh_advisories__nemo-guardrails; gh_license__nemo-guardrails | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.24.1) | Inputs: repo_created=2023-04-18, first_gh=2023-06-01, first_reg=None -> earliest=2023-04-18; gh_ver=v0.24.1, reg_ver=None -> latest=v0.24.1 |
| R9-241 | X-guard | Guardrails AI | guardrails-ai/guardrails | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-01-29 (3.21y) | v0.11.0 | 7585 | NONE | 1 GH / 9 OSV | Python | guardrails-ai | MATCH:  | gh_repo__guardrails-ai_guardrails; gh_release_latest__guardrails-ai; gh_releases__guardrails-ai; gh_advisories__guardrails-ai; gh_license__guardrails-ai | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.11.0) | Inputs: repo_created=2023-01-29, first_gh=2023-03-13, first_reg=None -> earliest=2023-01-29; gh_ver=v0.11.0, reg_ver=None -> latest=v0.11.0 |
| R9-242 | X-guard | LLM Guard | protectai/llm-guard | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2023-07-27 (2.72y) | NO_RELEASE | 3220 | archived | 0 GH / 0 OSV | Python | protectai | MATCH:  | gh_repo__protectai_llm-guard; gh_release_latest__llm-guard; gh_releases__llm-guard; gh_advisories__llm-guard; gh_license__llm-guard | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE) | Inputs: repo_created=2023-07-27, first_gh=None, first_reg=None -> earliest=2023-07-27; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-243 | X-guard | Llama Guard | meta-llama/PurpleLlama | PROPRIETARY/UNKNOWN (UNKNOWN) | 2023-12-06 (2.36y) | NO_RELEASE | 4467 | NONE | 0 GH / 0 OSV | Python | meta-llama | NA: unresolved_repo | gh_repo__meta-llama_PurpleLlama; gh_release_latest__llama-guard; gh_releases__llama-guard; gh_advisories__llama-guard; gh_license__llama-guard | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE); licence not permissive/weak-copyleft (PROPRIETARY/UNKNOWN (UNKNOWN)); identity not verified (NA) | Inputs: repo_created=2023-12-06, first_gh=None, first_reg=None -> earliest=2023-12-06; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-244 | X-guard | Invariant | invariantlabs-ai/invariant | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-05-08 (1.94y) | NO_RELEASE | 475 | NONE | 0 GH / 0 OSV | Python | invariantlabs-ai | PACKAGE_NOT_FOUND:  | gh_repo__invariantlabs-ai_invariant; gh_release_latest__invariant; gh_releases__invariant; gh_advisories__invariant; gh_license__invariant | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-05-08); version <1.0.0 (NO_RELEASE); stars <500 (475); identity not verified (PACKAGE_NOT_FOUND) | Inputs: repo_created=2024-05-08, first_gh=None, first_reg=None -> earliest=2024-05-08; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-245 | X-guard | Presidio | data-privacy-stack/presidio | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2018-05-04 (7.95y) | 2.2.366 | 11749 | NONE | 0 GH / 0 OSV | Python | data-privacy-stack | MATCH:  | gh_repo__data-privacy-stack_presidio; gh_release_latest__presidio; gh_releases__presidio; gh_advisories__presidio; gh_license__presidio | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2018-05-04, first_gh=2018-12-18, first_reg=None -> earliest=2018-05-04; gh_ver=2.2.366, reg_ver=None -> latest=2.2.366 |
| R9-246 | X-guard; X-portability | Bifrost | maximhq/bifrost | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2025-03-19 (1.08y) | helm-chart-v2.1.47 | 9398 | NONE | 3 GH / 0 OSV | Go | maximhq | NA: no_package_registered | gh_repo__maximhq_bifrost; gh_release_latest__bifrost; gh_releases__bifrost; gh_advisories__bifrost; gh_license__bifrost | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-03-19); identity not verified (NA) | Inputs: repo_created=2025-03-19, first_gh=2026-08-12, first_reg=None -> earliest=2025-03-19; gh_ver=helm-chart-v2.1.47, reg_ver=None -> latest=helm-chart-v2.1.47 |
| R9-247 | X-eval | inspect-ai | UKGovernmentBEIS/inspect_ai | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2023-11-14 (2.42y) | 0.3.287 | 3187 | NONE | 0 GH / 0 OSV | Python | UKGovernmentBEIS | MATCH:  | gh_repo__UKGovernmentBEIS_inspect_ai; gh_release_latest__inspect-ai; gh_releases__inspect-ai; gh_advisories__inspect-ai; gh_license__inspect-ai | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.3.287) | Inputs: repo_created=2023-11-14, first_gh=2026-10-09, first_reg=None -> earliest=2023-11-14; gh_ver=0.3.287, reg_ver=None -> latest=0.3.287 |
| R9-248 | X-eval | DeepEval | confident-ai/deepeval | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-08-10 (2.68y) | setup-v0.1.0 | 19322 | NONE | 0 GH / 0 OSV | Python | confident-ai | MATCH:  | gh_repo__confident-ai_deepeval; gh_release_latest__deepeval; gh_releases__deepeval; gh_advisories__deepeval; gh_license__deepeval | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (setup-v0.1.0) | Inputs: repo_created=2023-08-10, first_gh=2023-09-24, first_reg=None -> earliest=2023-08-10; gh_ver=setup-v0.1.0, reg_ver=None -> latest=setup-v0.1.0 |
| R9-249 | X-eval | Ragas | vibrantlabsai/ragas | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-05-08 (2.94y) | v0.4.3 | 16247 | NONE | 0 GH / 4 OSV | Python | vibrantlabsai | MATCH:  | gh_repo__vibrantlabsai_ragas; gh_release_latest__ragas; gh_releases__ragas; gh_advisories__ragas; gh_license__ragas | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.4.3) | Inputs: repo_created=2023-05-08, first_gh=2023-05-14, first_reg=None -> earliest=2023-05-08; gh_ver=v0.4.3, reg_ver=None -> latest=v0.4.3 |
| R9-250 | X-eval | lm-evaluation-harness | EleutherAI/lm-evaluation-harness | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2020-08-28 (5.63y) | v0.4.13 | 14409 | NONE | 0 GH / 0 OSV | Python | EleutherAI | MATCH:  | gh_repo__EleutherAI_lm-evaluation-harness; gh_release_latest__lm-evaluation-harness; gh_releases__lm-evaluation-harness; gh_advisories__lm-evaluation-harness; gh_license__lm-evaluation-harness | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (v0.4.13) | Inputs: repo_created=2020-08-28, first_gh=2021-09-02, first_reg=None -> earliest=2020-08-28; gh_ver=v0.4.13, reg_ver=None -> latest=v0.4.13 |
| R9-251 | X-eval | SWE-bench | SWE-bench/SWE-bench | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2023-10-04 (2.53y) | NO_RELEASE | 6150 | NONE | 0 GH / 0 OSV | Python | SWE-bench | MATCH:  | gh_repo__SWE-bench_SWE-bench; gh_release_latest__swe-bench; gh_releases__swe-bench; gh_advisories__swe-bench; gh_license__swe-bench | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (NO_RELEASE) | Inputs: repo_created=2023-10-04, first_gh=None, first_reg=None -> earliest=2023-10-04; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-252 | X-eval | OpenLLMetry | traceloop/openllmetry | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-09-02 (2.62y) | 0.63.0 | 7523 | NONE | 0 GH / 0 OSV | Python | traceloop | MATCH:  | gh_repo__traceloop_openllmetry; gh_release_latest__openllmetry; gh_releases__openllmetry; gh_advisories__openllmetry; gh_license__openllmetry | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (0.63.0) | Inputs: repo_created=2023-09-02, first_gh=2023-10-30, first_reg=None -> earliest=2023-09-02; gh_ver=0.63.0, reg_ver=None -> latest=0.63.0 |
| R9-253 | X-eval | Langfuse | langfuse/langfuse | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2023-05-18 (2.91y) | v4.76.0 | 37076 | NONE | 4 GH / 0 OSV | TypeScript | langfuse | MATCH:  | gh_repo__langfuse_langfuse; gh_release_latest__langfuse; gh_releases__langfuse; gh_advisories__langfuse; gh_license__langfuse | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-05-18, first_gh=2025-07-30, first_reg=None -> earliest=2023-05-18; gh_ver=v4.76.0, reg_ver=None -> latest=v4.76.0 |
| R9-254 | X-eval | Phoenix | Arize-ai/phoenix | PERMISSIVE (NOASSERTION) | 2022-11-09 (3.43y) | @arizeai/phoenix-cli@1.20.0 | 12168 | NONE | 0 GH / 0 OSV | Python | Arize-ai | MATCH:  | gh_repo__Arize-ai_phoenix; gh_release_latest__phoenix; gh_releases__phoenix; gh_advisories__phoenix; gh_license__phoenix | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2022-11-09, first_gh=2026-01-27, first_reg=None -> earliest=2022-11-09; gh_ver=@arizeai/phoenix-cli@1.20.0, reg_ver=None -> latest=@arizeai/phoenix-cli@1.20.0 |
| R9-255 | X-eval | MLflow | mlflow/mlflow | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2018-06-05 (7.86y) | model-catalog/latest | 28695 | NONE | 12 GH / 167 OSV | Python | mlflow | MATCH:  | gh_repo__mlflow_mlflow; gh_release_latest__mlflow; gh_releases__mlflow; gh_advisories__mlflow; gh_license__mlflow | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (model-catalog/latest) | Inputs: repo_created=2018-06-05, first_gh=2018-06-27, first_reg=None -> earliest=2018-06-05; gh_ver=model-catalog/latest, reg_ver=None -> latest=model-catalog/latest |
| R9-256 | X-eval | Opik | comet-ml/opik | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-05-10 (2.93y) | 2.2.142 | 23211 | NONE | 3 GH / 0 OSV | Python | comet-ml | MATCH:  | gh_repo__comet-ml_opik; gh_release_latest__opik; gh_releases__opik; gh_advisories__opik; gh_license__opik | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-05-10, first_gh=2023-11-21, first_reg=None -> earliest=2023-05-10; gh_ver=2.2.142, reg_ver=None -> latest=2.2.142 |
| R9-257 | X-portability | LiteLLM | BerriAI/litellm | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2023-07-27 (2.72y) | v1.108.1 | 62802 | NONE | 18 GH / 85 OSV | Python | BerriAI | MATCH:  | gh_repo__BerriAI_litellm; gh_release_latest__litellm; gh_releases__litellm; gh_advisories__litellm; gh_license__litellm | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-07-27, first_gh=2026-03-10, first_reg=None -> earliest=2023-07-27; gh_ver=v1.108.1, reg_ver=None -> latest=v1.108.1 |
| R9-258 | X-portability | any-llm | mozilla-ai/any-llm | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2025-07-14 (0.76y) | 1.46.0 | 2246 | NONE | 0 GH / 0 OSV | Python | mozilla-ai | NA: unresolved_repo | gh_repo__mozilla-ai_any-llm; gh_release_latest__any-llm; gh_releases__any-llm; gh_advisories__any-llm; gh_license__any-llm | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-07-14); identity not verified (NA) | Inputs: repo_created=2025-07-14, first_gh=2025-08-05, first_reg=None -> earliest=2025-07-14; gh_ver=1.46.0, reg_ver=None -> latest=1.46.0 |
| R9-259 | X-portability | Instructor | 567-labs/instructor | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2023-06-14 (2.84y) | v1.17.0 | 14098 | NONE | 0 GH / 0 OSV | Python | 567-labs | MATCH:  | gh_repo__567-labs_instructor; gh_release_latest__instructor; gh_releases__instructor; gh_advisories__instructor; gh_license__instructor | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-06-14, first_gh=2023-06-23, first_reg=None -> earliest=2023-06-14; gh_ver=v1.17.0, reg_ver=None -> latest=v1.17.0 |
| R9-260 | X-portability | Outlines | dottxt-ai/outlines | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-03-17 (3.08y) | 1.3.3 | 16004 | NONE | 0 GH / 0 OSV | Python | dottxt-ai | MATCH:  | gh_repo__dottxt-ai_outlines; gh_release_latest__outlines; gh_releases__outlines; gh_advisories__outlines; gh_license__outlines | CL | CL | CL | CL | MATURE_OBJECTIVE_PASS | None | Inputs: repo_created=2023-03-17, first_gh=2023-05-25, first_reg=None -> earliest=2023-03-17; gh_ver=1.3.3, reg_ver=None -> latest=1.3.3 |
| R9-261 | X-portability | BAML | BoundaryML/baml | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2023-10-06 (2.53y) | baml-wrapper-0.3.1 | 9485 | NONE | 0 GH / 0 OSV | Rust | BoundaryML | MATCH:  | gh_repo__BoundaryML_baml; gh_release_latest__baml; gh_releases__baml; gh_advisories__baml; gh_license__baml | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | version <1.0.0 (baml-wrapper-0.3.1) | Inputs: repo_created=2023-10-06, first_gh=2026-06-10, first_reg=None -> earliest=2023-10-06; gh_ver=baml-wrapper-0.3.1, reg_ver=None -> latest=baml-wrapper-0.3.1 |
| R9-262 | X-portability | Pydantic AI | pydantic/pydantic-ai | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2024-06-21 (1.82y) | clai2-bleeding | 21045 | NONE | 29 GH / 28 OSV | Python | pydantic | MATCH:  | gh_repo__pydantic_pydantic-ai; gh_release_latest__pydantic-ai; gh_releases__pydantic-ai; gh_advisories__pydantic-ai; gh_license__pydantic-ai | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-06-21); version <1.0.0 (clai2-bleeding) | Inputs: repo_created=2024-06-21, first_gh=2025-04-09, first_reg=None -> earliest=2024-06-21; gh_ver=clai2-bleeding, reg_ver=None -> latest=clai2-bleeding |
| R9-263 | X-portability | A2A protocol | a2aproject/A2A | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2025-03-25 (1.06y) | v1.0.1 | 26432 | NONE | 0 GH / 0 OSV | Shell | a2aproject | NA: no_package_registered | gh_repo__a2aproject_A2A; gh_release_latest__a2a-protocol; gh_releases__a2a-protocol; gh_advisories__a2a-protocol; gh_license__a2a-protocol | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-03-25); identity not verified (NA) | Inputs: repo_created=2025-03-25, first_gh=2025-05-27, first_reg=None -> earliest=2025-03-25; gh_ver=v1.0.1, reg_ver=None -> latest=v1.0.1 |
| R9-264 | X-portability | AGENTS.md convention | agentsmd/agents.md | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-08-19 (0.66y) | NO_RELEASE | 25352 | NONE | 0 GH / 0 OSV | TypeScript | agentsmd | NA: unresolved_repo | gh_repo__agentsmd_agents.md; gh_release_latest__agents-md; gh_releases__agents-md; gh_advisories__agents-md; gh_license__agents-md | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-08-19); version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2025-08-19, first_gh=None, first_reg=None -> earliest=2025-08-19; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-265 | X-portability | Model Context Protocol | modelcontextprotocol/modelcontextprotocol | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-09-24 (1.56y) | 2026-07-28 | 9624 | NONE | 1 GH / 0 OSV | TypeScript | modelcontextprotocol | NA: no_package_registered | gh_repo__modelcontextprotocol_modelcontextprotocol; gh_release_latest__mcp-spec; gh_releases__mcp-spec; gh_advisories__mcp-spec; gh_license__mcp-spec | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-09-24); version <1.0.0 (2026-07-28); identity not verified (NA) | Inputs: repo_created=2024-09-24, first_gh=2024-11-06, first_reg=None -> earliest=2024-09-24; gh_ver=2026-07-28, reg_ver=None -> latest=2026-07-28 |
| R9-266 | X-portability | opencodex | lidge-jun/opencodex | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-06-18 (-0.17y) | v2.97.0 | 18242 | NONE | 0 GH / 0 OSV | TypeScript | lidge-jun | NA: no_package_registered | gh_repo__lidge-jun_opencodex; gh_release_latest__opencodex; gh_releases__opencodex; gh_advisories__opencodex; gh_license__opencodex | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-06-18); identity not verified (NA) | Inputs: repo_created=2026-06-18, first_gh=2026-06-19, first_reg=None -> earliest=2026-06-18; gh_ver=v2.97.0, reg_ver=None -> latest=v2.97.0 |
| R9-267 | X-portability | Plano | katanemo/plano | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2024-07-09 (1.77y) | 0.4.39 | 7110 | NONE | 0 GH / 0 OSV | Rust | katanemo | NA: no_package_registered | gh_repo__katanemo_plano; gh_release_latest__plano; gh_releases__plano; gh_advisories__plano; gh_license__plano | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2024-07-09); version <1.0.0 (0.4.39); identity not verified (NA) | Inputs: repo_created=2024-07-09, first_gh=2024-10-31, first_reg=None -> earliest=2024-07-09; gh_ver=0.4.39, reg_ver=None -> latest=0.4.39 |
| R9-268 | X-workflow | GSD Core (open-gsd) | open-gsd/gsd-core | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-05-22 (-0.1y) | v1.20.1 | 11273 | NONE | 0 GH / 0 OSV | JavaScript | open-gsd | NA: no_package_registered | gh_repo__open-gsd_gsd-core; gh_release_latest__open-gsd; gh_releases__open-gsd; gh_advisories__open-gsd; gh_license__open-gsd | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-05-22); identity not verified (NA) | Inputs: repo_created=2026-05-22, first_gh=2026-05-22, first_reg=None -> earliest=2026-05-22; gh_ver=v1.20.1, reg_ver=None -> latest=v1.20.1 |
| R9-269 | X-workflow | get-shit-done (gsd-build) | gsd-build/get-shit-done | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-12-14 (0.34y) | v1.43.0-rc2 | 64159 | archived; moved_to=open-gsd/gsd-core | 0 GH / 0 OSV | JavaScript | gsd-build | NA: no_package_registered | gh_repo__gsd-build_get-shit-done; gh_release_latest__gsd-build; gh_releases__gsd-build; gh_advisories__gsd-build; gh_license__gsd-build | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-12-14); identity not verified (NA) | Inputs: repo_created=2025-12-14, first_gh=2026-01-22, first_reg=None -> earliest=2025-12-14; gh_ver=v1.43.0-rc2, reg_ver=None -> latest=v1.43.0-rc2 |
| R9-270 | X-workflow | get-shit-done (jmathai) | jmathai/get-shit-done | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-03-17 (0.08y) | NO_RELEASE | 0 | fork_of=gsd-build/get-shit-done | 0 GH / 0 OSV | NA | jmathai | NA: no_package_registered | gh_repo__jmathai_get-shit-done; gh_release_latest__jmathai-gsd; gh_releases__jmathai-gsd; gh_advisories__jmathai-gsd; gh_license__jmathai-gsd | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-03-17); version <1.0.0 (NO_RELEASE); stars <500 (0); identity not verified (NA) | Inputs: repo_created=2026-03-17, first_gh=None, first_reg=None -> earliest=2026-03-17; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-271 | X-workflow | get-shit-done (ludicrypt) | ludicrypt/get-shit-done | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-01-20 (0.24y) | NO_RELEASE | 0 | fork_of=gsd-build/get-shit-done | 0 GH / 0 OSV | NA | ludicrypt | NA: no_package_registered | gh_repo__ludicrypt_get-shit-done; gh_release_latest__ludicrypt-gsd; gh_releases__ludicrypt-gsd; gh_advisories__ludicrypt-gsd; gh_license__ludicrypt-gsd | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-01-20); version <1.0.0 (NO_RELEASE); stars <500 (0); identity not verified (NA) | Inputs: repo_created=2026-01-20, first_gh=None, first_reg=None -> earliest=2026-01-20; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-272 | X-workflow | get-shit-done (itsjwill) | UNRESOLVED | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | NA | NA: unresolved_repo | gh_repo__UNRESOLVED; gh_release_latest__itsjwill-gsd; gh_releases__itsjwill-gsd; gh_advisories__itsjwill-gsd; gh_license__itsjwill-gsd | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-273 | X-workflow | Geoffrey Huntley technique (ghuntley/work) | UNRESOLVED | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | NA | NA: unresolved_repo | gh_repo__UNRESOLVED; gh_release_latest__ghuntley-work; gh_releases__ghuntley-work; gh_advisories__ghuntley-work; gh_license__ghuntley-work | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-274 | X-workflow | Ralph (snarktank) | snarktank/ralph | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-01-07 (0.27y) | NO_RELEASE | 22122 | NONE | 0 GH / 0 OSV | TypeScript | snarktank | NA: no_package_registered | gh_repo__snarktank_ralph; gh_release_latest__snarktank-ralph; gh_releases__snarktank-ralph; gh_advisories__snarktank-ralph; gh_license__snarktank-ralph | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-01-07); version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2026-01-07, first_gh=None, first_reg=None -> earliest=2026-01-07; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-275 | X-workflow | Claude Plugins ralph-loop | anthropics/claude-plugins-official | PERMISSIVE (Apache-2.0) [Quote: "Apache License"] | 2025-11-20 (0.4y) | NO_RELEASE | 46240 | NONE | 0 GH / 0 OSV | Python | anthropics | NA: no_package_registered | gh_repo__anthropics_claude-plugins-official; gh_release_latest__claude-plugins-ralph; gh_releases__claude-plugins-ralph; gh_advisories__claude-plugins-ralph; gh_license__claude-plugins-ralph | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-11-20); version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2025-11-20, first_gh=None, first_reg=None -> earliest=2025-11-20; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-276 | X-workflow | ralph-claude-code (frankbria) | frankbria/ralph-claude-code | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-08-27 (0.64y) | NO_RELEASE | 9719 | NONE | 0 GH / 0 OSV | Shell | frankbria | NA: no_package_registered | gh_repo__frankbria_ralph-claude-code; gh_release_latest__frankbria-ralph; gh_releases__frankbria-ralph; gh_advisories__frankbria-ralph; gh_license__frankbria-ralph | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-08-27); version <1.0.0 (NO_RELEASE); identity not verified (NA) | Inputs: repo_created=2025-08-27, first_gh=None, first_reg=None -> earliest=2025-08-27; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-277 | X-workflow | Ralphy (michaelshimeles) | michaelshimeles/ralphy | MISSING (NONE) | 2026-01-15 (0.25y) | NO_RELEASE | 2983 | NONE | 0 GH / 0 OSV | TypeScript | michaelshimeles | NA: no_package_registered | gh_repo__michaelshimeles_ralphy; gh_release_latest__michaelshimeles-ralphy; gh_releases__michaelshimeles-ralphy; gh_advisories__michaelshimeles-ralphy; gh_license__michaelshimeles-ralphy | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-01-15); version <1.0.0 (NO_RELEASE); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=2026-01-15, first_gh=None, first_reg=None -> earliest=2026-01-15; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-278 | X-workflow | ralph-workflow | Ralph-Workflow/Ralph-Workflow | STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"] | 2026-01-13 (0.25y) | NO_RELEASE | 5 | NONE | 0 GH / 0 OSV | Python | Ralph-Workflow | NA: unresolved_repo | gh_repo__Ralph-Workflow_Ralph-Workflow; gh_release_latest__ralph-workflow; gh_releases__ralph-workflow; gh_advisories__ralph-workflow; gh_license__ralph-workflow | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-01-13); version <1.0.0 (NO_RELEASE); stars <500 (5); licence not permissive/weak-copyleft (STRONG-COPYLEFT (GPL-3.0) [Quote: "GNU General Public License"]); identity not verified (NA) | Inputs: repo_created=2026-01-13, first_gh=None, first_reg=None -> earliest=2026-01-13; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-279 | X-workflow | ralphify | computerlovetech/ralphify | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-03-08 (0.11y) | v0.4.0b3 | 70 | NONE | 0 GH / 0 OSV | Python | computerlovetech | NA: unresolved_repo | gh_repo__computerlovetech_ralphify; gh_release_latest__ralphify; gh_releases__ralphify; gh_advisories__ralphify; gh_license__ralphify | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-03-08); version <1.0.0 (v0.4.0b3); stars <500 (70); identity not verified (NA) | Inputs: repo_created=2026-03-08, first_gh=2026-03-09, first_reg=None -> earliest=2026-03-08; gh_ver=v0.4.0b3, reg_ver=None -> latest=v0.4.0b3 |
| R9-280 | X-workflow | open-ralph-wiggum | UNRESOLVED | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | NA | NA: unresolved_repo | gh_repo__UNRESOLVED; gh_release_latest__open-ralph-wiggum; gh_releases__open-ralph-wiggum; gh_advisories__open-ralph-wiggum; gh_license__open-ralph-wiggum | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-281 | X-workflow | awesome-ralph (dabit3 fork) | dabit3/awesome-ralph | MISSING (NONE) | 2026-01-19 (0.24y) | NO_RELEASE | 5 | fork_of=snwfdhmp/awesome-ralph | 0 GH / 0 OSV | NA | dabit3 | NA: no_package_registered | gh_repo__dabit3_awesome-ralph; gh_release_latest__awesome-ralph; gh_releases__awesome-ralph; gh_advisories__awesome-ralph; gh_license__awesome-ralph | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-01-19); version <1.0.0 (NO_RELEASE); stars <500 (5); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=2026-01-19, first_gh=None, first_reg=None -> earliest=2026-01-19; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-282 | X-workflow | GitHub Spec Kit | github/spec-kit | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-08-21 (0.65y) | v1.3.1 | 147960 | NONE | 0 GH / 0 OSV | Python | github | NA: no_package_registered | gh_repo__github_spec-kit; gh_release_latest__github-spec-kit; gh_releases__github-spec-kit; gh_advisories__github-spec-kit; gh_license__github-spec-kit | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-08-21); identity not verified (NA) | Inputs: repo_created=2025-08-21, first_gh=2025-08-22, first_reg=None -> earliest=2025-08-21; gh_ver=v1.3.1, reg_ver=None -> latest=v1.3.1 |
| R9-283 | X-workflow | OpenSpec | Fission-AI/OpenSpec | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-08-05 (0.7y) | v1.16.0 | 74077 | NONE | 0 GH / 0 OSV | TypeScript | Fission-AI | NA: no_package_registered | gh_repo__Fission-AI_OpenSpec; gh_release_latest__openspec; gh_releases__openspec; gh_advisories__openspec; gh_license__openspec | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-08-05); identity not verified (NA) | Inputs: repo_created=2025-08-05, first_gh=2025-09-06, first_reg=None -> earliest=2025-08-05; gh_ver=v1.16.0, reg_ver=None -> latest=v1.16.0 |
| R9-284 | X-workflow | Superpowers | obra/superpowers | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-10-09 (0.52y) | v7.0.2 | 313126 | NONE | 0 GH / 0 OSV | Shell | obra | NA: no_package_registered | gh_repo__obra_superpowers; gh_release_latest__superpowers; gh_releases__superpowers; gh_advisories__superpowers; gh_license__superpowers | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-10-09); identity not verified (NA) | Inputs: repo_created=2025-10-09, first_gh=2026-03-17, first_reg=None -> earliest=2025-10-09; gh_ver=v7.0.2, reg_ver=None -> latest=v7.0.2 |
| R9-285 | X-workflow | Agent OS | buildermethods/agent-os | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-07-16 (0.75y) | v3.0.0 | 5584 | NONE | 0 GH / 0 OSV | Shell | buildermethods | NA: unresolved_repo | gh_repo__buildermethods_agent-os; gh_release_latest__agent-os; gh_releases__agent-os; gh_advisories__agent-os; gh_license__agent-os | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-07-16); identity not verified (NA) | Inputs: repo_created=2025-07-16, first_gh=2025-07-29, first_reg=None -> earliest=2025-07-16; gh_ver=v3.0.0, reg_ver=None -> latest=v3.0.0 |
| R9-286 | X-workflow | SuperClaude | SuperClaude-Org/SuperClaude_Framework | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-06-22 (0.82y) | v4.3.0 | 23929 | NONE | 0 GH / 0 OSV | Python | SuperClaude-Org | NA: unresolved_repo | gh_repo__SuperClaude-Org_SuperClaude_Framework; gh_release_latest__superclaude; gh_releases__superclaude; gh_advisories__superclaude; gh_license__superclaude | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-06-22); identity not verified (NA) | Inputs: repo_created=2025-06-22, first_gh=2025-09-06, first_reg=None -> earliest=2025-06-22; gh_ver=v4.3.0, reg_ver=None -> latest=v4.3.0 |
| R9-287 | X-workflow | ruflo (formerly claude-flow) | ruvnet/ruflo | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-06-02 (0.87y) | v3.72.0 | 81009 | NONE | 9 GH / 0 OSV | TypeScript | ruvnet | NA: no_package_registered | gh_repo__ruvnet_ruflo; gh_release_latest__ruflo; gh_releases__ruflo; gh_advisories__ruflo; gh_license__ruflo | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-06-02); identity not verified (NA) | Inputs: repo_created=2025-06-02, first_gh=2025-09-26, first_reg=None -> earliest=2025-06-02; gh_ver=v3.72.0, reg_ver=None -> latest=v3.72.0 |
| R9-288 | X-workflow | Paperclip | paperclipai/paperclip | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-03-02 (0.12y) | v2026.1023.0 | 111503 | NONE | 12 GH / 0 OSV | TypeScript | paperclipai | NA: no_package_registered | gh_repo__paperclipai_paperclip; gh_release_latest__paperclip; gh_releases__paperclip; gh_advisories__paperclip; gh_license__paperclip | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-03-02); identity not verified (NA) | Inputs: repo_created=2026-03-02, first_gh=2026-03-09, first_reg=None -> earliest=2026-03-02; gh_ver=v2026.1023.0, reg_ver=None -> latest=v2026.1023.0 |
| R9-289 | X-workflow | PentaGI | vxcontrol/pentagi | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2025-01-06 (1.27y) | v2.2.0 | 33463 | NONE | 0 GH / 0 OSV | Go | vxcontrol | NA: no_package_registered | gh_repo__vxcontrol_pentagi; gh_release_latest__pentagi; gh_releases__pentagi; gh_advisories__pentagi; gh_license__pentagi | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2025-01-06); identity not verified (NA) | Inputs: repo_created=2025-01-06, first_gh=2025-01-07, first_reg=None -> earliest=2025-01-06; gh_ver=v2.2.0, reg_ver=None -> latest=v2.2.0 |
| R9-290 | X-workflow | planning-with-files | OthmanAdi/planning-with-files | PERMISSIVE (MIT) [Quote: "Permission is hereby granted, free of charge"] | 2026-01-03 (0.28y) | v3.28.0 | 27914 | NONE | 0 GH / 0 OSV | Shell | OthmanAdi | NA: no_package_registered | gh_repo__OthmanAdi_planning-with-files; gh_release_latest__planning-with-files; gh_releases__planning-with-files; gh_advisories__planning-with-files; gh_license__planning-with-files | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=2026-01-03); identity not verified (NA) | Inputs: repo_created=2026-01-03, first_gh=2026-01-08, first_reg=None -> earliest=2026-01-03; gh_ver=v3.28.0, reg_ver=None -> latest=v3.28.0 |
| R9-291 | X-workflow | AWS Kiro | closed/aws-kiro | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | closed | NA: closed_vendor | gh_repo__closed_aws-kiro; gh_release_latest__aws-kiro; gh_releases__aws-kiro; gh_advisories__aws-kiro; gh_license__aws-kiro | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-292 | X-workflow | Tessl | closed/tessl | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | closed | NA: closed_vendor | gh_repo__closed_tessl; gh_release_latest__tessl; gh_releases__tessl; gh_advisories__tessl; gh_license__tessl | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-293 | X-workflow | Cursor Plan Mode | closed/cursor-plan-mode | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | closed | NA: closed_vendor | gh_repo__closed_cursor-plan-mode; gh_release_latest__cursor-plan-mode; gh_releases__cursor-plan-mode; gh_advisories__cursor-plan-mode; gh_license__cursor-plan-mode | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-294 | P9 | Greptile | closed/greptile | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | closed | NA: closed_vendor | gh_repo__closed_greptile; gh_release_latest__greptile; gh_releases__greptile; gh_advisories__greptile; gh_license__greptile | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-295 | P0 | Augment Intent | closed/augment-intent | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | closed | NA: closed_vendor | gh_repo__closed_augment-intent; gh_release_latest__augment-intent; gh_releases__augment-intent; gh_advisories__augment-intent; gh_license__augment-intent | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (NA) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |
| R9-296 | P7 | sclass-does-not-exist-12345 | sclass-test/non-existent-pkg | MISSING (NONE) | NO_DATE (NA) | NO_RELEASE | NA | NONE | 0 GH / 0 OSV | NA | sclass-test | PACKAGE_NOT_FOUND:  | gh_repo__sclass-test_non-existent-pkg; gh_release_latest__non-existent-pkg-control; gh_releases__non-existent-pkg-control; gh_advisories__non-existent-pkg-control; gh_license__non-existent-pkg-control | CL | CL | CL | CL | MATURE_OBJECTIVE_FAIL | age <2y (earliest=NO_DATE); version <1.0.0 (NO_RELEASE); stars <500 (NA); pushed >1y ago (NA); licence not permissive/weak-copyleft (MISSING (NONE)); identity not verified (PACKAGE_NOT_FOUND) | Inputs: repo_created=None, first_gh=None, first_reg=None -> earliest=NO_DATE; gh_ver=None, reg_ver=None -> latest=NO_RELEASE |


**R32 Sweep Summary Counts:** Total evaluated: 231; MATURE_OBJECTIVE_PASS: 60; MATURE_OBJECTIVE_FAIL: 171.
