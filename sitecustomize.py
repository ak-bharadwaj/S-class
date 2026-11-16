"""Site-wide runtime customization for S-Class development and testing.

Limited strictly to non-semantic environment and path setup.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFORMANCE_DIR = ROOT / "10-CONFORMANCE"
RUNTIME_DIR = ROOT / "20-RUNTIME"
SRC_DIR = ROOT / "src"

for d in [str(SRC_DIR), str(CONFORMANCE_DIR), str(RUNTIME_DIR), str(ROOT)]:
    if d not in sys.path:
        sys.path.insert(0, d)

