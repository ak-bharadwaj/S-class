#!/usr/bin/env python3
"""Extracts R30 Section F3 normative text and fixtures, verifying Master SHA-256."""
from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

ZIP_PATH = Path("/mnt/c/Users/dorni/Downloads/FREEZE-CANDIDATE-v6.0.2-R30.zip")
MEMBER_NAME = "FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md"
EXPECTED_SHA256 = "340db97857a7716b1aac2c1b44bc60b32642e3d8074d02720c2333cea278b4ff"

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "delivery-1-03"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "R30-F3-EXTRACT.md"


def main():
    if not ZIP_PATH.exists():
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

    # Locate Section F3
    f3_start = -1
    f3_end = -1
    fixtures_start = -1
    fixtures_end = -1

    for idx, line in enumerate(lines):
        if "<!-- SECTION F3 |" in line or "## F3 — Trust model for agent-authored content" in line:
            if f3_start == -1:
                f3_start = idx
        elif f3_start != -1 and f3_end == -1 and line.startswith("<!-- SECTION F4 |"):
            f3_end = idx

        if "### F3 fixtures" in line or "### F3 Test Fixtures" in line:
            if fixtures_start == -1 and idx > 8000:
                fixtures_start = idx
        elif fixtures_start != -1 and fixtures_end == -1 and ("### F4-T1" in line or "### F4-T1 / F4-FT1" in line):
            fixtures_end = idx

    print(f"Section F3 range: lines {f3_start+1} to {f3_end+1}")
    print(f"Fixtures range: lines {fixtures_start+1} to {fixtures_end+1}")

    f3_text = "".join(lines[f3_start:f3_end])
    fixtures_text = "".join(lines[fixtures_start:fixtures_end])

    out_content = f"""# Normative Extract: R30 Section F3 Trust Model for Agent-Authored Content

## Document Provenance & Verification
- **Source Archive:** `FREEZE-CANDIDATE-v6.0.2-R30.zip`
- **Source File:** `FREEZE-CANDIDATE-v6.0.2/S-CLASS-v6.0.2-MASTER-PRODUCT-DESIGN.md`
- **Expected SHA-256:** `{EXPECTED_SHA256}`
- **Verified SHA-256:** `{actual_hash}`
- **Integrity Status:** `MATCH - VERIFIED`

---

## Section F3 Normative Text

{f3_text}

---

## Authoritative F3 Test Fixtures (F3-T1 through F3-T7)

{fixtures_text}
"""
    OUT_PATH.write_text(out_content, encoding="utf-8")
    print(f"Wrote normative extract to {OUT_PATH} ({len(out_content)} chars)")


if __name__ == "__main__":
    main()
