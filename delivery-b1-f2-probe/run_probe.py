#!/usr/bin/env python3
import subprocess
from pathlib import Path

DIR = Path(__file__).resolve().parent

VERSIONS = ["3.10", "3.11", "3.12", "3.13"]
summary_lines = []

for v in VERSIONS:
    python_bin = f"/home/runner/venv-{v}/bin/python"
    log_file = DIR / f"probe_python_{v}.log"
    res = subprocess.run([python_bin, str(DIR / "f2_probe.py")], capture_output=True, text=True)
    log_file.write_text(res.stdout, encoding="utf-8")
    summary_lines.append(f"--- Python {v} ---")
    summary_lines.append(res.stdout.strip())
    summary_lines.append("")

summary_file = DIR / "probe_summary.txt"
summary_file.write_text("\n".join(summary_lines), encoding="utf-8")
print(f"Executed probe across {len(VERSIONS)} Python environments.")
