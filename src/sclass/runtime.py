"""Canonical S-Class v6.0.1 Runtime & Execution Gate."""

import sys
from pathlib import Path

_RUNT = str(Path(__file__).resolve().parents[2] / "20-RUNTIME")
if _RUNT not in sys.path:
    sys.path.insert(0, _RUNT)

from sclass_runtime_v6_0_1 import *
