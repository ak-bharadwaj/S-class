"""
CLI entry point for strict single-source Parity Certificate verification.
Cross-platform compatible without shell-specific heredocs or encoding issues.
"""

import os
import sys
import json
import argparse
from benchmark.parity.file_lock_harness import verify_parity_certificate


def main():
    parser = argparse.ArgumentParser(description="Verify OSS Parity Certificate against strict single-source gate rules.")
    parser.add_argument("--certificate", required=True, help="Path to the JSON parity certificate file.")
    parser.add_argument("--expected-sha", default=None, help="Expected git commit SHA for provenance verification.")
    args = parser.parse_args()

    cert_path = os.path.abspath(args.certificate)
    if not os.path.isfile(cert_path):
        print(f"FATAL: Certificate file not found at {cert_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(cert_path, "r", encoding="utf-8") as f:
            cert = json.load(f)
    except Exception as e:
        print(f"FATAL: Failed to parse JSON certificate at {cert_path}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Validating Parity Certificate: {cert_path}")
    print(f"Expected SHA: {args.expected_sha}")
    print("=" * 80)
    print(json.dumps(cert, indent=2))
    print("=" * 80)

    try:
        verify_parity_certificate(cert, expected_sha=args.expected_sha)
        print("\nALL PARITY GATE 1 ASSERTIONS AND PROVENANCE CHECKS PASSED PERFECTLY! [PASS]")
        sys.exit(0)
    except (ValueError, KeyError, AssertionError) as err:
        print(f"\nPARITY CERTIFICATE VERIFICATION FAILED: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
