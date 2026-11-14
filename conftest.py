"""Root pytest configuration and fixture setup.

Ensures that reference implementations relocated under A6.1 are available on the
semantics module namespace for legacy conformance tests without mutating the frozen
normative source on disk.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFORMANCE_DIR = ROOT / "10-CONFORMANCE"
RUNTIME_DIR = ROOT / "20-RUNTIME"
SRC_DIR = ROOT / "src"

for d in [str(SRC_DIR), str(CONFORMANCE_DIR), str(RUNTIME_DIR), str(ROOT)]:
    if d not in sys.path:
        sys.path.insert(0, d)

# Set PYTHONPATH in environment for any child subprocesses spawned during tests
cur_pypath = os.environ.get("PYTHONPATH", "")
extra_pypath = f"{ROOT}:{SRC_DIR}:{CONFORMANCE_DIR}:{RUNTIME_DIR}"
os.environ["PYTHONPATH"] = f"{extra_pypath}:{cur_pypath}" if cur_pypath else extra_pypath

import sitecustomize  # noqa: F401
