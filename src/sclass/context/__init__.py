"""
S-Class Context and Handoff Layer.
"""

from sclass.context.handoff import HandoffContext, HandoffAssembler, HandoffPackage
from sclass.context.continuity import CrossPlatformContinuityEngine, ContinuityTransferResult

__all__ = [
    "HandoffContext",
    "HandoffAssembler",
    "HandoffPackage",
    "CrossPlatformContinuityEngine",
    "ContinuityTransferResult",
]
