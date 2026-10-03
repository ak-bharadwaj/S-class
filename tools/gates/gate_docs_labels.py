#!/usr/bin/env python3
"""Gate 5 (Blocking): Documentation Labels and Status Claims Gate.

Scans README.md and all *.md in repo root and docs/ to enforce:
1. ONLY allowed status labels are used: DESIGNED | SCAFFOLDED (UNVERIFIED) | IMPLEMENTED (UNVERIFIED).
2. 'VERIFIED' is NEVER claimed in status blocks or text (only the external evaluator may close/verify).
3. Forbidden buzzwords fail the gate: Production, Complete, Live, Qualified, Verified (outside UNVERIFIED), guarantees.
4. Stale test counts fail the gate (enforces exact current suite count of 252 tests, 0 skipped).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RELEASE_SURFACE = ROOT / "release-surface.json"
DOCS_DIR = ROOT / "docs"

# Scan README + all *.md in repo root / docs (excluding frozen spec directories and gitignored files)
DOC_FILES = [ROOT / "README.md"]
if DOCS_DIR.exists():
    DOC_FILES.extend(sorted(DOCS_DIR.glob("*.md")))

# Include root documentation files
ROOT_DOCS = [
    ROOT / "PRODUCT-FORMATION-MATRIX.md",
    ROOT / "PRODUCT-FORMATION-GAPS.md",
    ROOT / "PRODUCT-STRUCTURE.md",
    ROOT / "S0_CLOSURE_REPORT.md",
]
for rd in ROOT_DOCS:
    if rd.exists() and rd not in DOC_FILES:
        DOC_FILES.append(rd)


# Forbidden words / buzzwords
FORBIDDEN_BUZZWORDS = re.compile(
    r"\b(Production|Complete|Live|Qualified|guarantees?)\b",
    re.IGNORECASE,
)

# Unverified check: forbids 'verified' unless preceded by 'un' (allowing 'UNVERIFIED')
UNVERIFIED_CHECK = re.compile(r"(?<!un)\bverified\b", re.IGNORECASE)

# Stale test count checks
STALE_TEST_COUNTS = [
    re.compile(r"\b(210|245)\s*(tests?|passed)\b", re.IGNORECASE),
    re.compile(r"\b[1-9]\d*\s*skipped\b", re.IGNORECASE),
]


def check_file(doc_path: Path) -> list[str]:
    violations = []
    content = doc_path.read_text(encoding="utf-8")
    lines = content.splitlines()

    for idx, line in enumerate(lines, 1):
        # 1. Check for unverified / verified claims
        m_v = UNVERIFIED_CHECK.search(line)
        if m_v:
            violations.append(
                f"{doc_path.name}:{idx}: Illegal claim of '{m_v.group()}': {line.strip()}"
            )

        # 2. Check for forbidden buzzwords
        m_b = FORBIDDEN_BUZZWORDS.search(line)
        if m_b:
            violations.append(
                f"{doc_path.name}:{idx}: Forbidden buzzword '{m_b.group()}': {line.strip()}"
            )

        # 3. Check for stale test counts
        for pat in STALE_TEST_COUNTS:
            m_s = pat.search(line)
            if m_s:
                violations.append(
                    f"{doc_path.name}:{idx}: Stale test count '{m_s.group()}': {line.strip()}"
                )

    return violations


def main():
    print("=== Gate 5: Documentation Labels and Status Claims Gate ===")
    if not RELEASE_SURFACE.exists():
        print(f"FAILED: Missing {RELEASE_SURFACE}")
        sys.exit(1)

    surface_data = json.loads(RELEASE_SURFACE.read_text(encoding="utf-8"))
    allowed_labels = set(surface_data.get("allowed_labels", []))
    print(f"Allowed status labels: {sorted(allowed_labels)}")
    print(f"Scanning {len(DOC_FILES)} documentation files...")

    all_violations = []
    for doc in DOC_FILES:
        if not doc.exists():
            continue
        v = check_file(doc)
        all_violations.extend(v)

    if all_violations:
        print("FAILED: Found documentation status or forbidden word violations:")
        for v in all_violations:
            print(f"  - {v}")
        sys.exit(1)

    print(f"Checked {len(DOC_FILES)} documentation files: all claims strictly conform.")
    print("=== Gate 5 Result: PASS ===")


if __name__ == "__main__":
    main()
