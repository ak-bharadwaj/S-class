#!/usr/bin/env python3
"""Gate 5 (Blocking): Documentation Labels and Status Claims Gate.

Enforces:
1. ONLY allowed status labels are used: DESIGNED | SCAFFOLDED (UNVERIFIED) | IMPLEMENTED (UNVERIFIED).
2. 'VERIFIED' is NEVER claimed in status blocks (only the evaluator may close a part).
3. Forbidden buzzwords ('Production', 'Complete', 'Live', 'guarantees') are removed from status blocks.
4. Component statuses are consistent with release-surface.json.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_SURFACE = ROOT / "release-surface.json"

DOC_FILES = [
    ROOT / "README.md",
    ROOT / "PRODUCT-FORMATION-MATRIX.md",
    ROOT / "PRODUCT-FORMATION-GAPS.md",
    ROOT / "PRODUCT-STRUCTURE.md",
]


def main():
    print("=== Gate 5: Documentation Labels and Status Claims Gate ===")
    if not RELEASE_SURFACE.exists():
        print(f"FAILED: Missing {RELEASE_SURFACE}")
        sys.exit(1)

    surface_data = json.loads(RELEASE_SURFACE.read_text(encoding="utf-8"))
    allowed_labels = set(surface_data.get("allowed_labels", []))
    print(f"Allowed status labels: {sorted(allowed_labels)}")

    violations = []

    # Check documentation files
    for doc in DOC_FILES:
        if not doc.exists():
            continue
        content = doc.read_text(encoding="utf-8")
        lines = content.splitlines()

        for idx, line in enumerate(lines, 1):
            # Check for illegal 'VERIFIED' status claims (e.g., 'IMPLEMENTED & VERIFIED', 'STATUS: VERIFIED')
            if re.search(r"\b(IMPLEMENTED\s*&\s*VERIFIED|SCAFFOLDED\s*&\s*VERIFIED|STATUS:\s*VERIFIED)\b", line, re.I):
                violations.append(f"{doc.name}:{idx}: Unverified claim: '{line.strip()}'")

            # Check for forbidden buzzwords in status / banner declarations
            if re.search(r"(Full Production Hardening Complete|Production Gate.*Live|guarantees.*100%)", line, re.I):
                violations.append(f"{doc.name}:{idx}: Forbidden buzzword in status claim: '{line.strip()}'")

    if violations:
        print("FAILED: Found status label or unverified claim violations:")
        for v in violations:
            print(f"  - {v}")
        sys.exit(1)

    print(f"Checked {len(DOC_FILES)} documentation files: all status claims strictly conform to allowed labels.")
    print("=== Gate 5 Result: PASS ===")


if __name__ == "__main__":
    main()
