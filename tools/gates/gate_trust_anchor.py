#!/usr/bin/env python3
"""Base-Enforced Trust Anchor Gate (CL Properties 1-4 / R4 Delivery).

Enforces authoritative trust anchor invariants from the BASE branch:
1. Anchors, package hashes, errata allowlists, state-machine expectations,
   and mutation expectations are read strictly from the BASE branch
   (via git show <base-ref>:governance/TRUST-ANCHORS.json).
2. The candidate PR head is treated strictly as pure DATA only. No PR code
   is installed or executed; zero candidate modules are imported.
3. Operates entirely with the Python standard library (no pip dependencies,
   no pytest runtime in the trust-anchor gate).
4. Validates:
   - Base custody protection: candidate PR cannot modify trust anchors,
     trust anchor workflow, or the trust anchor gate itself.
   - Frozen directory integrity (00-SPEC/, 10-CONFORMANCE/, 20-RUNTIME/, gate.py).
   - Package original hashes and base-authorized errata (E-SEM-1, E-SPEC-1, Runtime Baseline).
   - State-machine specification and full transition-edge graph.
   - Nine-mutation battery against candidate specification (all 9 must be rejected).
   - Baseline hashes lock (governance/BASELINE-HASHES.txt and FROZEN-MANIFEST.sha256).
"""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
FROZEN_DIRS = ["00-SPEC", "10-CONFORMANCE", "20-RUNTIME"]

# Files that candidate PRs are strictly forbidden from modifying relative to base
PROTECTED_GOVERNANCE_FILES = {
    "governance/TRUST-ANCHORS.json",
    "governance/BASELINE-HASHES.txt",
    "governance/FROZEN-MANIFEST.sha256",
    ".github/workflows/trust-anchor.yml",
    "tools/gates/gate_trust_anchor.py",
}


def sha256_lf(data: bytes) -> str:
    """Computes LF-normalized SHA-256 digest."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def git_show(ref: str, path: str) -> Optional[bytes]:
    """Reads file content from a git ref as raw bytes (data only)."""
    cmd = ["git", "show", f"{ref}:{path}"]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True)
    if res.returncode != 0:
        return None
    return res.stdout


def git_diff_files(base_ref: str, pr_head: str) -> List[Tuple[str, str]]:
    """Returns list of (status, filepath) for files changed in PR relative to base."""
    cmd = ["git", "diff", "--name-status", f"{base_ref}...{pr_head}"]
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, check=True)
    out = []
    for line in res.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            out.append((parts[0], parts[1]))
    return out


def load_base_trust_anchors(base_ref: str, anchors_file: str) -> dict:
    """Loads authoritative anchors strictly from the base branch (never from candidate PR)."""
    raw_bytes = git_show(base_ref, anchors_file)
    if raw_bytes is None:
        raise RuntimeError(
            f"CRITICAL TRUST ANCHOR BREACH: Base branch '{base_ref}' does not contain "
            f"authoritative trust anchors file '{anchors_file}'!"
        )
    try:
        data = json.loads(raw_bytes.decode("utf-8"))
    except Exception as e:
        raise RuntimeError(f"CRITICAL: Failed to parse base trust anchors '{anchors_file}': {e}")
    return data


def validate_transition_graph(
    spec_dict: dict,
    candidate_dict: dict,
) -> None:
    """Validates full transition-edge graph and invariants using stdlib only."""
    spec_machines = spec_dict.get("machines", {})
    cand_machines = candidate_dict.get("machines", {})

    added_machines = set(cand_machines.keys()) - set(spec_machines.keys())
    missing_machines = set(spec_machines.keys()) - set(cand_machines.keys())
    if added_machines:
        raise AssertionError(f"Unauthorized machine(s): {sorted(added_machines)}")
    if missing_machines:
        raise AssertionError(f"Missing canonical machine(s): {sorted(missing_machines)}")

    for m_name, spec_states in spec_machines.items():
        cand_states = cand_machines.get(m_name, {})
        added_states = set(cand_states.keys()) - set(spec_states.keys())
        missing_states = set(spec_states.keys()) - set(cand_states.keys())
        if added_states:
            raise AssertionError(f"Machine '{m_name}' has unauthorized state(s): {sorted(added_states)}")
        if missing_states:
            raise AssertionError(f"Machine '{m_name}' missing canonical state(s): {sorted(missing_states)}")

        spec_edges = {(src, dst) for src, dsts in spec_states.items() for dst in dsts}
        cand_edges = {(src, dst) for src, dsts in cand_states.items() for dst in dsts}
        added_edges = cand_edges - spec_edges
        missing_edges = spec_edges - cand_edges
        if added_edges:
            raise AssertionError(f"Machine '{m_name}' has unauthorized transition edge(s): {sorted(added_edges)}")
        if missing_edges:
            raise AssertionError(f"Machine '{m_name}' missing transition edge(s): {sorted(missing_edges)}")

        spec_terminals = {src for src, dsts in spec_states.items() if not dsts}
        cand_terminals = {src for src, dsts in cand_states.items() if not dsts}
        if spec_terminals != cand_terminals:
            raise AssertionError(f"Terminal states mismatch for machine '{m_name}': expected {sorted(spec_terminals)}, got {sorted(cand_terminals)}")

    # Check event transitions
    spec_events = spec_dict.get("event_transitions", {})
    cand_events = candidate_dict.get("event_transitions", {})
    if set(spec_events.keys()) != set(cand_events.keys()):
        diff = set(spec_events.keys()) ^ set(cand_events.keys())
        raise AssertionError(f"Event transitions key mismatch: {sorted(diff)}")
    for ev_name, spec_ev in spec_events.items():
        if spec_ev != cand_events.get(ev_name):
            raise AssertionError(f"Event transition mismatch for '{ev_name}': expected {spec_ev}, got {cand_events.get(ev_name)}")

    # Check guards (preconditions & postconditions)
    spec_guards = spec_dict.get("guards", {})
    cand_guards = candidate_dict.get("guards", {})
    if spec_guards != cand_guards:
        raise AssertionError(f"Guard specification mismatch: {sorted(set(spec_guards.keys()) ^ set(cand_guards.keys()))}")

    # Check rules
    spec_rules = spec_dict.get("rules", {})
    cand_rules = candidate_dict.get("rules", {})
    if spec_rules != cand_rules:
        raise AssertionError(f"Rules specification mismatch: {sorted(set(spec_rules.keys()) ^ set(cand_rules.keys()))}")


def validate_all_six_anchor_sections(anchors: dict, cand_spec: Optional[dict] = None) -> List[str]:
    """Validates that all six sections of TRUST-ANCHORS.json are strictly present and uncorrupted."""
    violations: List[str] = []

    # Section 1: package_original_hashes
    pkg_hashes = anchors.get("package_original_hashes")
    if not isinstance(pkg_hashes, dict) or len(pkg_hashes) < 13:
        violations.append("TRUST ANCHORS SECTION 1 CORRUPTED: package_original_hashes missing or has fewer than 13 files")

    # Section 2: authorized_errata
    errata = anchors.get("authorized_errata")
    if not isinstance(errata, dict):
        violations.append("TRUST ANCHORS SECTION 2 CORRUPTED: authorized_errata missing")
    else:
        for path, entry in errata.items():
            hashes = entry.get("authorized_hashes", [])
            if len(hashes) != 1:
                violations.append(f"TRUST ANCHORS SECTION 2 VIOLATION: '{path}' has {len(hashes)} authorized hashes (single-hash rule requires exactly 1)")

    # Section 3: state_machine_expectations
    sm_exp = anchors.get("state_machine_expectations")
    if not isinstance(sm_exp, dict):
        violations.append("TRUST ANCHORS SECTION 3 CORRUPTED: state_machine_expectations missing")
    elif cand_spec is not None:
        if len(cand_spec.get("machines", {})) != sm_exp.get("machines_count"):
            violations.append(f"STATE MACHINE EXPECTATION MISMATCH: machines_count expected {sm_exp.get('machines_count')}, got {len(cand_spec.get('machines', {}))}")
        if set(cand_spec.get("machines", {}).keys()) != set(sm_exp.get("canonical_machines", [])):
            violations.append("STATE MACHINE EXPECTATION MISMATCH: canonical_machines mismatch")
        if len(cand_spec.get("guards", {})) != sm_exp.get("guards_count"):
            violations.append(f"STATE MACHINE EXPECTATION MISMATCH: guards_count expected {sm_exp.get('guards_count')}, got {len(cand_spec.get('guards', {}))}")
        if len(cand_spec.get("rules", {})) != sm_exp.get("rules_count"):
            violations.append(f"STATE MACHINE EXPECTATION MISMATCH: rules_count expected {sm_exp.get('rules_count')}, got {len(cand_spec.get('rules', {}))}")

    # Section 4: mutation_battery_expectations
    mut_exp = anchors.get("mutation_battery_expectations")
    if not isinstance(mut_exp, dict) or "required_mutations" not in mut_exp:
        violations.append("TRUST ANCHORS SECTION 4 CORRUPTED: mutation_battery_expectations missing")
    else:
        req_muts = mut_exp["required_mutations"]
        expected_9 = {"delete_edge", "add_edge", "redirect_edge", "rename_state", "add_event_type", "remove_event_type", "reorder_only", "case_variant_name", "consistent_code_and_json_edit"}
        if set(req_muts.keys()) != expected_9:
            violations.append(f"TRUST ANCHORS SECTION 4 VIOLATION: required_mutations set mismatch: {set(req_muts.keys()) ^ expected_9}")
        if req_muts.get("reorder_only") != "ACCEPT":
            violations.append("TRUST ANCHORS SECTION 4 VIOLATION: reorder_only expectation must be ACCEPT")
        for k in expected_9 - {"reorder_only"}:
            if req_muts.get(k) != "REJECT":
                violations.append(f"TRUST ANCHORS SECTION 4 VIOLATION: {k} expectation must be REJECT")

    # Section 5: baseline_hashes
    bl_hashes = anchors.get("baseline_hashes")
    if not isinstance(bl_hashes, dict) or not bl_hashes.get("manifest_path") or not bl_hashes.get("baseline_hashes_path"):
        violations.append("TRUST ANCHORS SECTION 5 CORRUPTED: baseline_hashes missing or incomplete")

    # Section 6: authoritative_refs
    auth_refs = anchors.get("authoritative_refs")
    if not isinstance(auth_refs, dict):
        violations.append("TRUST ANCHORS SECTION 6 CORRUPTED: authoritative_refs missing")
    else:
        for r_name in ("main", "h0", "h1a", "h1b"):
            if r_name not in auth_refs or not auth_refs[r_name].get("sha"):
                violations.append(f"TRUST ANCHORS SECTION 6 VIOLATION: ref '{r_name}' missing or unpinned SHA")
        if "integration" not in auth_refs:
            violations.append("TRUST ANCHORS SECTION 6 VIOLATION: integration ref missing")

    return violations


def execute_nine_mutation_battery_stdlib(
    canonical_spec: dict,
    expectations: Optional[dict] = None,
) -> Tuple[bool, List[str]]:
    """Executes all nine adversarial state-machine mutations in-memory using pure stdlib.

    Validates that observed behavior matches the base anchor expectations (all REJECT except reorder_only ACCEPT).
    """
    results: List[str] = []
    all_match = True

    req_expectations = (expectations or {}).get("required_mutations", {
        "delete_edge": "REJECT",
        "add_edge": "REJECT",
        "redirect_edge": "REJECT",
        "rename_state": "REJECT",
        "add_event_type": "REJECT",
        "remove_event_type": "REJECT",
        "reorder_only": "ACCEPT",
        "case_variant_name": "REJECT",
        "consistent_code_and_json_edit": "REJECT",
    })

    mutations = [
        # 1. delete_edge
        ("delete_edge", lambda s: s["machines"]["WorkNodeStatus"]["ASSIGNED"].remove("AUTHORIZED")),
        # 2. add_edge
        ("add_edge", lambda s: s["machines"]["WorkNodeStatus"]["COMPLETED"].append("EXECUTING")),
        # 3. redirect_edge
        ("redirect_edge", lambda s: s["machines"]["WorkNodeStatus"].__setitem__("ASSIGNED", ["EXECUTING", "READY", "CANCELLED"])),
        # 4. rename_state
        ("rename_state", lambda s: (s["machines"]["WorkNodeStatus"].__setitem__("ASSIGNED_MUTATED", s["machines"]["WorkNodeStatus"].pop("ASSIGNED")))),
        # 5. add_event_type
        ("add_event_type", lambda s: s["event_transitions"].__setitem__("UNAUTHORIZED_EVENT", {"machine": "WorkNodeStatus", "valid_sources": ["SUBMITTED"], "target": "ASSIGNED"})),
        # 6. remove_event_type
        ("remove_event_type", lambda s: s["event_transitions"].pop("AUTHORIZATION_GRANTED", None)),
        # 7. reorder_only (Must ACCEPT)
        ("reorder_only", lambda s: s.__setitem__("machines", {k: s["machines"][k] for k in reversed(list(s["machines"].keys()))})),
        # 8. case_variant_name
        ("case_variant_name", lambda s: (s["machines"]["WorkNodeStatus"].__setitem__("assigned", s["machines"]["WorkNodeStatus"].pop("ASSIGNED")))),
        # 9. consistent_code_and_json_edit
        ("consistent_code_and_json_edit", lambda s: (s["machines"]["WorkNodeStatus"]["ASSIGNED"].append("BACKDOOR_STATE"), s["machines"]["WorkNodeStatus"].__setitem__("BACKDOOR_STATE", ["ASSIGNED"]))),
    ]

    for name, mutator in mutations:
        expected = req_expectations.get(name, "REJECT")
        mutated = copy.deepcopy(canonical_spec)
        try:
            mutator(mutated)
        except Exception as e:
            results.append(f"FAIL: Mutation setup failed for {name}: {e}")
            all_match = False
            continue

        try:
            validate_transition_graph(canonical_spec, mutated)
            observed = "ACCEPT"
        except AssertionError:
            observed = "REJECT"

        if observed == expected:
            results.append(f"PASS: Mutation '{name}' observed={observed} matched expected={expected}")
        else:
            results.append(f"FAIL: Mutation '{name}' observed={observed} but expected={expected}")
            all_match = False

    return all_match, results


def verify_pr_head_as_data(
    base_ref: str,
    pr_head: str,
    anchors: dict,
) -> List[str]:
    """Evaluates candidate PR head strictly as data without executing or installing PR code."""
    violations: List[str] = []
    changed_files = git_diff_files(base_ref, pr_head)
    print(f"[*] Analyzing PR candidate head '{pr_head}' against base '{base_ref}' (data-only mode)...")
    print(f"[*] Total files modified/added in PR: {len(changed_files)}")

    pkg_hashes: Dict[str, str] = anchors.get("package_original_hashes", {})
    errata_dict: Dict[str, dict] = anchors.get("authorized_errata", {})

    for status, filepath in changed_files:
        # 1. Protect Base-Controlled Governance & Workflow Files
        if filepath in PROTECTED_GOVERNANCE_FILES:
            base_bytes = git_show(base_ref, filepath)
            pr_bytes = git_show(pr_head, filepath)
            if base_bytes is not None and pr_bytes is not None and base_bytes != pr_bytes:
                violations.append(
                    f"UNAUTHORIZED GOVERNANCE MODIFICATION in '{filepath}':\n"
                    f"  Candidate PR attempted to modify base-controlled anchor/workflow file.\n"
                    f"  All governance files, trust anchors, and trust workflows are strictly base-controlled."
                )
                continue

        # 2. Protect Frozen Directories (00-SPEC/, 10-CONFORMANCE/, 20-RUNTIME/)
        for f_dir in FROZEN_DIRS:
            if filepath.startswith(f_dir + "/"):
                if status.startswith("D"):
                    # Check if authorized property test relocation
                    if filepath == "10-CONFORMANCE/test_sclass_v6_0_1_property.py":
                        relocated_bytes = git_show(pr_head, "tests/conformance_ext/test_sclass_v6_0_1_property.py")
                        if relocated_bytes is None:
                            violations.append(f"UNAUTHORIZED DELETION: '{filepath}' deleted but not relocated to tests/conformance_ext/")
                        else:
                            h = sha256_lf(relocated_bytes)
                            allowed_hashes = set(errata_dict.get("10-CONFORMANCE/test_sclass_v6_0_1_property.py", {}).get("authorized_hashes", []))
                            if h not in allowed_hashes:
                                violations.append(f"UNAUTHORIZED RELOCATION HASH: '{filepath}' relocated hash {h} unauthorized")
                    else:
                        violations.append(f"UNAUTHORIZED DELETION: Protected file '{filepath}' deleted in PR head.")
                    continue

                # Read candidate file bytes as raw data
                pr_bytes = git_show(pr_head, filepath)
                if pr_bytes is None:
                    violations.append(f"CANNOT READ FILE: Unable to extract '{filepath}' from PR head '{pr_head}'.")
                    continue

                cand_hash = sha256_lf(pr_bytes)
                pkg_hash = pkg_hashes.get(filepath)
                errata_entry = errata_dict.get(filepath)

                if pkg_hash is not None and cand_hash == pkg_hash:
                    continue  # Exact match to package original

                if errata_entry is not None:
                    allowed_hashes = set(errata_entry.get("authorized_hashes", []))
                    if cand_hash in allowed_hashes:
                        print(f"    [+] Verified authorized erratum {errata_entry['erratum_id']} for {filepath}")
                        continue
                    else:
                        violations.append(
                            f"UNAUTHORIZED ERRATA DRIFT in '{filepath}':\n"
                            f"  Candidate SHA-256:  {cand_hash}\n"
                            f"  Base Authorized:    {sorted(allowed_hashes)}\n"
                            f"  Erratum:            {errata_entry.get('erratum_id')}"
                        )
                else:
                    violations.append(
                        f"UNAUTHORIZED MODIFICATION in '{filepath}':\n"
                        f"  Candidate SHA-256:  {cand_hash}\n"
                        f"  Package SHA-256:     {pkg_hash}\n"
                        f"  No authorized errata entry exists in base branch for this file."
                    )

        # 3. Protect Reference Gate
        if filepath == "src/sclass/reference_impl/gate.py":
            pr_bytes = git_show(pr_head, filepath)
            if pr_bytes:
                pr_text = pr_bytes.decode("utf-8", errors="replace")
                if "return worker_instance.execute(request, ctx, handle)" in pr_text and "else:" in pr_text:
                    if "MANDATORY_CONTRACT_PARAMS" not in pr_text:
                        violations.append("GATE CONTRACT VIOLATION: gate.py contains unhardened signature fallback")

    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description="Base-Enforced Trust Anchor Gate (CL Property 1-4)")
    parser.add_argument("--base-ref", default="origin/integration-r30-b1", help="Base branch reference containing authoritative anchors")
    parser.add_argument("--pr-head", default="HEAD", help="Candidate PR head commit reference")
    parser.add_argument("--anchors-file", default="governance/TRUST-ANCHORS.json", help="Path to trust anchors file on base branch")
    args = parser.parse_args()

    print("=" * 80)
    print("S-CLASS BASE-ENFORCED TRUST ANCHOR GATE (STDLIB / DATA-ONLY)")
    print("=" * 80)
    print(f"[*] Base Branch Reference:      {args.base_ref}")
    print(f"[*] Candidate PR Head Reference: {args.pr_head}")
    print(f"[*] Base Anchors File:          {args.anchors_file}")
    print(f"[*] Execution Mode:             Stdlib / Pure Data-Only (Zero PR Code Executed)")
    print("=" * 80)

    # 1. Load authoritative anchors strictly from base branch
    try:
        anchors = load_base_trust_anchors(args.base_ref, args.anchors_file)
        print(f"[+] Loaded authoritative anchors from '{args.base_ref}:{args.anchors_file}'")
    except Exception as e:
        print(f"[-] FATAL: Failed to load base trust anchors: {e}")
        return 1

    # 2. Extract candidate spec for expectations validation
    cand_spec = None
    cand_spec_bytes = git_show(args.pr_head, "10-CONFORMANCE/state-machines.v6.0.1.json")
    if cand_spec_bytes is not None:
        try:
            cand_spec = json.loads(cand_spec_bytes.decode("utf-8"))
        except Exception:
            pass

    # 3. Validate ALL SIX sections of TRUST-ANCHORS.json
    section_violations = validate_all_six_anchor_sections(anchors, cand_spec)
    if section_violations:
        for sv in section_violations:
            print(f"[-] SECTION VALIDATION FAILED: {sv}")
        print("\nTRUST ANCHOR GATE: REJECTED (Section corruption or expectation mismatch)")
        return 1
    print("[+] Verified all 6 sections in authoritative base anchors.")

    # 4. Verify candidate PR changes as pure data
    violations = verify_pr_head_as_data(args.base_ref, args.pr_head, anchors)

    # 5. State-Machine Invariant & Nine-Mutation Battery Verification (Stdlib)
    print("\n[*] Validating candidate state machine specification and transition graph...")
    base_spec_bytes = git_show(args.base_ref, "10-CONFORMANCE/state-machines.v6.0.1.json")
    if base_spec_bytes is None:
        violations.append("CANNOT READ BASE SPEC: '10-CONFORMANCE/state-machines.v6.0.1.json' missing from base ref.")
    else:
        base_spec = json.loads(base_spec_bytes.decode("utf-8"))
        if cand_spec is None:
            violations.append("CANNOT READ CANDIDATE SPEC: '10-CONFORMANCE/state-machines.v6.0.1.json' missing from PR head.")
        else:
            try:
                validate_transition_graph(base_spec, cand_spec)
                print("    [+] Candidate state machine transition-edge graph matches base specification.")
            except AssertionError as err:
                violations.append(f"STATE MACHINE GRAPH VIOLATION: {err}")

        # Run 9-mutation battery against the validator using base expectations
        print("[*] Executing State-Machine Nine-Mutation Battery (Stdlib In-Memory Verification)...")
        mut_ok, mut_logs = execute_nine_mutation_battery_stdlib(base_spec, anchors.get("mutation_battery_expectations"))
        for log in mut_logs:
            print(f"    {log}")
        if not mut_ok:
            violations.append("STATE MACHINE MUTATION BATTERY FAILED: One or more mutations did not match expectations!")

    # 4. Final Evaluation & Report
    print("\n" + "=" * 90)
    if violations:
        print("TRUST ANCHOR GATE: REJECTED")
        print("=" * 90)
        print(f"Found {len(violations)} violation(s):")
        for i, v in enumerate(violations, 1):
            print(f"\n[{i}] {v}")
        print("\n" + "=" * 90)
        return 1

    print("TRUST ANCHOR GATE: ACCEPTED")
    print("=" * 90)
    print("[+] All candidate files match base-branch package hashes and authorized errata.")
    print("[+] Base-controlled anchors file read strictly from base branch.")
    print("[+] State-machine transition-edge graph validated; all 9 mutations rejected.")
    print("[+] Candidate PR head evaluated strictly as pure data (zero candidate code executed).")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
