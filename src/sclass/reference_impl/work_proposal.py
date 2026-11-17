"""Non-authoritative reference scaffold WorkProposal.

Provided for development, testing, and reference execution where a compatible
constructor is needed without mutating the frozen semantics module.
"""
from __future__ import annotations

from typing import Any, Optional
from sclass_semantics_v6_0_1 import WorkProposal, Digest, StateBinding, RequestedEffect


class ReferenceWorkProposal(WorkProposal):
    """Reference implementation of WorkProposal with explicit constructor."""

    def __init__(
        self,
        proposal_id: str = "",
        node_id: str = "",
        request_content_digest: Optional[Digest] = None,
        state_binding: Optional[StateBinding] = None,
        context_digest: Optional[Digest] = None,
        requested_effect: Optional[RequestedEffect] = None,
        primary_obligation_id: Optional[str] = None,
    ):
        self.proposal_id = proposal_id
        self.node_id = node_id
        self.request_content_digest = request_content_digest
        self.state_binding = state_binding
        self.context_digest = context_digest
        self.requested_effect = requested_effect
        if primary_obligation_id is not None:
            self.primary_obligation_id = primary_obligation_id
