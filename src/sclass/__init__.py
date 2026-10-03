"""S-Class v6.0.1: Universal Trust and Control Plane."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_CONF = str(_ROOT / "10-CONFORMANCE")
_RUNT = str(_ROOT / "20-RUNTIME")

if _CONF not in sys.path:
    sys.path.insert(0, _CONF)
if _RUNT not in sys.path:
    sys.path.insert(0, _RUNT)

from sclass_runtime_v6_0_1 import *
from sclass_semantics_v6_0_1 import *

__version__ = "6.0.1"
