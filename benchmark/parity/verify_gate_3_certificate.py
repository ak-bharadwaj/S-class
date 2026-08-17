"""
S-Class EOS V11.2 - Schemathesis Gate 3 Certificate Verifier (D0 Keyed Specification).
Single-source verifier validating Gate 3 Parity Certificates against authoritative source SHA,
pinned dependency versions, keyed HMAC-SHA256 digests, and cryptographic provenance hash chains.
"""

import os
import sys
import json
import hashlib
import argparse


def verify_gate_3_certificate(cert_path: str, expected_sha: str, expected_version: str = "4.24.3") -> bool:
    """Strictly verifies a Gate 3 Parity Certificate under the D0 Keyed HMAC Provider Contract."""
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"Certificate not found at: {cert_path}")

    with open(cert_path, "r", encoding="utf-8") as f:
        cert = json.load(f)

    # 1. Structural & Contract Spec Checks
    if cert.get("gate") != "PARITY-GATE-3":
        raise ValueError(f"Invalid gate in certificate: expected 'PARITY-GATE-3', got '{cert.get('gate')}'")

    if cert.get("contract_spec") not in ["D0", "D0_KEYED_HMAC"]:
        raise ValueError(f"Invalid contract spec: expected 'D0_KEYED_HMAC', got '{cert.get('contract_spec')}'")

    if cert.get("verdict") != "PASS":
        raise ValueError(f"Certificate verdict is not PASS: got '{cert.get('verdict')}'")

    # 2. Provenance & Source SHA Checks
    actual_sha = cert.get("source_sha")
    if not actual_sha or actual_sha == "UNKNOWN" or len(actual_sha) != 40:
        raise ValueError(f"Certificate has missing, UNKNOWN, or invalid source SHA: '{actual_sha}'")

    if expected_sha and expected_sha != "UNKNOWN" and actual_sha != expected_sha:
        raise ValueError(f"Source SHA mismatch: expected '{expected_sha}', got '{actual_sha}'")

    # 3. Version Pinning Checks
    st_ver = cert.get("schemathesis_version")
    if st_ver != expected_version:
        raise ValueError(f"Schemathesis version mismatch: expected '{expected_version}', got '{st_ver}'")

    pinned_ver = cert.get("exact_pinned_version")
    if pinned_ver != expected_version:
        raise ValueError(f"Exact pinned version mismatch: expected '{expected_version}', got '{pinned_ver}'")

    if cert.get("provider_version") != "1.0.0":
        raise ValueError(f"Provider version mismatch: expected '1.0.0', got '{cert.get('provider_version')}'")

    # 4. Zero Object Leakage & Keyed HMAC Check
    if cert.get("zero_object_leakage_verified") is not True:
        raise ValueError("Certificate indicates object leakage verification failed or missing.")

    if cert.get("keyed_hmac_authentication_verified") is not True:
        raise ValueError("Certificate indicates keyed HMAC authentication verification failed or missing.")

    # 5. Corpus Results & D0 Digest Validation
    corpus = cert.get("corpus_results", {})
    required_scenarios = ["clean_api", "schema_violation", "server_error_5xx", "malformed_schema", "unreachable_target"]
    for sc in required_scenarios:
        if sc not in corpus:
            raise KeyError(f"Missing corpus scenario result: {sc}")
        sc_res = corpus[sc]
        for req_field in ["schema_hash", "config_hash", "input_digest", "worker_digest", "worker_hmac", "provenance_hash"]:
            if req_field not in sc_res or not sc_res[req_field]:
                raise ValueError(f"Corpus scenario '{sc}' missing required D0 field '{req_field}'.")

    # Check scenario statuses
    if corpus["clean_api"]["status"] != "TARGET_CLEAN" or not corpus["clean_api"]["passed"]:
        raise ValueError("Corpus clean_api scenario did not pass as TARGET_CLEAN")

    if corpus["schema_violation"]["status"] != "TARGET_CONTRACT_VIOLATED" or corpus["schema_violation"]["passed"]:
        raise ValueError("Corpus schema_violation scenario did not fail closed")

    if corpus["server_error_5xx"]["status"] != "TARGET_CONTRACT_VIOLATED" or corpus["server_error_5xx"]["passed"]:
        raise ValueError("Corpus server_error_5xx scenario did not fail closed")

    if corpus["malformed_schema"]["status"] != "INPUT_INVALID" or corpus["malformed_schema"]["passed"]:
        raise ValueError("Corpus malformed_schema scenario did not fail closed")

    if corpus["unreachable_target"]["status"] not in ["TARGET_CONTRACT_VIOLATED", "TOOL_EXECUTION_FAILED"] or corpus["unreachable_target"]["passed"]:
        raise ValueError("Corpus unreachable_target scenario did not fail closed")

    # 6. Certificate Hash Integrity
    stored_hash = cert.get("certificate_hash")
    if not stored_hash:
        raise ValueError("Certificate missing certificate_hash field.")

    cert_copy = dict(cert)
    del cert_copy["certificate_hash"]
    expected_hash = hashlib.sha256(json.dumps(cert_copy, sort_keys=True).encode("utf-8")).hexdigest()

    if stored_hash != expected_hash:
        raise ValueError(f"Certificate hash tampering detected! Stored: {stored_hash}, Expected: {expected_hash}")

    print(f"VERIFIED: D0 Keyed Gate 3 Parity Certificate {cert_path} successfully validated against SHA {actual_sha} and Schemathesis {st_ver}.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Verify S-Class Gate 3 Parity Certificate (D0 Keyed Protocol)")
    parser.add_argument("--certificate", required=True, help="Path to certificate JSON file")
    parser.add_argument("--expected-sha", required=True, help="Expected authoritative git commit SHA")
    parser.add_argument("--expected-version", default="4.24.3", help="Expected Schemathesis version (default: 4.24.3)")

    args = parser.parse_args()
    try:
        verify_gate_3_certificate(
            cert_path=args.certificate,
            expected_sha=args.expected_sha,
            expected_version=args.expected_version
        )
        sys.exit(0)
    except Exception as e:
        print(f"FAILED: Certificate verification rejected: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
