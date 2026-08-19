"""D3 Policy Engine Strongly-Typed Immutable Data Models."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from types import MappingProxyType
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from domain.models import (
    Policy,
    PolicyRule,
    PolicyExpression,
    AsymmetricAuthoritySignature,
    Task,
    Obligation,
    Claim,
    Evidence,
    _freeze_nested,
    _validate_pattern,
    _validate_iso8601,
)
from domain.types import (
    PolicyScope,
    RuleType,
    CombinatorType,
    ClaimTier,
    ClaimStatus,
    EvidencePolarity,
    EvidenceValidity,
    RawStatus,
)
from policy.exceptions import PolicyValidationError, InvalidExceptionError

HEX_64_PATTERN = re.compile(r"^[a-f0-9]{64}$")
HEX_128_PATTERN = re.compile(r"^[a-f0-9]{128}$")
EXCEPTION_ID_PATTERN = re.compile(r"^EXC-[A-Za-z0-9_-]+$")
OBLIGATION_ID_PATTERN = re.compile(r"^OBL-[A-Za-z0-9_-]+$")
POLICY_ID_PATTERN = re.compile(r"^POL-[A-Za-z0-9_-]+$")


class PolicyDecisionType(str, Enum):
    """Deterministic categorical decision outcomes for policy evaluation."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_EXCEPTION = "REQUIRE_EXCEPTION"


@dataclass(frozen=True)
class AuthorizedActor:
    """Authorized human/security actor credentials granting a policy exception."""
    actor_id: str
    actor_role: str
    public_key_fingerprint: str

    def __post_init__(self):
        if not self.actor_id or not isinstance(self.actor_id, str):
            raise PolicyValidationError("actor_id must be a non-empty string.")
        if not self.actor_role or not isinstance(self.actor_role, str):
            raise PolicyValidationError("actor_role must be a non-empty string.")
        _validate_pattern(self.public_key_fingerprint, HEX_64_PATTERN, "public_key_fingerprint")


@dataclass(frozen=True)
class PolicyException:
    """Explicit, typed, cryptographically signed policy exception record (§3.5)."""
    exception_id: str
    obligation_id: str
    policy_id: str
    justification: str
    authorized_by: AuthorizedActor
    compensating_controls: Tuple[str, ...]
    signature: AsymmetricAuthoritySignature
    expiry: Optional[str] = None

    def __post_init__(self):
        _validate_pattern(self.exception_id, EXCEPTION_ID_PATTERN, "exception_id")
        _validate_pattern(self.obligation_id, OBLIGATION_ID_PATTERN, "obligation_id")
        _validate_pattern(self.policy_id, POLICY_ID_PATTERN, "policy_id")

        if not isinstance(self.justification, str) or len(self.justification) < 20:
            raise PolicyValidationError("justification must be a string with minLength: 20.")

        if not isinstance(self.authorized_by, AuthorizedActor):
            raise PolicyValidationError("authorized_by must be an AuthorizedActor instance.")

        if not isinstance(self.compensating_controls, (list, tuple)) or len(self.compensating_controls) < 1:
            raise PolicyValidationError("compensating_controls must contain at least 1 control.")
        for ctrl in self.compensating_controls:
            if not isinstance(ctrl, str) or len(ctrl) < 5:
                raise PolicyValidationError("Each compensating control must be a string with minLength: 5.")
        object.__setattr__(self, "compensating_controls", tuple(self.compensating_controls))

        if self.expiry is not None:
            _validate_iso8601(self.expiry, "expiry")

        if not isinstance(self.signature, AsymmetricAuthoritySignature):
            raise InvalidExceptionError("signature must be an AsymmetricAuthoritySignature instance.")


@dataclass(frozen=True)
class RuleEvaluationResult:
    """Individual rule evaluation verdict with rationale."""
    rule: PolicyRule
    passed: bool
    reason: str
    requires_exception: bool = False
    exception_applied: Optional[str] = None


@dataclass(frozen=True)
class PolicyDecision:
    """Deterministic, categorical decision result produced by the policy evaluator."""
    decision: PolicyDecisionType
    scope_evaluated: PolicyScope
    rules_evaluated: Tuple[RuleEvaluationResult, ...]
    unmet_requirements: Tuple[str, ...]
    exceptions_applied: Tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class EvidenceTrustCertificate:
    """Cryptographic trust certificate produced by an authoritative verifier and consumed by D3."""
    evidence_id: str
    source_sha: str
    is_verified: bool
    digest_verified: bool
    signature_verified: bool
    provenance_verified: bool
    verifier_identity: str = "Gate3EvidenceVerifier"
    rejection_reason: Optional[str] = None


@dataclass(frozen=True)
class PolicyEvaluationContext:
    """Immutable evaluation context capturing target obligation, claims, evidence, and exact revision binding."""
    obligation: Obligation
    claims: Tuple[Claim, ...]
    evidence: Tuple[Evidence, ...]
    exceptions: Tuple[PolicyException, ...] = field(default_factory=tuple)
    evaluation_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expected_source_sha: Optional[str] = None
    trust_certificates: Mapping[str, EvidenceTrustCertificate] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.obligation, Obligation):
            raise PolicyValidationError("obligation must be an Obligation instance.")
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "exceptions", tuple(self.exceptions))
        _validate_iso8601(self.evaluation_timestamp, "evaluation_timestamp")
        if self.expected_source_sha is not None:
            if not isinstance(self.expected_source_sha, str) or len(self.expected_source_sha) not in (40, 64):
                raise PolicyValidationError(f"Invalid expected_source_sha: '{self.expected_source_sha}'")
        object.__setattr__(self, "trust_certificates", MappingProxyType(dict(self.trust_certificates)))
