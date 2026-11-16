"""Source scan integrity checker for CL compliance."""
import os
from pathlib import Path

patterns = [
    "_make_authorized_work_request",
    "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    'b"sig"',
    "obj-rev-1",
    "measured_tokens = 100",
    "measured_duration_ms = 50",
    "measured_tokens = 0",
    "measured_duration_ms = 0",
    "measured_tokens=0",
    "measured_duration_ms=0",
    "epoch-genesis",
    "causal-frontier/genesis",
    "target-snapshot/genesis",
]

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

hits = {p: [] for p in patterns}
for root, dirs, files in os.walk(SRC):
    if "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            p = Path(root) / f
            text = p.read_text(encoding="utf-8", errors="ignore")
            for pat in patterns:
                if pat in text:
                    hits[pat].append(str(p.relative_to(ROOT)))

all_clean = True
for pat, file_list in hits.items():
    print(f"{pat}: {len(file_list)} hits")
    if file_list:
        all_clean = False
        for f in file_list:
            print(f"  -> {f}")

if all_clean:
    print("\nALL MANDATORY SCANS REPORT ZERO HITS.")
else:
    raise SystemExit(1)
