"""Canonical S-Class v6.0.1 Semantic Kernel."""

import sys
from pathlib import Path

_CONF = str(Path(__file__).resolve().parents[2] / "10-CONFORMANCE")
if _CONF not in sys.path:
    sys.path.insert(0, _CONF)

from sclass_semantics_v6_0_1 import *
