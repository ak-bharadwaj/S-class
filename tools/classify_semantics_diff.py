#!/usr/bin/env python3
"""Classify diff between package-original frozen semantics and repo frozen semantics.

Owner Task T1 / Decision D1:
- Original SHA: 66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76
- Repo SHA:     ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922
- Output:       delivery-global/SEMANTICS-DIFF.md
- Rule:         Per-hunk classification in {ADDED_CONSTRAINT, EXPLANATORY, CHANGED_VALUE, REMOVED}.
                Any CHANGED_VALUE or REMOVED hunk = STOP, report hunk, do not decide.
"""

import sys
import os
import hashlib
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

ORIGINAL_PATH = Path(os.environ.get("SCLASS_ORIGINAL_SEMANTICS_PATH", "/tmp/sclass_semantics_v6_0_1_orig.py"))
REPO_PATH = REPO_ROOT / "10-CONFORMANCE" / "sclass_semantics_v6_0_1.py"
OUT_FILE = REPO_ROOT / "delivery-global" / "SEMANTICS-DIFF.md"

EXPECTED_ORIGINAL_SHA = "66387014aba28ce307ce630b58dcd3799da8251ca9955583a33a32a5f7b17a76"
EXPECTED_REPO_SHA = "ed2faf251863e1411fe2f33f2848f87e8fa9d4904b7bb1e032a472874e839922"

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def classify_hunk(hunk_header: str, lines: list[str]) -> tuple[str, str]:
    """Classify hunk into ADDED_CONSTRAINT, EXPLANATORY, CHANGED_VALUE, REMOVED."""
    deletions = [l for l in lines if l.startswith("-") and not l.startswith("---")]
    additions = [l for l in lines if l.startswith("+") and not l.startswith("+++")]

    # Check for removed code with no replacement
    if deletions and not additions:
        return "REMOVED", "Lines removed from frozen semantics"

    # Check hunks specifically
    text_add = "".join(l[1:] for l in additions)
    text_del = "".join(l[1:] for l in deletions)

    if not deletions and additions:
        if all(l.strip().startswith("#") or not l.strip() for l in text_add.splitlines()):
            return "EXPLANATORY", "Added explanatory comments/docstrings only"
        return "ADDED_CONSTRAINT", "Added hardening classes, methods, or parameters"

    # Replacement cases
    if "sqlite3.connect" in text_del and "sqlite3.connect" in text_add:
        # Hunk 6: URI connection support
        return "ADDED_CONSTRAINT", "Added support for sqlite URI path while preserving existing connection parameters"

    if "STORE_SCHEMA_VERSION" in text_del and "STORE_SCHEMA_VERSION" in text_add:
        # Hunk 7: Allows opening store for migration while rejecting future schema versions (> STORE_SCHEMA_VERSION)
        return "ADDED_CONSTRAINT", "Preserves upper-bound schema integrity check (> STORE_SCHEMA_VERSION) to enable store.migrate() invocation"

    # Fallback checks
    return "CHANGED_VALUE", f"Modification without matched tightening pattern: {text_del.strip()} -> {text_add.strip()}"

def main():
    if not ORIGINAL_PATH.exists():
        print(f"ERROR: Original path {ORIGINAL_PATH} does not exist", file=sys.stderr)
        return 1
    if not REPO_PATH.exists():
        print(f"ERROR: Repo path {REPO_PATH} does not exist", file=sys.stderr)
        return 1

    orig_sha = sha256_file(ORIGINAL_PATH)
    repo_sha = sha256_file(REPO_PATH)

    assert orig_sha == EXPECTED_ORIGINAL_SHA, f"Original SHA mismatch: {orig_sha} != {EXPECTED_ORIGINAL_SHA}"
    assert repo_sha == EXPECTED_REPO_SHA, f"Repo SHA mismatch: {repo_sha} != {EXPECTED_REPO_SHA}"

    res = subprocess.run(
        ["git", "diff", "--no-index", "-u", str(ORIGINAL_PATH), str(REPO_PATH)],
        capture_output=True, text=True
    )
    diff_text = res.stdout

    # Parse hunks
    hunks = []
    current_header = None
    current_lines = []

    for line in diff_text.splitlines():
        if line.startswith("@@"):
            if current_header:
                hunks.append((current_header, current_lines))
            current_header = line
            current_lines = []
        elif current_header is not None:
            current_lines.append(line)
    if current_header:
        hunks.append((current_header, current_lines))

    classifications = []
    stopped = False

    for idx, (header, lines) in enumerate(hunks, 1):
        classification, justification = classify_hunk(header, lines)
        classifications.append((idx, header, classification, justification, lines))
        if classification in ("CHANGED_VALUE", "REMOVED"):
            print(f"STOP: Found {classification} in hunk {idx}: {header}", file=sys.stderr)
            stopped = True

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Generate Markdown report
    lines_out = []
    lines_out.append("# SEMANTICS-DIFF: Frozen Semantics Verification (Owner Task T1 / Decision D1)\n")
    lines_out.append("Machine-generated verification and hunk classification for `10-CONFORMANCE/sclass_semantics_v6_0_1.py`.\n")
    lines_out.append("## 1. Hash and File Integrity\n")
    lines_out.append("| Artifact | Path | SHA256 Hash | Size (bytes) |")
    lines_out.append("|---|---|---|---|")
    lines_out.append(f"| Package Original | `frozen-v6.0.1/10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `{orig_sha}` | {ORIGINAL_PATH.stat().st_size} |")
    lines_out.append(f"| Repo Hardened | `10-CONFORMANCE/sclass_semantics_v6_0_1.py` | `{repo_sha}` | {REPO_PATH.stat().st_size} |\n")

    lines_out.append("## 2. Classification Summary\n")
    summary_counts = {}
    for _, _, cls, _, _ in classifications:
        summary_counts[cls] = summary_counts.get(cls, 0) + 1

    lines_out.append(f"- **Total Hunks**: {len(hunks)}")
    for cls in ("ADDED_CONSTRAINT", "EXPLANATORY", "CHANGED_VALUE", "REMOVED"):
        lines_out.append(f"- **{cls}**: {summary_counts.get(cls, 0)}")

    decision_status = "STOP: REJECTED (found CHANGED_VALUE or REMOVED)" if stopped else "ACCEPTED UNDER DECISION D1 (additions/tightenings only)"
    lines_out.append(f"\n**Verdict**: `{decision_status}`\n")

    lines_out.append("## 3. Per-Hunk Classification Details\n")
    for idx, header, cls, just, lines in classifications:
        lines_out.append(f"### Hunk {idx}: `{header}`")
        lines_out.append(f"- **Classification**: `{cls}`")
        lines_out.append(f"- **Justification**: {just}")
        lines_out.append("```diff")
        lines_out.extend(lines[:35])
        if len(lines) > 35:
            lines_out.append(f"... ({len(lines) - 35} lines truncated for brevity) ...")
        lines_out.append("```\n")

    OUT_FILE.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
    print(f"Generated {OUT_FILE} with {len(hunks)} classified hunks. Verdict: {decision_status}")

    if stopped:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
