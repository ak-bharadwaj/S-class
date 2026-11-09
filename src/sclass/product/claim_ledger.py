"""S-Class Product Layer: Section F7 Claim Ledger & Reference Verification.

Normative Reference:
    R30 Master Product Design (FREEZE-CANDIDATE-v6.0.2), Section F7.
    Obligations: PD-F7-001 through PD-F7-006.

Core Invariants:
    1. Structured Claims (PD-F7-001): Every agent claim MUST be a structured record with
       claim_id, type, subject, and optional evidence_refs. Prose alone MUST NOT create a claim.
    2. Evidence Requirements (PD-F7-002): Behavioral and completion claims without resolvable
       kernel evidence references MUST remain unverified and MUST NOT satisfy a gate. Reference
       claims use evaluator-owned repository-intelligence resolution as their evidence.
    3. TargetSnapshot & Dependency Identity (PD-F7-003): Proposed symbols, imports, packages,
       and APIs MUST resolve against the TargetSnapshot and canonical dependency identity.
       Package digest mismatches fail closed. Packages MUST NEVER be resolved by name alone.
    4. Pre-Existing Reference Absence (PD-F7-004): A pre-existing reference (created_by_delta=False)
       absent from the pre-delta repository view MUST yield MISSING[PD-F7-004].
    5. Closed Claim-Type Registry (PD-F7-005): Claim types MUST use the closed v1 registry:
       reference, behavioral, completion. Each type MUST follow its declared evidence rule.
       Completion claims require governing obligation closure and cannot rely on agent self-report.
    6. Post-Delta Symbol Resolution (PD-F7-006): When created_by_delta=True, the claimed symbol
       MUST resolve in the post-delta repository overlay. Absence post-delta yields MISSING[PD-F7-006],
       regardless of pre-delta presence.
    7. Anti-Gaming / Fail-Closed: S-Class never parses prose to discover claims. Injected resolvers
       embedded inside candidate specs are strictly ignored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Set,
    Tuple,
    Union,
    runtime_checkable,
)

from sclass.product.artifacts import c1_canonical_encode, compute_content_digest

# -----------------------------------------------------------------------------
# Gate Vocabulary
# TEMPORARY: Import gate vocabulary from trust_model until Lane B is GPT-passed
# -----------------------------------------------------------------------------
from sclass.product.trust_model import GateOutput, GateState


# -----------------------------------------------------------------------------
# 1. Closed Registries (PD-F7-001, PD-F7-005)
# -----------------------------------------------------------------------------

class ClaimType(str, Enum):
    """Closed v1 registry of normative claim types (Section F7)."""
    REFERENCE = "reference"
    BEHAVIORAL = "behavioral"
    COMPLETION = "completion"


VALID_CLAIM_TYPES: FrozenSet[str] = frozenset({e.value for e in ClaimType})


class ReferenceKind(str, Enum):
    """Closed registry of reference kinds for reference-type claims."""
    SYMBOL = "symbol"
    IMPORT = "import"
    PACKAGE = "package"
    API = "api"


VALID_REFERENCE_KINDS: FrozenSet[str] = frozenset({e.value for e in ReferenceKind})


class EvaluatorResolution(str, Enum):
    """Evaluator reference resolution status."""
    RESOLVED = "RESOLVED"
    MISSING = "MISSING"


# -----------------------------------------------------------------------------
# 2. Claim Record Data Model (PD-F7-001)
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaimRecord:
    """Structured Agent Claim Record compliant with claim_record.json schema.
    
    Invariant: Every claim MUST be represented as {claim_id, type, subject, evidence_refs}.
    Prose alone MUST NOT create a claim (PD-F7-001).
    """
    claim_id: str
    type: str
    subject: str
    evidence_refs: Tuple[str, ...] = field(default_factory=tuple)
    reference_kind: Optional[str] = None
    created_by_delta: bool = False
    target_snapshot_ref: Optional[str] = None
    dependency_digest: Optional[str] = None
    expected_dependency_digest: Optional[str] = None
    canonical_dependency_set_digest: Optional[str] = None
    content_digest: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.claim_id or not isinstance(self.claim_id, str):
            raise ValueError("ClaimRecord requires a non-empty string 'claim_id'")
        if not self.type or not isinstance(self.type, str):
            raise ValueError("ClaimRecord requires a non-empty string 'type'")
        if not self.subject or not isinstance(self.subject, str):
            raise ValueError("ClaimRecord requires a non-empty string 'subject'")
        if type(self.created_by_delta) is not bool:
            raise ValueError(
                f"ClaimRecord requires 'created_by_delta' to be a strict boolean (True or False), got {type(self.created_by_delta).__name__}"
            )
        if self.reference_kind is not None:
            if not isinstance(self.reference_kind, str) or self.reference_kind not in VALID_REFERENCE_KINDS:
                raise ValueError(
                    f"ClaimRecord requires 'reference_kind' to be one of {sorted(VALID_REFERENCE_KINDS)} or None, got '{self.reference_kind}'"
                )

        # Ensure evidence_refs is an immutable tuple
        if not isinstance(self.evidence_refs, tuple):
            object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))

        # Compute content_digest if absent
        if not self.content_digest:
            payload_str = (
                f"{self.claim_id}|{self.type}|{self.reference_kind or ''}|"
                f"{self.subject}|{self.created_by_delta}|{','.join(sorted(self.evidence_refs))}"
            )
            raw = c1_canonical_encode(payload_str)
            computed = hashlib.sha256(raw).hexdigest()
            object.__setattr__(self, "content_digest", computed)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize claim to dictionary matching claim_record.json."""
        d: Dict[str, Any] = {
            "claim_id": self.claim_id,
            "type": self.type,
            "subject": self.subject,
            "created_by_delta": self.created_by_delta,
            "evidence_refs": list(self.evidence_refs),
            "content_digest": self.content_digest or "",
        }
        if self.reference_kind is not None:
            d["reference_kind"] = self.reference_kind
        if self.target_snapshot_ref is not None:
            d["target_snapshot_ref"] = self.target_snapshot_ref
        if self.dependency_digest is not None:
            d["dependency_digest"] = self.dependency_digest
        if self.expected_dependency_digest is not None:
            d["expected_dependency_digest"] = self.expected_dependency_digest
        if self.canonical_dependency_set_digest is not None:
            d["canonical_dependency_set_digest"] = self.canonical_dependency_set_digest
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ClaimRecord:
        """Construct ClaimRecord from a mapping."""
        if not isinstance(data, Mapping):
            raise ValueError("ClaimRecord.from_dict requires a Mapping")
        raw_delta = data.get("created_by_delta", False)
        if type(raw_delta) is not bool:
            raise ValueError(
                f"ClaimRecord.from_dict requires 'created_by_delta' to be a strict boolean (True or False), got {type(raw_delta).__name__}"
            )
        raw_kind = data.get("reference_kind")
        if raw_kind is not None:
            if not isinstance(raw_kind, str) or raw_kind not in VALID_REFERENCE_KINDS:
                raise ValueError(
                    f"ClaimRecord.from_dict requires 'reference_kind' to be one of {sorted(VALID_REFERENCE_KINDS)} or None, got '{raw_kind}'"
                )
        return cls(
            claim_id=str(data.get("claim_id", "")),
            type=str(data.get("type", "")),
            subject=str(data.get("subject", "")),
            evidence_refs=tuple(data.get("evidence_refs", ())),
            reference_kind=raw_kind,
            created_by_delta=raw_delta,
            target_snapshot_ref=data.get("target_snapshot_ref") or data.get("target_snapshot"),
            dependency_digest=data.get("dependency_digest"),
            expected_dependency_digest=data.get("expected_dependency_digest"),
            canonical_dependency_set_digest=data.get("canonical_dependency_set_digest"),
            content_digest=data.get("content_digest"),
        )


# -----------------------------------------------------------------------------
# 3. Protocols for Caller-Injected Intelligence & Resolvers (PD-F7-003, PD-F7-004, PD-F7-006)
# -----------------------------------------------------------------------------

@runtime_checkable
class RepositoryIntelligenceIndex(Protocol):
    """Protocol for resolving symbols, imports, and APIs against repository views."""
    def resolve_reference(self, kind: str, subject: str, post_delta: bool = False) -> bool:
        """Check whether a reference exists in pre-delta index or post-delta overlay."""
        ...


class InMemoryRepositoryIntelligenceIndex:
    """In-memory reference resolver for repository intelligence testing."""
    def __init__(
        self,
        pre_delta_symbols: Optional[Iterable[str]] = None,
        post_delta_overlay: Optional[Iterable[str]] = None,
    ):
        self.pre_delta_symbols: Set[str] = set(pre_delta_symbols or [])
        self.post_delta_overlay: Set[str] = set(post_delta_overlay or [])

    def resolve_reference(self, kind: str, subject: str, post_delta: bool = False) -> bool:
        if not isinstance(kind, str) or kind not in VALID_REFERENCE_KINDS:
            return False
        if post_delta:
            return subject in self.post_delta_overlay
        return subject in self.pre_delta_symbols


@runtime_checkable
class CanonicalDependencyResolver(Protocol):
    """Protocol for resolving package identities against CanonicalDependencySet."""
    def get_canonical_digest(self, package_name: str) -> Optional[str]:
        """Return the canonical digest for the package, or None if absent."""
        ...


class InMemoryCanonicalDependencyResolver:
    """In-memory dependency resolver."""
    def __init__(self, mapping: Optional[Mapping[str, str]] = None):
        self._mapping: Dict[str, str] = dict(mapping or {})

    def get_canonical_digest(self, package_name: str) -> Optional[str]:
        return self._mapping.get(package_name)


@runtime_checkable
class KernelEvidenceResolver(Protocol):
    """Protocol for resolving kernel evidence references."""
    def resolve_evidence(self, evidence_ref: str) -> bool:
        """Return True if evidence reference resolves to a valid, current kernel receipt."""
        ...


class InMemoryKernelEvidenceResolver:
    """In-memory kernel evidence resolver."""
    def __init__(self, valid_refs: Optional[Iterable[str]] = None):
        self.valid_refs: Set[str] = set(valid_refs or [])

    def resolve_evidence(self, evidence_ref: str) -> bool:
        return evidence_ref in self.valid_refs


@runtime_checkable
class ObligationClosureResolver(Protocol):
    """Protocol for verifying whether a governing obligation is closed by evidence."""
    def is_obligation_closed(self, obligation_ref: str) -> bool:
        """Return True if obligation is formally closed with admissible evidence."""
        ...


class InMemoryObligationClosureResolver:
    """In-memory obligation closure resolver."""
    def __init__(self, closed_obligations: Optional[Iterable[str]] = None):
        self.closed_obligations: Set[str] = set(closed_obligations or [])

    def is_obligation_closed(self, obligation_ref: str) -> bool:
        return obligation_ref in self.closed_obligations


# -----------------------------------------------------------------------------
# 4. Normative F7 Claim Evaluator (PD-F7-001 through PD-F7-006)
# -----------------------------------------------------------------------------

def evaluate_f7_claim(
    claim_or_spec: Union[ClaimRecord, Mapping[str, Any], str],
    *,
    repo_index: Optional[RepositoryIntelligenceIndex] = None,
    dependency_resolver: Optional[CanonicalDependencyResolver] = None,
    evidence_resolver: Optional[KernelEvidenceResolver] = None,
    obligation_resolver: Optional[ObligationClosureResolver] = None,
) -> GateOutput:
    """Normative evaluator for Section F7 claim ledger and reference verification.
    
    Evaluates an agent claim against the six normative MUSTs:
    - PD-F7-001: Structured claim format required. Prose alone rejected.
    - PD-F7-002: Behavioral and completion claims require resolvable evidence refs.
    - PD-F7-003: Packages and symbols must resolve against TargetSnapshot/dependency identity.
    - PD-F7-004: Pre-existing reference absent from pre-delta view yields MISSING[PD-F7-004].
    - PD-F7-005: Closed v1 registry enforcement and declared evidence rule compliance.
    - PD-F7-006: Delta-created symbol absent from post-delta overlay yields MISSING[PD-F7-006].
    """
    # -------------------------------------------------------------------------
    # MUST PD-F7-001: Prose alone MUST NOT create a claim; structured record required
    # -------------------------------------------------------------------------
    if isinstance(claim_or_spec, str):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="Prose alone MUST NOT create a claim; structured record required",
        )

    if not isinstance(claim_or_spec, (ClaimRecord, Mapping)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="Claim must be a structured ClaimRecord or Mapping",
        )

    # Convert to ClaimRecord or extract fields
    if isinstance(claim_or_spec, ClaimRecord):
        claim_id = claim_or_spec.claim_id
        c_type = claim_or_spec.type
        subject = claim_or_spec.subject
        evidence_refs = list(claim_or_spec.evidence_refs)
        reference_kind = claim_or_spec.reference_kind
        created_by_delta = claim_or_spec.created_by_delta
        expected_dep_digest = claim_or_spec.expected_dependency_digest or claim_or_spec.dependency_digest
        canonical_dep_digest = claim_or_spec.canonical_dependency_set_digest
        spec_dict: Mapping[str, Any] = claim_or_spec.to_dict()
    else:
        # Anti-gaming: Candidate-embedded resolvers are strictly ignored
        spec_dict = claim_or_spec
        claim_id = spec_dict.get("claim_id")
        c_type = spec_dict.get("type")
        subject = spec_dict.get("subject")
        raw_evidence = spec_dict.get("evidence_refs", [])
        evidence_refs = list(raw_evidence) if isinstance(raw_evidence, (list, tuple)) else []
        reference_kind = spec_dict.get("reference_kind")
        created_by_delta = spec_dict.get("created_by_delta", False)
        expected_dep_digest = spec_dict.get("expected_dependency_digest") or spec_dict.get("dependency_digest")
        canonical_dep_digest = spec_dict.get("canonical_dependency_set_digest")

    # Validate required structured fields (PD-F7-001)
    if not claim_id or not isinstance(claim_id, str):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="Structured claim missing required non-empty 'claim_id'",
        )
    if not c_type or not isinstance(c_type, str):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="Structured claim missing required non-empty 'type'",
        )
    if not subject or not isinstance(subject, str):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="Structured claim missing required non-empty 'subject'",
        )
    if type(created_by_delta) is not bool:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail=f"Structured claim field 'created_by_delta' must be a strict boolean (True or False), got {type(created_by_delta).__name__}",
        )

    # -------------------------------------------------------------------------
    # MUST PD-F7-005: Closed v1 registry enforcement
    # -------------------------------------------------------------------------
    if c_type not in VALID_CLAIM_TYPES:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-005",
            detail=f"Invalid claim type '{c_type}'; must be one of: {sorted(VALID_CLAIM_TYPES)}",
        )

    # -------------------------------------------------------------------------
    # MUST PD-F7-003: Closed ReferenceKind registry validation
    # -------------------------------------------------------------------------
    if reference_kind is not None:
        if not isinstance(reference_kind, str) or reference_kind not in VALID_REFERENCE_KINDS:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-003",
                detail=f"Invalid reference_kind '{reference_kind}'; must be one of: {sorted(VALID_REFERENCE_KINDS)}",
            )

    # -------------------------------------------------------------------------
    # MUST PD-F7-002: Behavioral claims require caller-injected KernelEvidenceResolver
    # -------------------------------------------------------------------------
    if c_type == ClaimType.BEHAVIORAL:
        if evidence_resolver is None:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-002",
                detail="Behavioral claim requires a caller-injected KernelEvidenceResolver; non-empty evidence_refs is not proof",
            )
        if not evidence_refs:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-002",
                detail="Behavioral claim lacks required evidence_refs",
            )
        for ref in evidence_refs:
            if not evidence_resolver.resolve_evidence(ref):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F7-002",
                    detail=f"Behavioral evidence_ref '{ref}' not found in kernel evidence store",
                )

    # -------------------------------------------------------------------------
    # MUST PD-F7-005 / PD-F7-002: Completion claims require obligation & evidence closure
    # -------------------------------------------------------------------------
    if c_type == ClaimType.COMPLETION:
        if obligation_resolver is None:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-005",
                detail="Completion claim requires a caller-injected ObligationClosureResolver; payload obligation_closed confers no authority",
            )
        obl_ref = spec_dict.get("obligation_ref") or subject
        if not obligation_resolver.is_obligation_closed(obl_ref):
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-005",
                detail=f"Governing obligation '{obl_ref}' is not closed by admissible evidence",
            )
        if evidence_resolver is None:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-002",
                detail="Completion claim requires a caller-injected KernelEvidenceResolver",
            )
        if not evidence_refs:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-002",
                detail="Completion claim lacks required evidence_refs",
            )
        for ref in evidence_refs:
            if not evidence_resolver.resolve_evidence(ref):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F7-002",
                    detail=f"Completion evidence_ref '{ref}' not found in kernel evidence store",
                )

    # -------------------------------------------------------------------------
    # MUST PD-F7-003: Package dependency digest verification (NEVER by name alone)
    # -------------------------------------------------------------------------
    if c_type == ClaimType.REFERENCE and reference_kind == ReferenceKind.PACKAGE:
        if dependency_resolver is None:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-003",
                detail="Package claim requires a caller-injected CanonicalDependencyResolver; candidate digests confer no authority",
            )
        canonical_digest = dependency_resolver.get_canonical_digest(subject)
        if canonical_digest is None:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-003",
                detail=f"Package '{subject}' absent from CanonicalDependencySet",
            )
        if not expected_dep_digest:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-003",
                detail=f"Package reference '{subject}' cannot be resolved by name alone without digest verification",
            )
        if expected_dep_digest != canonical_digest:
            return GateOutput(
                state=GateState.MISSING,
                must_id="PD-F7-003",
                detail=(
                    f"Package '{subject}' dependency digest mismatch: "
                    f"expected '{expected_dep_digest}', resolved '{canonical_digest}'"
                ),
            )

    # -------------------------------------------------------------------------
    # MUST PD-F7-006 & PD-F7-004: Reference Symbol Resolution Precedence
    # Precedence: created_by_delta determines whether PD-F7-006 or PD-F7-004 applies.
    # -------------------------------------------------------------------------
    if c_type == ClaimType.REFERENCE and reference_kind != ReferenceKind.PACKAGE:
        # 1. Delta-created references (created_by_delta=True) -> PD-F7-006
        if created_by_delta:
            if repo_index is None:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F7-006",
                    detail="Delta-created reference claim requires a caller-injected RepositoryIntelligenceIndex",
                )
            if not repo_index.resolve_reference(reference_kind or "symbol", subject, post_delta=True):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F7-006",
                    detail=f"Delta-created symbol '{subject}' absent from post-delta overlay in repository index",
                )

        # 2. Pre-existing references (created_by_delta=False) -> PD-F7-004
        else:
            if repo_index is None:
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F7-004",
                    detail="Pre-existing reference claim requires a caller-injected RepositoryIntelligenceIndex",
                )
            if not repo_index.resolve_reference(reference_kind or "symbol", subject, post_delta=False):
                return GateOutput(
                    state=GateState.MISSING,
                    must_id="PD-F7-004",
                    detail=f"Pre-existing reference '{subject}' absent from pre-delta view in repository index",
                )

    # All normative rules satisfied
    return GateOutput(
        state=GateState.SATISFIED,
        must_id=None,
        detail="All claim ledger and reference verification rules satisfied",
    )


# -----------------------------------------------------------------------------
# 5. Composite Ledger & Fixture Evaluator
# -----------------------------------------------------------------------------

def evaluate_f7_claim_ledger(
    spec: Mapping[str, Any],
    *,
    repo_index: Optional[RepositoryIntelligenceIndex] = None,
    dependency_resolver: Optional[CanonicalDependencyResolver] = None,
    evidence_resolver: Optional[KernelEvidenceResolver] = None,
    obligation_resolver: Optional[ObligationClosureResolver] = None,
) -> Union[GateOutput, Dict[str, GateOutput]]:
    """Evaluates composite Section F7 specifications and authoritative fixtures (F7-T1..F7-T6)."""
    if not isinstance(spec, Mapping) or not spec:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="F7 claim ledger specification must be a non-empty mapping",
        )

    # Case A: Fixture F7-T5 composite claim rules
    if "reference_claim" in spec and "behavioral_claim" in spec and "completion_claim" in spec:
        res_ref = evaluate_f7_claim(
            spec["reference_claim"],
            repo_index=repo_index,
            dependency_resolver=dependency_resolver,
            evidence_resolver=evidence_resolver,
            obligation_resolver=obligation_resolver,
        )
        res_beh = evaluate_f7_claim(
            spec["behavioral_claim"],
            repo_index=repo_index,
            dependency_resolver=dependency_resolver,
            evidence_resolver=evidence_resolver,
            obligation_resolver=obligation_resolver,
        )
        res_comp = evaluate_f7_claim(
            spec["completion_claim"],
            repo_index=repo_index,
            dependency_resolver=dependency_resolver,
            evidence_resolver=evidence_resolver,
            obligation_resolver=obligation_resolver,
        )
        return {
            "reference": res_ref,
            "behavioral": res_beh,
            "completion": res_comp,
        }

    # Case B: Fixture F7-T6 post-delta overlay test suite
    if "pre_delta_index" in spec and "post_delta_overlay" in spec:
        active_index = repo_index

        results: Dict[str, GateOutput] = {}

        # 1. Delta-created present case
        if "claim_subject" in spec:
            claim_rec = {
                "claim_id": "CL-T6-PRESENT",
                "type": "reference",
                "reference_kind": spec.get("reference_kind", "symbol"),
                "subject": spec["claim_subject"],
                "created_by_delta": spec.get("created_by_delta", True),
                "evidence_refs": [],
            }
            results["delta_created_present"] = evaluate_f7_claim(claim_rec, repo_index=active_index)

        # 2. Delta-created absent case
        if "absent_case_subject" in spec:
            absent_rec = {
                "claim_id": "CL-T6-ABSENT",
                "type": "reference",
                "reference_kind": spec.get("reference_kind", "symbol"),
                "subject": spec["absent_case_subject"],
                "created_by_delta": spec.get("absent_case_created_by_delta", True),
                "evidence_refs": [],
            }
            results["delta_created_absent"] = evaluate_f7_claim(absent_rec, repo_index=active_index)

        # 3. Pre-existing absent case
        if "pre_existing_absent_subject" in spec:
            pre_absent_rec = {
                "claim_id": "CL-T6-PRE-ABSENT",
                "type": "reference",
                "reference_kind": spec.get("reference_kind", "symbol"),
                "subject": spec["pre_existing_absent_subject"],
                "created_by_delta": spec.get("pre_existing_created_by_delta", False),
                "evidence_refs": [],
            }
            results["pre_existing_absent"] = evaluate_f7_claim(pre_absent_rec, repo_index=active_index)

        return results

    # Case C: Standard single claim evaluation
    return evaluate_f7_claim(
        spec,
        repo_index=repo_index,
        dependency_resolver=dependency_resolver,
        evidence_resolver=evidence_resolver,
        obligation_resolver=obligation_resolver,
    )


def evaluate_f7_claims(
    claims: Sequence[Union[ClaimRecord, Mapping[str, Any]]],
    *,
    repo_index: Optional[RepositoryIntelligenceIndex] = None,
    dependency_resolver: Optional[CanonicalDependencyResolver] = None,
    evidence_resolver: Optional[KernelEvidenceResolver] = None,
    obligation_resolver: Optional[ObligationClosureResolver] = None,
) -> GateOutput:
    """Evaluates a sequence of claims. Fails closed on the first missing/failing claim."""
    if not isinstance(claims, Sequence) or isinstance(claims, (str, bytes)):
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="Claims must be a non-string sequence",
        )
    if not claims:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail="No claims provided for evaluation",
        )
    try:
        for claim in claims:
            out = evaluate_f7_claim(
                claim,
                repo_index=repo_index,
                dependency_resolver=dependency_resolver,
                evidence_resolver=evidence_resolver,
                obligation_resolver=obligation_resolver,
            )
            if out.state != GateState.SATISFIED:
                return out
        return GateOutput(GateState.SATISFIED, detail="All claims in ledger satisfied")
    except Exception as e:
        return GateOutput(
            state=GateState.MISSING,
            must_id="PD-F7-001",
            detail=f"Adversarial or malformed claim rejected: {type(e).__name__}",
        )
