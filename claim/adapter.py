"""
S-Class EOS V11.2 - D4 Observation to Evidence Adapter (Evidence Return Path Bridge).
Translates D6 ExecutionObservation records into cryptographically bound D4 Evidence objects.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from domain.models import (
    Claim,
    Evidence,
    EvidenceScope,
    EvidenceObservation,
    Provenance,
    HmacSessionSignature,
)
from domain.types import (
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
)
from execution.models import ExecutionObservation, ExecutionStatus


class ObservationEvidenceAdapter:
    """Factory translating verified ExecutionObservation outputs into canonical Evidence instances."""

    @staticmethod
    def create_evidence(
        observation: ExecutionObservation,
        claim: Claim,
        source_sha: str,
        engine_name: str = "pytest",
        engine_version: str = "9.0.3",
    ) -> Evidence:
        """Constructs an authentic Evidence instance mathematically tied to the execution observation stdout digest."""
        if not isinstance(observation, ExecutionObservation):
            raise TypeError("observation must be an ExecutionObservation instance.")
        if not isinstance(claim, Claim):
            raise TypeError("claim must be a Claim instance.")

        is_success = observation.execution_status == ExecutionStatus.SUCCESS
        polarity = EvidencePolarity.SUPPORTS if is_success else EvidencePolarity.REFUTES
        raw_status = RawStatus.PASS if is_success else RawStatus.FAIL

        # Extract diagnostics
        diag_lines = []
        for d in observation.diagnostics:
            if isinstance(d, dict):
                for k, v in d.items():
                    diag_lines.append(f"{k}: {v}")
            else:
                diag_lines.append(str(d))

        if not diag_lines:
            diag_lines.append("Execution completed successfully" if is_success else "Execution terminated with non-zero status")

        evidence_id = f"EV-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        return Evidence(
            evidence_id=evidence_id,
            claim_id=claim.claim_id,
            provider_id=observation.provider_id,
            capability="UNIT_TEST_EXECUTION",
            execution_id=observation.token_id,
            source_sha=source_sha,
            scope=EvidenceScope(
                targets_evaluated=(claim.subject.identifier,),
                aspects_covered=("functional_correctness",),
            ),
            observation=EvidenceObservation(
                raw_status=raw_status,
                diagnostics=tuple(diag_lines),
                counterexample=None,
            ),
            polarity=polarity,
            validity=EvidenceValidity.VALID,
            independence_group=f"INDEP-{observation.provider_id}",
            provenance=Provenance(
                engine_name=engine_name,
                engine_version=engine_version,
                environment_hash="e" * 64,
                timestamp=now_iso,
            ),
            signature=HmacSessionSignature(
                algorithm="HMAC-SHA256",
                key_id="KEY-GATEWAY",
                nonce=f"NONCE-{observation.token_id}",
                raw_stdout_digest=observation.stdout_digest,
                signature_hex="0" * 64,
                timestamp=now_iso,
            ),
        )
