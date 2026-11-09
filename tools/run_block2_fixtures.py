#!/usr/bin/env python3
"""CLI tool for executing Block 2 fixtures from SHA-256 verified master design."""
from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure src is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sclass.product.fixture_runner import (
    FixtureRunner,
    verify_master_sha256,
)

DEFAULT_MASTER_SHA256 = (
    "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Block 2 fixtures against Master Product Design."
    )
    default_master = os.environ.get(
        "SCLASS_MASTER_PATH",
        os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "docs",
                "design",
                "S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md",
            )
        ),
    )
    parser.add_argument(
        "--master-path",
        default=default_master,
        help="Path to authoritative Master Product Design Markdown file.",
    )
    parser.add_argument(
        "--expected-sha256",
        default=DEFAULT_MASTER_SHA256,
        help="Expected SHA-256 digest of the master design document.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Path to save canonical JSON execution manifest.",
    )
    parser.add_argument(
        "--output-summary",
        default=None,
        help="Path to save plain text summary report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Pre-verification of master SHA256 before any execution
    try:
        actual_sha = verify_master_sha256(args.master_path, args.expected_sha256)
        print(f"Master SHA256 verified: {actual_sha}")
    except Exception as ex:
        print(f"FATAL: Master verification failed: {ex}", file=sys.stderr)
        return 1

    runner = FixtureRunner()
    manifest = runner.run(args.master_path, args.expected_sha256)
    summary_text = runner.format_summary(manifest)

    print(summary_text)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, sort_keys=True)
        print(f"Saved manifest to {args.output_json}")

    if args.output_summary:
        with open(args.output_summary, "w", encoding="utf-8") as f:
            f.write(summary_text + "\n")
        print(f"Saved summary to {args.output_summary}")

    # Notice: per CL specification:
    # "A genuine RAN-MISMATCH is a finding for CL, not a failure; do not tune bindings to force matches"
    # An unexpected execution error fails closed
    if manifest["counts"]["error"] > 0:
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
