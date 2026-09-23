"""
S-Class Context and Handoff Layer.
"""

from sclass.context.handoff import HandoffContext, HandoffAssembler, HandoffPackage
from sclass.context.continuity import CrossPlatformContinuityEngine, ContinuityTransferResult
from sclass.context.assurance_handoff import AssuranceHandoff, assemble_assurance_handoff

__all__ = [
    "HandoffContext",
    "HandoffAssembler",
    "HandoffPackage",
    "CrossPlatformContinuityEngine",
    "ContinuityTransferResult",
    "AssuranceHandoff",
    "assemble_assurance_handoff",
]

