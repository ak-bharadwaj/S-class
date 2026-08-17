"""
S-Class EOS V11.2 - Formal Verifier for THESIS-GATE-1A Certificate Receipt.
Enforces strict fail-closed provenance, zero treatment defect escapes, observable pre/post-gen defect detections,
and bounded false-positive rates on the Enterprise Core Synthetic Efficacy Pilot.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, Optional


def verify_thesis_gate_1a_certificate(certificate_path: str, expected_sha: Optional[str] = None) -> bool:
    """
    Verifies that a THESIS-GATE-1A Synthetic Efficacy receipt meets all enterprise criteria.
    Fails closed on missing provenance or out-of-spec metrics.
    """
    if not os.path.exists(certificate_path):
        print(f"[FAIL] Certificate file does not exist: {certificate_path}")
        return False

    try:
        with open(certificate_path, "r", encoding="utf-8") as f:
            cert = json.load(f)
    except Exception as ex:
        print(f"[FAIL] Failed to parse certificate JSON: {ex}")
        return False

    # 1. Provenance Integrity (Fail-Closed)
    provenance = cert.get("provenance", {})
    tested_sha = provenance.get("tested_source_sha")

    if not tested_sha or tested_sha == "UNKNOWN" or len(tested_sha.strip()) == 0:
        print(f"[FAIL] Missing or invalid tested_source_sha in provenance: '{tested_sha}'")
        return False

    if expected_sha is not None:
        if tested_sha != expected_sha:
            print(f"[FAIL] Provenance SHA mismatch: expected '{expected_sha}', found '{tested_sha}'")
            return False

    # 2. Schema and Milestone Check
    milestone = cert.get("milestone", "")
    if "THESIS-GATE-1" not in milestone:
        print(f"[FAIL] Invalid milestone in receipt: '{milestone}'")
        return False

    # 3. Observable Comparative Metrics
    metrics = cert.get("observable_comparative_metrics", {})
    total_scenarios = provenance.get("total_scenarios_evaluated", 0)

    if total_scenarios < 5:
        print(f"[FAIL] Insufficient controlled scenarios evaluated: {total_scenarios} (required >= 5)")
        return False

    treatment_escaped = metrics.get("treatment_defects_escaped", 999)
    if treatment_escaped != 0:
        print(f"[FAIL] Treatment allowed defects to escape: {treatment_escaped} (required == 0)")
        return False

    pre_gen_caught = metrics.get("pre_gen_defects_caught_by_grounding", 0)
    if pre_gen_caught < 1:
        print(f"[FAIL] Pre-generation grounding caught zero defects: {pre_gen_caught} (required >= 1)")
        return False

    post_gen_caught = metrics.get("post_gen_defects_caught_by_evidence", 0)
    if post_gen_caught < 1:
        print(f"[FAIL] Post-generation evidence caught zero defects: {post_gen_caught} (required >= 1)")
        return False

    fp_rate = metrics.get("false_positive_rate", 1.0)
    if fp_rate > 0.050:
        print(f"[FAIL] False positive rate exceeded threshold: {fp_rate} > 0.050")
        return False

    verdict = cert.get("pilot_verdict")
    if verdict != "PASS":
        print(f"[FAIL] Pilot verdict is not PASS: '{verdict}'")
        return False

    print(f"[PASS] THESIS-GATE-1A Certificate '{certificate_path}' verified successfully.")
    print(f"       Tested SHA: {tested_sha}")
    print(f"       Defects Escaped: Baseline={metrics.get('baseline_defects_escaped')} vs Treatment=0")
    print(f"       Pre-Gen Caught: {pre_gen_caught}, Post-Gen Caught: {post_gen_caught}, FP Rate: {fp_rate}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="THESIS-GATE-1A Certificate Verifier")
    parser.add_argument("certificate", help="Path to THESIS-GATE-1A receipt JSON")
    parser.add_argument("--sha", help="Expected git commit SHA", default=None)
    args = parser.parse_args()

    success = verify_thesis_gate_1a_certificate(args.certificate, expected_sha=args.sha)
    sys.exit(0 if success else 1)
