#!/usr/bin/env python3
"""Extracts R30 Section F2 normative text and validates SHA-256."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ZIP_PATH = Path("/mnt/c/Users/dorni/Downloads/FREEZE-CANDIDATE-v6.0.2-R30.zip")
MEMBER_NAME = "FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
EXPECTED_SHA256 = "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"

OUT_PATH = Path(__file__).resolve().parent / "normative_f2_extract.md"


def main():
    if not ZIP_PATH.exists():
        # Fallback to Windows path if running directly in Windows
        win_path = Path("C:/Users/dorni/Downloads/FREEZE-CANDIDATE-v6.0.2-R30.zip")
        if win_path.exists():
            zpath = win_path
        else:
            raise FileNotFoundError(f"Cannot find zip at {ZIP_PATH} or {win_path}")
    else:
        zpath = ZIP_PATH

    with zipfile.ZipFile(zpath, "r") as zf:
        raw_bytes = zf.read(MEMBER_NAME)

    actual_hash = hashlib.sha256(raw_bytes).hexdigest()
    print(f"Master design document SHA-256: {actual_hash}")
    assert actual_hash == EXPECTED_SHA256, f"Hash mismatch: {actual_hash} != {EXPECTED_SHA256}"
    print("SHA-256 hash verified successfully!")

    content = raw_bytes.decode("utf-8")
    lines = content.splitlines(keepends=True)

    # Locate Section F2
    f2_start = -1
    f2_end = -1
    fixtures_start = -1
    fixtures_end = -1

    for idx, line in enumerate(lines):
        if "<!-- SECTION F2 |" in line or "## F2 — Predicate and Invariant Language" in line:
            if f2_start == -1:
                f2_start = idx
        elif f2_start != -1 and f2_end == -1 and line.startswith("<!-- SECTION F3 |"):
            f2_end = idx

        if "### F2 Test Fixtures" in line or "F2-T1 —" in line or "### F2-T1" in line:
            if fixtures_start == -1 and idx > 8000:
                fixtures_start = idx
        elif fixtures_start != -1 and fixtures_end == -1 and "### F3 fixtures" in line:
            fixtures_end = idx

    print(f"Section F2 range: lines {f2_start+1} to {f2_end+1}")
    print(f"Fixtures range: lines {fixtures_start+1} to {fixtures_end+1}")

    f2_text = "".join(lines[f2_start:f2_end]) if f2_end != -1 else "".join(lines[f2_start:f2_start+300])
    fixtures_text = (
        "".join(lines[fixtures_start:fixtures_end])
        if fixtures_end != -1
        else ("".join(lines[fixtures_start:fixtures_start+350]) if fixtures_start != -1 else "")
    )

    out_content = f"""# Normative Extract: R30 Section F2 Predicate and Invariant Evaluator

## Document Provenance & Verification
- **Source Archive:** `FREEZE-CANDIDATE-v6.0.2-R30.zip`
- **Source File:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`
- **Expected SHA-256:** `{EXPECTED_SHA256}`
- **Verified SHA-256:** `{actual_hash}`
- **Integrity Status:** `MATCH - VERIFIED`

---

## Section F2 Normative Text

{f2_text}

---

## Authoritative F2 Test Fixtures (F2-T1 through F2-T14)

{fixtures_text}
"""
    OUT_PATH.write_text(out_content, encoding="utf-8")
    print(f"Wrote normative extract to {OUT_PATH} ({len(out_content)} chars)")


if __name__ == "__main__":
    main()
