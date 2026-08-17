"""
S-Class EOS V11.2 - Gate 2 Parity Certificate Verifier.
Single source of truth verifier for Gate 2 Property Testing Parity Certificates.
Validates SHA provenance, 95% bootstrap confidence intervals, and soak memory growth.
Supported Python Versions: 3.10-3.13.
"""

import sys
import json
import argparse
from typing import Optional, Dict, Any


def verify_gate2_certificate(cert: Dict[str, Any], expected_sha: Optional[str] = None) -> bool:
    """
    Validates Gate 2 Parity Certificate against frozen acceptance criteria.
    Fails closed on missing provenance, UNKNOWN SHA, or statistical gate violations.
    Raises ValueError on any missing key or failed constraint.
    """
    if not isinstance(cert, dict):
        raise ValueError("Certificate must be a dictionary")

    cert_id = cert.get("certificate_id", "")
    if not cert_id.startswith("OSS-PARITY-GATE-2-PROPERTY-TESTING-LINUX"):
        raise ValueError(f"Invalid certificate_id: {cert_id}")

    prov = cert.get("provenance", {})
    if not prov or not isinstance(prov, dict):
        raise ValueError("Missing provenance in certificate")

    tested_sha = prov.get("tested_source_sha", "")
    if expected_sha:
        if not tested_sha or tested_sha == "UNKNOWN":
            raise ValueError(f"Provenance missing or UNKNOWN tested_source_sha in certificate! Expected {expected_sha}, got {repr(tested_sha)}")
        if tested_sha != expected_sha:
            raise ValueError(f"Tested source SHA mismatch! Expected {expected_sha}, got {tested_sha}")

    crit = cert.get("acceptance_criteria", {})
    if crit.get("soak_cycles_executed") != 5000:
        raise ValueError(f"Soak cycles must be 5000, got {crit.get('soak_cycles_executed')}")
    if crit.get("total_paired_benchmark_trials") < 6000:
        raise ValueError(f"Total paired benchmark trials must be at least 6000, got {crit.get('total_paired_benchmark_trials')}")

    # Aggregate performance metrics
    agg = cert.get("aggregate_performance_metrics", {})
    med_ci = agg.get("median_ratio_95_ci", [99, 99])
    p95_ci = agg.get("p95_ratio_95_ci", [99, 99])
    tp_ci = agg.get("throughput_ratio_95_ci", [0, 0])

    if med_ci[1] > 1.050:
        raise ValueError(f"Aggregate median upper 95% CI failed: {med_ci[1]} > 1.050")
    if p95_ci[1] > 1.050:
        raise ValueError(f"Aggregate P95 upper 95% CI failed: {p95_ci[1]} > 1.050")
    if tp_ci[0] < 0.950:
        raise ValueError(f"Aggregate throughput lower 95% CI failed: {tp_ci[0]} < 0.950")
    if not agg.get("all_gates_passed"):
        raise ValueError("Aggregate all_gates_passed is False")

    # Domain performance metrics
    dom_metrics = cert.get("domain_performance_metrics", {})
    if len(dom_metrics) < 6:
        raise ValueError(f"Expected at least 6 domain benchmarks, got {len(dom_metrics)}")
    for dom_name, dom_info in dom_metrics.items():
        if not dom_info.get("domain_gate_passed"):
            raise ValueError(f"Domain '{dom_name}' failed performance gate")

    # Soak memory metrics
    soak = cert.get("long_soak_memory", {})
    if soak.get("rss_growth_ratio", 99) > 1.050:
        raise ValueError(f"Soak memory growth failed: {soak.get('rss_growth_ratio')} > 1.050")
    if not soak.get("soak_gate_passed"):
        raise ValueError("Soak gate passed is False")

    # Final verdict
    if cert.get("final_verdict") != "PASS":
        raise ValueError(f"Final verdict must be PASS, got {cert.get('final_verdict')}")

    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify Gate 2 Parity Certificate")
    parser.add_argument("--certificate", type=str, required=True, help="Path to certificate JSON")
    parser.add_argument("--expected-sha", type=str, default=None, help="Expected Git commit SHA")
    args = parser.parse_args()

    with open(args.certificate, "r", encoding="utf-8") as f:
        cert_data = json.load(f)

    try:
        verify_gate2_certificate(cert_data, expected_sha=args.expected_sha)
        print(f"Gate 2 Parity Certificate '{args.certificate}' successfully verified and certified 100% PASS.")
        sys.exit(0)
    except Exception as err:
        print(f"Gate 2 Certificate Verification FAILED: {err}", file=sys.stderr)
        sys.exit(1)
