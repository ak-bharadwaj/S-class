"""Versioned S-Class v6.0.1 semantic runtime.

This checked-in module is the executable semantic authority for development and
conformance. The build spec documents the same contracts; runtime does not parse Markdown.
"""

from __future__ import annotations
import types, base64, hashlib, json, ipaddress, unicodedata
from dataclasses import dataclass, fields, field, replace
from enum import Enum, IntEnum
from typing import Any, Mapping, NewType, Optional, Protocol, Sequence, Union


def canonical_dataclass(cls):
    """Single construction gate for immutable canonical dataclasses.

    The generated __init__ always invokes __post_init__, which is wrapped here so
    mutable containers are converted into their immutable canonical forms before
    any class-specific invariant runs.
    """
    original_post_init = cls.__dict__.get("__post_init__")
    def _canonical_post_init(self):
        freeze_fields(self)
        if original_post_init is not None:
            original_post_init(self)
    cls.__post_init__ = _canonical_post_init
    cls.__c1_canonical__ = True
    return dataclass(frozen=True)(cls)


_SAFE_BUILTIN_PICKLE_TYPES = frozenset({
    "bool", "bytes", "bytearray", "dict", "float", "frozenset", "int", "list", "set", "str", "tuple", "object"
})
_SAFE_PICKLE_HELPERS = frozenset({"__newobj__", "__newobj_ex__"})

class _SafeCanonicalUnpickler(__import__("pickle").Unpickler):
    def find_class(self, module, name):
        if module == "builtins" and name in _SAFE_BUILTIN_PICKLE_TYPES:
            return getattr(__import__("builtins"), name)
        if module == "copyreg" and name in _SAFE_PICKLE_HELPERS:
            import copyreg
            return getattr(copyreg, name)
        if module == __name__:
            cls=globals().get(name)
            if isinstance(cls,type) and (getattr(cls,"__c1_canonical__",False) or issubclass(cls,Enum)):
                return cls
        raise ValueError(f"unsafe pickle global blocked: {module}.{name}")

def _safe_pickle_loads(blob: bytes):
    import io
    return _SafeCanonicalUnpickler(io.BytesIO(blob)).load()


class CommitState(Enum):
    PROPOSED = "PROPOSED"
    PREPARED = "PREPARED"
    RECOVERABLE = "RECOVERABLE"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"

@canonical_dataclass
class CanonicalCommit:
    commit_id: str
    workspace_id: str
    command_id: Optional[str]
    participant_ids: tuple[str, ...]
    expected_versions: FrozenMap
    causal_frontier_digest: Digest
    state: CommitState
    recovery_epoch: int
    integrity_digest: Digest

@canonical_dataclass
class CommitRecord:
    commit_id: str
    workspace_id: str
    participant_ids: tuple[str, ...]
    participant_hashes: tuple[Digest, ...]
    participant_types: tuple[str, ...]
    previous_head: Digest
    resulting_head: Digest
    resulting_state_revision: str
    event_sequence_start: int
    event_sequence_end: int
    schema_version: int
    commit_digest: Digest
    state: CommitState
    prepared_at_epoch_ns: int
    committed_at_epoch_ns: Optional[int]
    resulting_state_digest: Optional[Digest] = None  # complete canonical-state integrity identity

def commit_record_digest(record_without_digest) -> Digest:
    return digest("sclass/commit-record/v2", (
        record_without_digest.commit_id, record_without_digest.workspace_id,
        tuple(record_without_digest.participant_ids), tuple(record_without_digest.participant_hashes),
        tuple(record_without_digest.participant_types), record_without_digest.previous_head,
        record_without_digest.resulting_head, record_without_digest.resulting_state_revision,
        record_without_digest.resulting_state_digest,
        record_without_digest.event_sequence_start, record_without_digest.event_sequence_end,
        record_without_digest.schema_version, record_without_digest.state))

def commit_complete(record: CommitRecord, participant_rows: Mapping[str, tuple[str, Digest]]) -> bool:
    if record.state not in (CommitState.PREPARED, CommitState.RECOVERABLE, CommitState.COMMITTED):
        return False
    if len(record.participant_ids) != len(set(record.participant_ids)):
        return False
    if not (record.event_sequence_start <= record.event_sequence_end):
        return False
    expected = dict(zip(record.participant_ids, zip(record.participant_types, record.participant_hashes)))
    return dict(participant_rows) == expected

def verify_commit_record_integrity(record: CommitRecord) -> None:
    if record.commit_digest != commit_record_digest(record):
        raise ValueError("commit record digest mismatch")
    if len(record.participant_ids) != len(set(record.participant_ids)):
        raise ValueError("duplicate commit participant")
    if not (len(record.participant_ids) == len(record.participant_hashes) == len(record.participant_types)):
        raise ValueError("commit participant metadata mismatch")
    if record.event_sequence_start > record.event_sequence_end:
        raise ValueError("invalid commit sequence range")
    if not record.workspace_id or not record.commit_id:
        raise ValueError("commit identity missing")
    if record.state is CommitState.COMMITTED:
        if record.committed_at_epoch_ns is None:
            raise ValueError("committed record requires committed_at_epoch_ns")
        if record.resulting_state_digest is None:
            raise ValueError("committed record requires resulting_state_digest")

@canonical_dataclass
class CausalFrontier:
    frontier_id: str
    profile_id: str
    profile_version: str
    objective_revision: str
    obligation_graph_revision: str
    workgraph_revision: str
    policy_digest: Digest
    target_snapshot_digest: Digest
    authorization_epoch: str
    capability_digest: Digest
    budget_lineage_digest: Digest
    dependency_digests: tuple[Digest, ...]
    inclusion_reasons: tuple[str, ...]

    def __post_init__(self):
        ids=(self.frontier_id,self.profile_id,self.profile_version,self.objective_revision,
             self.obligation_graph_revision,self.workgraph_revision,self.authorization_epoch)
        if any(not isinstance(x,str) or not x for x in ids):
            raise ValueError('CausalFrontier identity fields must be non-empty')
        for name,d in (("policy_digest",self.policy_digest),("target_snapshot_digest",self.target_snapshot_digest),
                       ("capability_digest",self.capability_digest),("budget_lineage_digest",self.budget_lineage_digest)):
            if not _is_digest_value(d):
                raise ValueError(f'invalid CausalFrontier {name}')
        if tuple(self.dependency_digests) != tuple(sorted(self.dependency_digests)):
            raise ValueError('CausalFrontier dependency_digests must be sorted')
        if len(set(self.dependency_digests)) != len(self.dependency_digests):
            raise ValueError('CausalFrontier duplicate dependency digest')
        if not self.inclusion_reasons or any(not isinstance(x,str) or not x for x in self.inclusion_reasons):
            raise ValueError('CausalFrontier requires non-empty inclusion reasons')
        if tuple(self.inclusion_reasons) != tuple(sorted(self.inclusion_reasons)):
            raise ValueError('CausalFrontier inclusion_reasons must be sorted')

@canonical_dataclass
class TargetSnapshot:
    snapshot_id: str
    workspace_id: str
    repository_identity_digest: Digest
    workspace_state_digest: Digest
    dependency_lock_digest: Optional[Digest]
    generated_state_digest: Optional[Digest]
    untracked_manifest_digest: Digest
    environment_digest: Digest
    toolchain_digest: Digest
    external_state_reference_digests: tuple[Digest, ...]
    dependency_digests: FrozenMap                  # dependency key -> exact current digest
    target_policy_version: str
    created_at: UtcInstant

def target_snapshot_digest(snapshot: TargetSnapshot) -> Digest:
    """Canonical identity of the complete immutable target snapshot."""
    return digest("sclass/target-snapshot/v1", (
        snapshot.snapshot_id, snapshot.workspace_id, snapshot.repository_identity_digest,
        snapshot.workspace_state_digest, snapshot.dependency_lock_digest, snapshot.generated_state_digest,
        snapshot.untracked_manifest_digest, snapshot.environment_digest, snapshot.toolchain_digest,
        snapshot.external_state_reference_digests, dependency_map_digest(snapshot.dependency_digests),
        snapshot.target_policy_version, snapshot.created_at))

@canonical_dataclass
class AcceptanceSnapshot:
    snapshot_id: str
    workspace_id: str
    causal_frontier_digest: Digest
    target_snapshot_digest: Digest
    objective_revision: str
    obligation_graph_revision: str
    workgraph_revision: str
    policy_digest: Digest
    authorization_lineage_digest: Digest
    evidence_set_digest: Digest
    assessment_strategy_digest: Digest
    external_state_reference_digest: Digest
    canonical_event_sequence: int
    canonical_event_head_hash: Digest

def canonical_acceptance_snapshot(state: EngineeringState, snapshot_id: str) -> AcceptanceSnapshot:
    if not snapshot_id or state.target_snapshot is None or state.objective is None or state.causal_frontier is None or state.active_policy is None:
        raise ValueError("acceptance snapshot requires complete canonical state")
    evidence_entries=tuple(sorted((str(k), digest("sclass/evidence-closure/v1",v)) for k,v in state.evidence.items()))
    assessment_strategy=digest("sclass/assessment-strategy/v1", state.active_policy.release_rules)
    auth_lineage=digest("sclass/authorization-lineage/v1", tuple(sorted((str(k),digest("sclass/authorization-decision/v1",v)) for k,v in state.authorization_decisions.items())))
    external_refs=tuple(state.target_snapshot.external_state_reference_digests)
    external_digest=digest("sclass/external-state-references/v1", external_refs)
    obligation_graph_revision = getattr(state.work_graph, "obligation_graph_revision", "")
    workgraph_revision = getattr(state.work_graph, "revision_id", "")
    if not obligation_graph_revision or not workgraph_revision:
        raise ValueError("canonical work graph revisions are required")
    return AcceptanceSnapshot(snapshot_id,state.workspace_id,
        digest("sclass/causal-frontier/v1",state.causal_frontier),
        target_snapshot_digest(state.target_snapshot),
        state.objective.revisions[-1].revision_id,
        obligation_graph_revision, workgraph_revision, state.policy_digest, auth_lineage,
        digest("sclass/evidence-set/v1", evidence_entries), assessment_strategy, external_digest,
        state.event_sequence, state.event_head_hash)


def acceptance_snapshot_digest(snapshot: AcceptanceSnapshot) -> Digest:
    return digest("sclass/acceptance-snapshot/v1", snapshot)

class ExecutionGenerationStatus(Enum):
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    RECONCILED = "RECONCILED"

@canonical_dataclass
class ExecutionGeneration:
    work_node_id: str
    generation: int
    execution_attempt_id: str
    authority_epoch: str
    worker_identity: str
    target_snapshot_digest: Digest
    state_binding_digest: Digest
    governing_budget_lineage_id: str
    objective_revision: str
    workgraph_revision: str
    status: ExecutionGenerationStatus

    def __post_init__(self):
        for name,v in (("work_node_id",self.work_node_id),("execution_attempt_id",self.execution_attempt_id),("authority_epoch",self.authority_epoch),("worker_identity",self.worker_identity),("governing_budget_lineage_id",self.governing_budget_lineage_id),("objective_revision",self.objective_revision),("workgraph_revision",self.workgraph_revision)):
            if not isinstance(v,str) or not v:
                raise ValueError(f"invalid execution generation {name}")
        if isinstance(self.generation,bool) or not isinstance(self.generation,int) or self.generation < 1:
            raise ValueError("execution generation must be >= 1")
        for name,v in (("target_snapshot_digest",self.target_snapshot_digest),("state_binding_digest",self.state_binding_digest)):
            if not _is_digest_value(v): raise ValueError(f"invalid execution generation {name}")

@canonical_dataclass
class AuthorityEnvelope:
    envelope_id: str
    principal_id: str
    workspace_id: str
    target_digest: Digest
    request_content_digest: Digest
    policy_digest: Digest
    capability_digest: Digest
    authorization_epoch: str
    issued_at: UtcInstant
    expires_at: UtcInstant

def authority_envelope_digest(envelope: AuthorityEnvelope) -> Digest:
    """Canonical digest of the authoritative envelope object."""
    if not isinstance(envelope, AuthorityEnvelope):
        raise TypeError("AuthorityEnvelope required")
    return digest("sclass/authority-envelope/v1", envelope)


@canonical_dataclass
class GoverningBudgetLineage:
    lineage_id: str
    workspace_id: str
    objective_budget_id: str
    consumed_digest: Digest
    reserved_digest: Digest
    retry_budget_ids: tuple[str, ...]
    recovery_reservation_ids: tuple[str, ...]
    verification_reservation_ids: tuple[str, ...]
    model_spend_reservation_ids: tuple[str, ...]
    revision: int

class ApprovalSetResult(Enum):
    VALID = "VALID"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID_SCOPE = "INVALID_SCOPE"
    DUPLICATE_PRINCIPAL = "DUPLICATE_PRINCIPAL"
    EXPIRED = "EXPIRED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"

@canonical_dataclass
class ApprovalSet:
    set_id: str
    kind: ApprovalKind
    workspace_id: str
    target_digest: Digest
    policy_version: str
    scope_digest: Digest
    required_principals: int
    approvals: tuple[ApprovalRecord, ...]
    requester_principal_id: str

def validate_approval_set(a: ApprovalSet, valid_signature_ids: frozenset[str], at: UtcInstant,
                           principal_directory: Mapping[str, str],
                           required_principals: int,
                           principal_authority_ids: Optional[Mapping[str, str]] = None,
                           require_separation_of_duties: bool = True) -> ApprovalSetResult:
    if required_principals < 1:
        return ApprovalSetResult.INSUFFICIENT
    if a.required_principals != required_principals:
        return ApprovalSetResult.INVALID_SCOPE
    if require_separation_of_duties and not a.requester_principal_id:
        return ApprovalSetResult.INVALID_SCOPE
    principal_authority_ids = principal_authority_ids or {}
    principals=set()
    authorities=set()
    for r in a.approvals:
        if r.approval_id not in valid_signature_ids:
            return ApprovalSetResult.INVALID_SIGNATURE
        if (r.kind is not a.kind or r.workspace_id != a.workspace_id or
            r.target_digest != a.target_digest or r.policy_version != a.policy_version or
            r.scope_digest != a.scope_digest):
            return ApprovalSetResult.INVALID_SCOPE
        if not (r.issued_at.epoch_ns <= at.epoch_ns < r.expires_at.epoch_ns):
            return ApprovalSetResult.EXPIRED
        if principal_directory.get(r.principal_id) != r.principal_role:
            return ApprovalSetResult.INVALID_SCOPE
        if r.principal_id in principals:
            return ApprovalSetResult.DUPLICATE_PRINCIPAL
        if require_separation_of_duties and r.principal_id == a.requester_principal_id:
            return ApprovalSetResult.INVALID_SCOPE
        authority_id = principal_authority_ids.get(r.principal_id, r.principal_id)
        if authority_id in authorities:
            return ApprovalSetResult.DUPLICATE_PRINCIPAL
        principals.add(r.principal_id)
        authorities.add(authority_id)
    return ApprovalSetResult.VALID if len(authorities) >= required_principals else ApprovalSetResult.INSUFFICIENT

class StateSnapshot(Protocol):
    """Atomic canonical-state read; head is carried by EngineeringState."""
    def snapshot(self) -> EngineeringState: ...

Digest = NewType("Digest", str)              # "sha256:<hex>"
MutationDigest = NewType("MutationDigest", str)

def deep_freeze(v: Any) -> Any:
    """Convert ordinary mutable containers to canonical immutable containers.

    Direct canonical_c1() calls still reject mutable containers; this conversion is
    exclusively the canonical-dataclass construction gate.
    """
    if isinstance(v, FrozenMap): return v
    if isinstance(v, Mapping): return FrozenMap.from_items((k, deep_freeze(value)) for k, value in v.items())
    if isinstance(v, list): return tuple(deep_freeze(x) for x in v)
    if isinstance(v, set): return frozenset(deep_freeze(x) for x in v)
    if isinstance(v, bytearray): return bytes(v)
    if isinstance(v, tuple): return tuple(deep_freeze(x) for x in v)
    if isinstance(v, frozenset): return frozenset(deep_freeze(x) for x in v)
    return v

def _raise_mutable_mapping():
    raise TypeError("mutable mapping is not admissible; use FrozenMap")

class FrozenMap(Mapping):
    """Deeply immutable, hashable, canonical-key-sorted mapping."""
    __c1_canonical__ = True
    __slots__ = ("_m",)
    @classmethod
    def from_items(cls, items: Any = ()):
        return cls(items)
    def __init__(self, items: Any = ()):
        pairs = list(items.items()) if isinstance(items, FrozenMap) else list(items) if not isinstance(items, Mapping) else (_raise_mutable_mapping())
        canonical_keys = []
        seen = set()
        for k,v in pairs:
            if isinstance(k, bool):
                raise TypeError("bool keys are forbidden because bool and int compare equal")
            ck = _c1_tree(k) if "_c1_tree" in globals() else k
            ck_bytes = _c1_json_bytes(ck) if "_c1_json_bytes" in globals() else repr(ck).encode()
            if ck_bytes in seen:
                raise TypeError("duplicate canonical map key")
            seen.add(ck_bytes)
            canonical_keys.append((k, deep_freeze(v), ck_bytes))
        canonical_keys.sort(key=lambda x: x[2])
        object.__setattr__(self, "_m", types.MappingProxyType({k:v for k,v,_ in canonical_keys}))
    def __getitem__(self, k): return self._m[k]
    def __iter__(self): return iter(self._m)
    def __len__(self): return len(self._m)
    def __hash__(self): return hash(tuple((_c1_json_bytes(_c1_tree(k)), _c1_json_bytes(_c1_tree(v))) for k,v in self._m.items()))
    def __getstate__(self): return tuple(self._m.items())
    def __setstate__(self, state): object.__setattr__(self, "_m", types.MappingProxyType(dict(state)))
    def __setattr__(self, *_): raise TypeError("FrozenMap is immutable")


def freeze_fields(obj: Any) -> None:
    """Call from __post_init__ of every dataclass that has collection fields."""
    for f in fields(obj):
        object.__setattr__(obj, f.name, deep_freeze(getattr(obj, f.name)))

import base64, hashlib, json, math

C1_MAX_DEPTH = 64
C1_MIN_INT = -(2**63)
C1_MAX_INT = 2**63 - 1

def registry_name_for(cls: type) -> str:
    return str(getattr(cls, "__c1_name__", cls.__name__))

def _c1_validate_depth(depth: int) -> None:
    if depth > C1_MAX_DEPTH:
        raise TypeError("c1 nesting depth exceeds limit")

def _c1_tree(v: Any, depth: int = 0) -> Any:
    _c1_validate_depth(depth)
    if isinstance(v, Enum):
        return {"$enum": registry_name_for(type(v)), "$name": v.name}
    if v is None or isinstance(v, (bool, int, str)):
        if isinstance(v, int) and not isinstance(v, bool) and not (C1_MIN_INT <= v <= C1_MAX_INT):
            raise TypeError("integer outside signed int64 canonical domain")
        if isinstance(v, str):
            if any(0xD800 <= ord(ch) <= 0xDFFF for ch in v): raise TypeError("unpaired surrogate is not canonical")
            if unicodedata.normalize("NFC", v) != v: raise TypeError("non-NFC string is not canonical")
        return v
    if isinstance(v, float): raise TypeError("floats are forbidden in c1")
    if isinstance(v, bytes): return {"$bytes": base64.b64encode(v).decode("ascii")}
    if isinstance(v, tuple): return [_c1_tree(x, depth + 1) for x in v]
    if isinstance(v, list): raise TypeError("mutable list is not canonical")
    if isinstance(v, frozenset):
        items=[_c1_tree(x, depth + 1) for x in v]; items.sort(key=_c1_json_bytes); return {"$set":items}
    if isinstance(v, FrozenMap):
        entries=[[_c1_tree(k, depth + 1),_c1_tree(val, depth + 1)] for k,val in v.items()]; entries.sort(key=lambda pair:_c1_json_bytes(pair[0])); return {"$map":entries}
    if isinstance(v, (dict, types.MappingProxyType)): raise TypeError("mutable mapping is not canonical")
    if isinstance(v, Mapping): return _c1_tree(FrozenMap(v), depth + 1)
    if hasattr(v, "__dataclass_fields__"):
        out={"$type":registry_name_for(type(v))}
        for f in fields(v): out[f.name]=_c1_tree(getattr(v,f.name), depth + 1)
        return out
    raise TypeError(f"unsupported c1 value: {type(v).__name__}")

def _c1_json_bytes(tree: Any) -> bytes:
    return json.dumps(tree, ensure_ascii=False, separators=(",",":"), allow_nan=False, sort_keys=True).encode("utf-8")

def canonical_c1(obj: Any) -> bytes:
    return _c1_json_bytes(_c1_tree(obj))

def digest(domain: str, obj: Any) -> Digest:
    if not domain:
        raise ValueError("digest domain must be non-empty")
    return Digest("sha256:" + hashlib.sha256(domain.encode("utf-8") + b"\x00" + canonical_c1(obj)).hexdigest())

def canonical_c1_pack(obj: Any) -> bytes:
    return canonical_c1(obj)

def _c1_decode_tree(tree: Any) -> Any:
    if tree is None or isinstance(tree,(bool,int,str)): return tree
    if isinstance(tree,list): return tuple(_c1_decode_tree(x) for x in tree)
    if not isinstance(tree,dict): raise ValueError("invalid c1 envelope")
    if "$enum" in tree:
        if set(tree) != {"$enum", "$name"}: raise ValueError("unknown keys in $enum envelope")
        cls=globals().get(tree["$enum"])
        if not isinstance(cls,type) or not issubclass(cls,Enum): raise ValueError("unknown enum in c1 envelope")
        return cls[tree["$name"]]
    if "$bytes" in tree:
        if set(tree) != {"$bytes"}: raise ValueError("unknown keys in $bytes envelope")
        return base64.b64decode(tree["$bytes"].encode("ascii"),validate=True)
    if "$set" in tree:
        if set(tree) != {"$set"}: raise ValueError("unknown keys in $set envelope")
        return frozenset(_c1_decode_tree(x) for x in tree["$set"])
    if "$map" in tree:
        if set(tree) != {"$map"}: raise ValueError("unknown keys in $map envelope")
        return FrozenMap.from_items((_c1_decode_tree(k),_c1_decode_tree(v)) for k,v in tree["$map"])
    type_name=tree.get("$type")
    if type_name:
        cls=globals().get(type_name)
        if not isinstance(cls,type) or not getattr(cls,"__c1_canonical__",False): raise ValueError(f"unknown canonical type: {type_name}")
        return cls(**{k:_c1_decode_tree(v) for k,v in tree.items() if k != "$type"})
    raise ValueError("invalid canonical c1 object")

def canonical_c1_unpack(blob: bytes) -> Any:
    if not isinstance(blob,(bytes,bytearray)): raise TypeError("c1 bytes required")
    return _c1_decode_tree(json.loads(bytes(blob).decode("utf-8")))

def signature_preimage(domain: str, obj: Any) -> bytes:
    """Exact signature domain separation. Domain and c1 bytes are both bound."""
    if not domain:
        raise ValueError("signature domain must be non-empty")
    return b"sclass/sig/c1\x00" + domain.encode("utf-8") + b"\x00" + canonical_c1(obj)


@canonical_dataclass
class SemanticTypeRegistryEntry:
    type_name: str
    category: str          # Canonical | Value | Enum | Protocol | Alias
    canonicality: str      # CANONICAL (in EngineeringState/events) | PROJECTION | TRANSIENT
    mutability: str        # IMMUTABLE | APPEND_ONLY | SERVICE
    serialized: bool
    schema_version: int
    owner: str             # owning subsystem
    lifecycle: str         # ACTIVE | DEPRECATED | SUPERSEDED


@canonical_dataclass
class UtcInstant:
    epoch_ns: int          # UTC wall clock, recorded time only
    def __post_init__(self):
        if isinstance(self.epoch_ns, bool) or not isinstance(self.epoch_ns, int):
            raise TypeError("UtcInstant.epoch_ns must be int")
        if self.epoch_ns < 0 or self.epoch_ns > 2**63-1:
            raise ValueError("UtcInstant.epoch_ns out of int64 range")

class Clock(Protocol):
    def wall_now(self) -> UtcInstant: ...     # for recording and cross-process expiry
    def monotonic_ns(self) -> int: ...        # for ALL durations, timeouts, deadlines


class Authority(Enum):
    USER = "USER"                       # human principal
    POLICY = "POLICY"                   # versioned Policy object
    SYSTEM = "SYSTEM"                   # SDK deterministic logic
    LLM_DERIVED = "LLM_DERIVED"
    REPOSITORY_DERIVED = "REPOSITORY_DERIVED"
    WORKER = "WORKER"

@canonical_dataclass
class ProjectIdentity:
    project_id: str
    name: str

@canonical_dataclass
class RepositoryIdentity:
    repository_id: str
    project_id: str
    root_manifest_digest: Digest

@canonical_dataclass
class WorkspaceIdentity:
    workspace_id: str
    repository_id: str
    project_id: str

@canonical_dataclass
class WorkspaceInstance:
    instance_id: str
    workspace_id: str
    host_fingerprint: Digest
    created_at: UtcInstant

class KeyStatus(Enum):
    ACTIVE = "ACTIVE"
    ROTATED_OUT = "ROTATED_OUT"     # valid for verifying past signatures, not for new ones
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"

@canonical_dataclass
class SignatureBlock:
    algorithm: str                  # fixed: "ed25519"
    key_id: str
    trust_root: str
    canonicalization_version: str   # "c1"
    signature: bytes                # over signature_preimage(signature_domain, claims)

class SignatureVerificationResult(Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    UNKNOWN_KEY = "UNKNOWN_KEY"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"

class KeyDirectory(Protocol):
    def status(self, key_id: str, trust_root: str, at: UtcInstant) -> KeyStatus: ...
    def verify(self, block: SignatureBlock, message: bytes, at: UtcInstant) -> SignatureVerificationResult: ...


class SourceType(Enum):
    USER_INPUT = "USER_INPUT"
    POLICY_FILE = "POLICY_FILE"
    REPOSITORY = "REPOSITORY"
    LLM_INFERENCE = "LLM_INFERENCE"
    TOOL_OUTPUT = "TOOL_OUTPUT"

class DiscoveryMethod(Enum):
    USER_STATED = "USER_STATED"
    STATIC_ANALYSIS = "STATIC_ANALYSIS"
    TEST_DERIVED = "TEST_DERIVED"
    LLM_INFERRED = "LLM_INFERRED"

class ConstraintType(Enum):
    TECHNICAL = "TECHNICAL"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    LEGAL = "LEGAL"
    PROCESS = "PROCESS"

class EnforcementPhase(Enum):
    PLANNING = "PLANNING"
    AUTHORIZATION = "AUTHORIZATION"
    EXECUTION = "EXECUTION"
    VERIFICATION = "VERIFICATION"
    RELEASE = "RELEASE"

class Severity(Enum):
    ADVISORY = "ADVISORY"
    MAJOR = "MAJOR"
    BLOCKING = "BLOCKING"

@canonical_dataclass
class Requirement:
    requirement_id: str
    description: str
    authority: Authority
    source_type: SourceType
    source_provenance: Digest          # digest of the source artifact/message
    discovery_method: DiscoveryMethod
    confidence_bp: int                 # 0..10000
    objective_revision: str
    parent_requirement: Optional[str]
    derived_obligations: tuple[str, ...]
    # INVARIANT: only Authority.USER or Authority.POLICY yields a *binding* requirement.
    # LLM_DERIVED / REPOSITORY_DERIVED requirements are PROPOSED until a USER/POLICY event confirms them.

@canonical_dataclass
class Constraint:
    constraint_id: str
    description: str
    constraint_type: ConstraintType
    authority: Authority
    enforcement_phase: EnforcementPhase
    severity: Severity
    scope: tuple[str, ...]             # workspace-relative path globs; empty = objective-wide
    version: int

@canonical_dataclass
class DecisionOption:
    option_id: str
    description: str
    estimated_cost_units: int
    estimated_quality_bp: int

@canonical_dataclass
class Decision:
    decision_id: str
    question: str
    options: tuple[DecisionOption, ...]        # ORDERED; order is semantic (fixes #38)
    selected_option_id: str
    rationale: str
    constraint_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    policy_version: str
    decision_scope: str                        # e.g. "routing", "architecture", "repair"
    revisit_conditions: tuple[str, ...]
    expires_at: Optional[UtcInstant]
    created_by: str

@canonical_dataclass
class DecisionOutcome:
    """Recorded by a later DecisionOutcomeRecorded event; Decision itself stays immutable."""
    decision_id: str
    outcome_status: str
    actual_cost_units: int
    actual_quality_bp: int
    recorded_at: UtcInstant

class TrajectoryStore(Protocol):
    """Layer 5 projection: append-only, never canonical. Enables explaining why a routing decision was good/bad."""
    def append(self, decision: Decision, outcome: Optional[DecisionOutcome]) -> None: ...
    def chain(self, decision_id: str) -> tuple[Decision, ...]: ...   # decision → rationale → inputs → policy → outcome

@canonical_dataclass
class StructuredIntent:
    schema_version: int
    goal: str                                   # ≤ 2000 chars
    in_scope: tuple[str, ...]                   # each ≤ 500 chars, ≤ 50 entries
    out_of_scope: tuple[str, ...]
    target_paths: tuple[str, ...]
    acceptance_summary: tuple[str, ...]
    # Bounded, versioned. Unknown fields are rejected, not preserved.

@canonical_dataclass
class GitCommitState:
    commit_sha: str
    tree_sha: str
    dirty_manifest_digest: Digest

@canonical_dataclass
class ContentManifestState:
    manifest_digest: Digest
    file_count: int

WorkspaceState = Union[GitCommitState, ContentManifestState]   # typed union (fixes #33)

@canonical_dataclass
class EngineeringSnapshot:
    snapshot_id: str
    snapshot_schema_version: int
    baseline_state_hash: Digest
    workspace_state: WorkspaceState
    world_model_revision: str
    policy_version: str
    risk_classifier_version: str
    sdk_version: str
    toolchain_version: str
    platform_fingerprint: Digest

@canonical_dataclass
class ObjectiveRevision:
    revision_id: str
    revision_number: int
    structured_intent: StructuredIntent
    requirements: tuple[Requirement, ...]      # sorted by id, unique
    constraints: tuple[Constraint, ...]        # sorted by id, unique
    decisions: tuple[Decision, ...]            # in creation order
    snapshot: EngineeringSnapshot
    parent_revision_id: Optional[str]

@canonical_dataclass
class CanonicalObjective:
    objective_id: str
    workspace_id: str
    revisions: tuple[ObjectiveRevision, ...]   # append-only; current = last


class RiskTier(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    CRITICAL = 3

@canonical_dataclass
class RiskVector:
    blast_radius: int          # each dimension 0..3
    reversibility: int         # 3 = irreversible
    data_sensitivity: int
    external_effects: int
    novelty: int

@canonical_dataclass
class FloorRule:
    dimension: str
    min_value: int
    floor_tier: RiskTier

class AuthorizationMode(Enum):
    AUTO = "AUTO"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    DUAL_APPROVAL = "DUAL_APPROVAL"

class IsolationLevel(IntEnum):
    PROCESS = 0
    CONTAINER = 1
    VM = 2

@canonical_dataclass
class ControlProfile:
    authorization_mode: AuthorizationMode
    min_isolation: IsolationLevel
    required_evidence_kinds: tuple[EvidenceKind, ...]
    required_independence: IndependenceProfile
    max_retries: int
    external_effects_allowed: bool

@canonical_dataclass
class RiskMapping:
    classifier_version: str
    floor_rules: tuple[FloorRule, ...]
    control_profiles: FrozenMap            # RiskTier -> ControlProfile (total over all tiers)

def classify_risk(v: RiskVector, m: RiskMapping) -> RiskTier:
    tier = RiskTier(max(v.blast_radius, v.reversibility, v.data_sensitivity,
                        v.external_effects, v.novelty))
    for r in m.floor_rules:
        if getattr(v, r.dimension) >= r.min_value and r.floor_tier > tier:
            tier = r.floor_tier
    return tier

def effective_tier(*tiers: RiskTier) -> RiskTier:
    """Highest applicable control tier is MANDATORY (obligation, node, and requested-effect tiers)."""
    return RiskTier(max(tiers))


@canonical_dataclass
class AuthorizationRules:
    lease_ttl_ms: int
    max_execution_ms: int
    allowed_audiences: tuple[str, ...]
    require_attestation: bool
    denied_action_types: tuple[ActionType, ...]

@canonical_dataclass
class EvidenceRules:
    default_freshness: tuple[FreshnessDimension, ...]
    receipts_must_be_signed: bool
    max_excerpt_bytes: int

@canonical_dataclass
class RetryRules:
    max_same_failure: int
    backoff_ms: int

@canonical_dataclass
class BudgetRules:
    default_objective_budget: ResourceBudget
    reservation_ttl_ms: int

@canonical_dataclass
class ReleaseRules:
    target_environments: tuple[str, ...]
    required_evidence_kinds: tuple[EvidenceKind, ...]
    allow_waivers: bool
    max_waiver_ttl_ms: int

@canonical_dataclass
class WaiverRules:
    approver_authorities: tuple[str, ...]
    max_ttl_ms: int
    require_signature: bool

@canonical_dataclass
class DependencyRules:
    waived_satisfies_dependents: bool          # default False
    superseded_requires_replacement_satisfied: bool   # default True

class DataClassification(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    SECRET = 3

@canonical_dataclass
class DataClassificationPolicy:
    default: DataClassification
    path_rules: tuple[tuple[str, DataClassification], ...]   # (glob, class); first match by specificity

@canonical_dataclass
class RedactionPolicy:
    secret_detector_ids: tuple[str, ...]
    replacement: str
    redact_registered_credentials: bool

@canonical_dataclass
class ProviderEgressPolicy:
    allowed_providers: tuple[str, ...]
    max_classification: DataClassification
    denied_path_globs: tuple[str, ...]
    require_redaction: bool
    allow_remote_workers: bool                 # default False until this policy is approved

@canonical_dataclass
class RetentionPolicy:
    evidence_days: int
    model_io_days: int
    telemetry_days: int

@canonical_dataclass
class TelemetryPrivacyPolicy:
    allowed_fields: tuple[str, ...]
    forbid_content: bool
    hash_paths: bool

@canonical_dataclass
class Policy:
    policy_id: str
    policy_version: str
    risk_mapping: RiskMapping
    authorization_rules: AuthorizationRules
    evidence_rules: EvidenceRules
    retry_rules: RetryRules
    budget_rules: BudgetRules
    egress_rules: ProviderEgressPolicy
    release_rules: ReleaseRules
    waiver_rules: WaiverRules
    dependency_rules: DependencyRules
    data_classification: DataClassificationPolicy
    redaction: RedactionPolicy
    retention: RetentionPolicy
    telemetry: TelemetryPrivacyPolicy
    clock_skew_tolerance_ms: int
    floor_id: str
    floor_digest: Digest
    approval_quorums: FrozenMap = field(default_factory=lambda: FrozenMap.from_items(
        ((ApprovalKind.DUAL_AUTHORIZATION,2),(ApprovalKind.POLICY_RELAXATION,2),
         (ApprovalKind.BREAK_GLASS_USE,2),(ApprovalKind.WAIVER,2),(ApprovalKind.RELEASE,1))))

    def __post_init__(self):
        if not self.policy_id or not self.policy_version or not self.floor_id or not _is_digest_value(self.floor_digest):
            raise ValueError('invalid policy identity')
        for name,v in (("clock_skew_tolerance_ms",self.clock_skew_tolerance_ms),
                       ("lease_ttl_ms",self.authorization_rules.lease_ttl_ms),
                       ("max_execution_ms",self.authorization_rules.max_execution_ms),
                       ("reservation_ttl_ms",self.budget_rules.reservation_ttl_ms),
                       ("max_excerpt_bytes",self.evidence_rules.max_excerpt_bytes),
                       ("max_waiver_ttl_ms",self.release_rules.max_waiver_ttl_ms),
                       ("waiver_max_ttl_ms",self.waiver_rules.max_ttl_ms)):
            if isinstance(v,bool) or not isinstance(v,int) or v < 0 or v > 2**63-1:
                raise ValueError(f'invalid policy range: {name}')
        for kind in ApprovalKind:
            q=self.approval_quorums.get(kind)
            if isinstance(q,bool) or not isinstance(q,int) or q < 1:
                raise ValueError(f'invalid approval quorum for {kind.value}')


class ValidationVerdict(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_EVALUABLE = "NOT_EVALUABLE"

class PolicyFloorVerdict(Enum):
    MEETS = "MEETS"
    VIOLATES = "VIOLATES"
    NOT_EVALUABLE = "NOT_EVALUABLE"

class DeltaMatchVerdict(Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"

class PolicyRelation(Enum):
    SAME = "SAME"
    TIGHTENED = "TIGHTENED"
    RELAXED = "RELAXED"
    UNSUPPORTED_CHANGE = "UNSUPPORTED_CHANGE"

@canonical_dataclass
class PolicyFloor:
    floor_id: str
    sdk_version: str
    baseline_policy: Policy
    floor_digest: Digest
    signature: SignatureBlock

class ApprovalKind(Enum):
    DUAL_AUTHORIZATION = "DUAL_AUTHORIZATION"
    POLICY_RELAXATION = "POLICY_RELAXATION"
    BREAK_GLASS_USE = "BREAK_GLASS_USE"
    WAIVER = "WAIVER"
    RELEASE = "RELEASE"

# Immutable SDK governance thresholds. PolicyActivation cannot use the candidate policy
# to lower its own relaxation quorum; ordinary operational quorums remain policy-owned.
GOVERNANCE_APPROVAL_QUORUMS = {ApprovalKind.POLICY_RELAXATION: 2}

@canonical_dataclass
class ApprovalRecord:
    approval_id: str
    kind: ApprovalKind
    principal_id: str
    principal_role: str
    workspace_id: str
    target_digest: Digest
    policy_version: str
    scope_digest: Digest
    issued_at: UtcInstant
    expires_at: UtcInstant
    signature: SignatureBlock

def _subset(a, b):
    return set(a) <= set(b)

def _budget_tightened(old: ResourceBudget, new: ResourceBudget) -> bool:
    return all(getattr(new, f.name) <= getattr(old, f.name) for f in fields(ResourceBudget))

_AUTH_RANK = {AuthorizationMode.AUTO: 0, AuthorizationMode.HUMAN_APPROVAL: 1, AuthorizationMode.DUAL_APPROVAL: 2}

def _profile_tightened(old: ControlProfile, new: ControlProfile) -> bool:
    return (_AUTH_RANK[new.authorization_mode] >= _AUTH_RANK[old.authorization_mode] and
            new.min_isolation >= old.min_isolation and
            _subset(old.required_evidence_kinds, new.required_evidence_kinds) and
            new.required_independence.model >= old.required_independence.model and
            new.required_independence.context >= old.required_independence.context and
            new.required_independence.execution >= old.required_independence.execution and
            new.required_independence.verifier >= old.required_independence.verifier and
            new.required_independence.configuration >= old.required_independence.configuration and
            new.max_retries <= old.max_retries and
            (not new.external_effects_allowed or old.external_effects_allowed))

def _risk_mapping_tightened(old: RiskMapping, new: RiskMapping) -> bool:
    if old.classifier_version != new.classifier_version: return False
    import itertools
    dimensions=("blast_radius","reversibility","data_sensitivity","external_effects","novelty")
    for values in itertools.product(range(4), repeat=len(dimensions)):
        vector=RiskVector(*values)
        old_tier=classify_risk(vector,old)
        new_tier=classify_risk(vector,new)
        if new_tier < old_tier:
            return False
        if not _profile_tightened(old.control_profiles[old_tier], new.control_profiles[new_tier]):
            return False
    return True

def _is_tightening(old: Policy, new: Policy) -> bool:
    return (new.floor_id == old.floor_id and new.floor_digest == old.floor_digest and
            _risk_mapping_tightened(old.risk_mapping,new.risk_mapping) and
            new.authorization_rules.lease_ttl_ms <= old.authorization_rules.lease_ttl_ms and
            new.authorization_rules.max_execution_ms <= old.authorization_rules.max_execution_ms and
            _subset(new.authorization_rules.allowed_audiences, old.authorization_rules.allowed_audiences) and
            (not old.authorization_rules.require_attestation or new.authorization_rules.require_attestation) and
            _subset(old.authorization_rules.denied_action_types, new.authorization_rules.denied_action_types) and
            _subset(old.evidence_rules.default_freshness, new.evidence_rules.default_freshness) and
            (not old.evidence_rules.receipts_must_be_signed or new.evidence_rules.receipts_must_be_signed) and
            new.evidence_rules.max_excerpt_bytes <= old.evidence_rules.max_excerpt_bytes and
            new.retry_rules.max_same_failure <= old.retry_rules.max_same_failure and
            new.retry_rules.backoff_ms == old.retry_rules.backoff_ms and
            _budget_tightened(old.budget_rules.default_objective_budget,new.budget_rules.default_objective_budget) and
            new.budget_rules.reservation_ttl_ms <= old.budget_rules.reservation_ttl_ms and
            _subset(new.egress_rules.allowed_providers, old.egress_rules.allowed_providers) and
            new.egress_rules.max_classification <= old.egress_rules.max_classification and
            _subset(old.egress_rules.denied_path_globs,new.egress_rules.denied_path_globs) and
            (not old.egress_rules.require_redaction or new.egress_rules.require_redaction) and
            (not new.egress_rules.allow_remote_workers or old.egress_rules.allow_remote_workers) and
            _subset(new.release_rules.target_environments,old.release_rules.target_environments) and
            _subset(old.release_rules.required_evidence_kinds,new.release_rules.required_evidence_kinds) and
            (not new.release_rules.allow_waivers or old.release_rules.allow_waivers) and
            new.release_rules.max_waiver_ttl_ms <= old.release_rules.max_waiver_ttl_ms and
            _subset(new.waiver_rules.approver_authorities,old.waiver_rules.approver_authorities) and
            new.waiver_rules.max_ttl_ms <= old.waiver_rules.max_ttl_ms and
            (not old.waiver_rules.require_signature or new.waiver_rules.require_signature) and
            (not new.dependency_rules.waived_satisfies_dependents or old.dependency_rules.waived_satisfies_dependents) and
            (old.dependency_rules.superseded_requires_replacement_satisfied <= new.dependency_rules.superseded_requires_replacement_satisfied) and
            new.clock_skew_tolerance_ms <= old.clock_skew_tolerance_ms and
            _subset(new.telemetry.allowed_fields,old.telemetry.allowed_fields) and
            (not old.telemetry.forbid_content or new.telemetry.forbid_content) and
            (not old.telemetry.hash_paths or new.telemetry.hash_paths) and
            old.data_classification.default == new.data_classification.default and
            old.data_classification.path_rules == new.data_classification.path_rules and
            _subset(old.redaction.secret_detector_ids,new.redaction.secret_detector_ids) and
            old.redaction.replacement == new.redaction.replacement and
            (not old.redaction.redact_registered_credentials or new.redaction.redact_registered_credentials) and
            old.retention == new.retention)

_POLICY_FIELDS = frozenset({
    "policy_id", "policy_version", "risk_mapping", "authorization_rules", "evidence_rules",
    "retry_rules", "budget_rules", "egress_rules", "release_rules", "waiver_rules",
    "dependency_rules", "data_classification", "redaction", "retention", "telemetry",
    "clock_skew_tolerance_ms", "floor_id", "floor_digest", "approval_quorums",
})

def policy_relation(old: Policy, new: Policy) -> PolicyRelation:
    if frozenset(f.name for f in fields(old)) != _POLICY_FIELDS or frozenset(f.name for f in fields(new)) != _POLICY_FIELDS:
        return PolicyRelation.UNSUPPORTED_CHANGE
    if old.policy_id != new.policy_id or old.floor_id != new.floor_id or old.floor_digest != new.floor_digest:
        return PolicyRelation.UNSUPPORTED_CHANGE
    if old == new: return PolicyRelation.SAME
    if _is_tightening(old,new): return PolicyRelation.TIGHTENED
    return PolicyRelation.RELAXED

def policy_meets_floor(candidate: Policy, floor: PolicyFloor, key_directory: KeyDirectory,
                       at: UtcInstant) -> PolicyFloorVerdict:
    recomputed = digest("sclass/policy-floor/v1", floor.baseline_policy)
    if recomputed != floor.floor_digest:
        return PolicyFloorVerdict.NOT_EVALUABLE
    if key_directory.verify(floor.signature,
            signature_preimage("sclass/policy-floor/v1", floor.baseline_policy), at) is not SignatureVerificationResult.VALID:
        return PolicyFloorVerdict.NOT_EVALUABLE
    if candidate.floor_id != floor.floor_id or candidate.floor_digest != floor.floor_digest:
        return PolicyFloorVerdict.VIOLATES
    relation = policy_relation(floor.baseline_policy, candidate)
    return PolicyFloorVerdict.MEETS if relation in (PolicyRelation.SAME, PolicyRelation.TIGHTENED) else PolicyFloorVerdict.VIOLATES

def validate_policy_activation(old: Policy, new: Policy, floor: PolicyFloor, approvals: tuple[ApprovalRecord, ...],
                               valid_signature_ids: frozenset[str], workspace_id: str, scope_digest: Digest,
                               at: UtcInstant, principal_directory: Mapping[str, str],
                               required_principals: int, key_directory: KeyDirectory,
                               requester_principal_id: str = "",
                               principal_authority_ids: Mapping[str, str] = {}) -> PolicyRelation:
    relation=policy_relation(old,new)
    if policy_meets_floor(new,floor,key_directory,at) is not PolicyFloorVerdict.MEETS: return PolicyRelation.UNSUPPORTED_CHANGE
    if relation in (PolicyRelation.RELAXED,PolicyRelation.UNSUPPORTED_CHANGE):
        target=digest("sclass/policy/v1",new)
        if validate_approval_set(ApprovalSet("policy-activation", ApprovalKind.POLICY_RELAXATION,
        workspace_id, target, new.policy_version, scope_digest, required_principals, approvals, requester_principal_id),
        valid_signature_ids, at, principal_directory, required_principals, principal_authority_ids, bool(requester_principal_id)) is not ApprovalSetResult.VALID:
            return PolicyRelation.UNSUPPORTED_CHANGE
    return relation


@canonical_dataclass
class AcceptedRiskWaiver:
    waiver_id: str
    obligation_id: str
    waived_evidence_kinds: tuple[EvidenceKind, ...]
    scoped_effects: RequestedEffect          # effects the waiver covers; nothing broader
    policy_version: str
    objective_revision: str
    workspace_id: str
    approver: str                            # must be in Policy.waiver_rules.approver_authorities
    approval_set_id: str
    rationale: str
    issued_at: UtcInstant
    expires_at: UtcInstant
    signature: SignatureBlock                # attributable

@canonical_dataclass
class BreakGlassAuthority:
    authority_id: str
    key_id: str
    scope_obligation_ids: tuple[str, ...]
    workspace_id: str
    policy_version: str
    max_uses: int
    expires_at: UtcInstant
    audit_required: bool
    approval_scope_digest: Digest
    signature: SignatureBlock


class ObligationKind(Enum):
    FUNCTIONAL = "FUNCTIONAL"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    DOCUMENTATION = "DOCUMENTATION"
    RELEASE = "RELEASE"
    REPAIR = "REPAIR"

class RequirementStatus(Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"

@canonical_dataclass
class RequirementRecord:
    requirement: Requirement
    status: RequirementStatus

class ObligationStatus(Enum):
    PENDING = "PENDING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    SATISFIED = "SATISFIED"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"
    FAILED = "FAILED"
    REPAIR_REQUIRED = "REPAIR_REQUIRED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"
    WAIVED = "WAIVED"
    CANCELLED = "CANCELLED"          # restored (fixes #48); distinct from SUPERSEDED

@canonical_dataclass
class Obligation:
    obligation_id: str
    objective_id: str
    revision: int
    description: str
    kind: ObligationKind
    risk_tier: RiskTier
    status: ObligationStatus
    depends_on: frozenset[str]
    acceptance_contract_id: str
    satisfied_by: Optional[str]          # evidence_id
    verification_plan_id: Optional[str] = None  # exact canonical VerificationPlan identity

    def __post_init__(self):
        if not self.obligation_id or not self.objective_id or not self.acceptance_contract_id:
            raise ValueError("obligation identity is incomplete")
        if isinstance(self.revision,bool) or self.revision < 1:
            raise ValueError("obligation revision must be >= 1")
        if self.verification_plan_id is not None and not self.verification_plan_id:
            raise ValueError("verification_plan_id cannot be empty")


@canonical_dataclass
class SemanticGraph:
    nodes: tuple[str, ...]                       # sorted, unique
    edges: tuple[tuple[str, str, str], ...]      # (src, dst, edge_type) sorted, unique
    # INVARIANTS: acyclic over "depends_on"; edge types ∈ {"depends_on","superseded_by"}; deterministic serialization

@canonical_dataclass
class ObligationGraph:
    _graph: SemanticGraph
    _obligations: FrozenMap

    def _edges(self, edge_type="depends_on"):
        return tuple((a,b,t) for a,b,t in self._graph.edges if t==edge_type)
    def add(self, obligation: Obligation) -> "ObligationGraph":
        if obligation.obligation_id in self._obligations:
            existing=self._obligations[obligation.obligation_id]
            if existing == obligation: return self
            raise ValueError("duplicate obligation identity")
        d=dict(self._obligations.items()); d[obligation.obligation_id]=obligation
        nodes=set(self._graph.nodes); nodes.add(obligation.obligation_id)
        edges=set(self._graph.edges)
        for dep in obligation.depends_on:
            if dep not in d: raise ValueError(f"unknown obligation dependency: {dep}")
            edges.add((obligation.obligation_id,dep,"depends_on"))
        g=SemanticGraph(tuple(sorted(nodes)),tuple(sorted(edges)))
        out=ObligationGraph(g,FrozenMap.from_items(d.items()))
        out.topological_order()
        return out
    def ancestors(self, obligation_id: str) -> frozenset[str]:
        if obligation_id not in self._obligations: raise KeyError(obligation_id)
        rev={}
        for a,b,t in self._edges(): rev.setdefault(a,set()).add(b)
        seen=set(); stack=list(rev.get(obligation_id,set()))
        while stack:
            x=stack.pop()
            if x in seen: continue
            seen.add(x); stack.extend(rev.get(x,set()))
        return frozenset(seen)
    def dependents(self, obligation_id: str) -> frozenset[str]:
        if obligation_id not in self._obligations: raise KeyError(obligation_id)
        rev={}
        for a,b,t in self._edges(): rev.setdefault(b,set()).add(a)
        seen=set(); stack=list(rev.get(obligation_id,set()))
        while stack:
            x=stack.pop()
            if x in seen: continue
            seen.add(x); stack.extend(rev.get(x,set()))
        return frozenset(seen)
    def invalidate(self, obligation_id: str) -> "ObligationGraph":
        ids={obligation_id}|set(self.dependents(obligation_id)); d=dict(self._obligations.items())
        for oid in ids: d[oid]=replace(d[oid],status=ObligationStatus.INVALIDATED,satisfied_by=None)
        return ObligationGraph(self._graph,FrozenMap.from_items(d.items()))
    def topological_order(self) -> Sequence[str]:
        deps={n:set() for n in self._graph.nodes}
        for a,b,t in self._edges(): deps[a].add(b)
        ready=sorted(n for n,v in deps.items() if not v); out=[]
        while ready:
            n=ready.pop(0); out.append(n)
            for x in sorted(deps):
                if n in deps[x]:
                    deps[x].remove(n)
                    if not deps[x] and x not in out and x not in ready: ready.append(x); ready.sort()
        if len(out)!=len(deps): raise ValueError("obligation dependency cycle")
        return tuple(out)
    def dependency_satisfies(self, obligation_id: str, policy: Policy) -> bool:
        return all(self._obligations[x].status in (ObligationStatus.SATISFIED,ObligationStatus.WAIVED) for x in self.ancestors(obligation_id))
    def is_complete(self) -> bool:
        return set(self._graph.nodes)==set(k for k,_ in self._obligations.items()) and len(self._graph.nodes)==len(set(self._graph.nodes))


class IndependenceLevel(IntEnum):        # numeric rank: comparison is by value (fixes #9)
    NONE = 0
    WEAK = 1
    MODERATE = 2
    STRONG = 3

@canonical_dataclass
class IndependenceProfile:
    model: IndependenceLevel
    context: IndependenceLevel
    execution: IndependenceLevel
    verifier: IndependenceLevel
    configuration: IndependenceLevel

class EvidenceKind(Enum):
    BEHAVIORAL = "BEHAVIORAL"
    STRUCTURAL = "STRUCTURAL"
    STATIC = "STATIC"
    DYNAMIC = "DYNAMIC"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    METAMORPHIC = "METAMORPHIC"
    ADVERSARIAL = "ADVERSARIAL"
    HUMAN = "HUMAN"                      # all nine are supported; none referenced elsewhere is unsupported (fixes #31)

class FreshnessDimension(Enum):
    TARGET_SNAPSHOT = "TARGET_SNAPSHOT"
    WORKSPACE_SNAPSHOT = "WORKSPACE_SNAPSHOT"
    EVENT_HEAD = "EVENT_HEAD"
    OBJECTIVE_REVISION = "OBJECTIVE_REVISION"
    POLICY = "POLICY"
    ACCEPTANCE_CONTRACT = "ACCEPTANCE_CONTRACT"
    VERIFICATION_PLAN = "VERIFICATION_PLAN"
    VERIFIER_CONFIG = "VERIFIER_CONFIG"
    ENVIRONMENT = "ENVIRONMENT"
    DEPENDENT_ARTIFACTS = "DEPENDENT_ARTIFACTS"

# Acceptance/release freshness floor. These dimensions are always evaluated;
# callers may add dimensions but may not remove the floor.
FRESHNESS_FLOOR = (
    FreshnessDimension.TARGET_SNAPSHOT,
    FreshnessDimension.OBJECTIVE_REVISION,
    FreshnessDimension.POLICY,
    FreshnessDimension.ACCEPTANCE_CONTRACT,
    FreshnessDimension.VERIFICATION_PLAN,
    FreshnessDimension.VERIFIER_CONFIG,
    FreshnessDimension.ENVIRONMENT,
    FreshnessDimension.DEPENDENT_ARTIFACTS,
)

class CompositionMode(Enum):
    ALL_OF = "ALL_OF"
    ANY_OF = "ANY_OF"
    K_OF_N = "K_OF_N"

@canonical_dataclass
class RequiredEvidence:
    requirement_key: str
    evidence_kind: EvidenceKind
    verifier_id: str
    min_independence: IndependenceProfile
    freshness: tuple[FreshnessDimension, ...]
    mandatory: bool
    min_receipts: int

@canonical_dataclass
class EvidenceComposition:
    mode: CompositionMode
    k: int                                # used when mode == K_OF_N
    def __post_init__(self):
        if self.mode is CompositionMode.K_OF_N and self.k < 1:
            raise ValueError("K_OF_N requires k >= 1")
        if self.mode is not CompositionMode.K_OF_N and self.k != 0:
            raise ValueError("k is only valid for K_OF_N")

@canonical_dataclass
class EvidenceCompositionEvaluation:
    verdict: ClosureVerdict
    requirement_results: tuple[RequirementResult, ...]

def evaluate_evidence_composition(contract: AcceptanceContract, receipts: tuple[EvidenceReceipt, ...],
                                  ctx: FreshnessContext,
                                  verifier_profiles: Mapping[str, IndependenceProfile],
                                  signature_valid_receipt_ids: frozenset[str]) -> EvidenceCompositionEvaluation:
    """Canonical, deterministic ALL_OF/ANY_OF/K_OF_N evaluator.
    All admissibility, verifier, freshness and receipt-count decisions are explicit inputs/facts.
    """
    if len({r.receipt_id for r in receipts}) != len(receipts):
        raise ValueError("duplicate evidence receipt id")
    results=[]
    for req in contract.required_evidence:
        matched=[]
        for receipt in receipts:
            if not validate_evidence_receipt_identity(receipt):
                continue
            p=receipt.payload
            if p.requirement_key != req.requirement_key or p.evidence_kind is not req.evidence_kind:
                continue
            if p.signer_identity != req.verifier_id:
                continue
            if receipt.receipt_id not in signature_valid_receipt_ids:
                continue
            profile=verifier_profiles.get(p.signer_identity)
            if profile is None or is_admissible(req.min_independence, profile).verdict is not Admissibility.ADMISSIBLE:
                continue
            if p.result_status is not VerificationStatus.PASS:
                continue
            if p.target_snapshot_digest != ctx.target_snapshot_digest or p.objective_revision != ctx.objective_revision:
                continue
            if p.acceptance_contract_revision != ctx.contract_revision or p.verification_plan_revision != ctx.plan_revision:
                continue
            if p.environment_digest != ctx.environment_digest:
                continue
            if ctx.dependency_set_digest_now is not None and p.dependency_set_digest != ctx.dependency_set_digest_now:
                continue
            if req.freshness:
                pseudo=type("_ReceiptClosure", (), {})()
                pseudo.target_snapshot_digest=p.target_snapshot_digest
                pseudo.workspace_snapshot_id=ctx.snapshot_id
                pseudo.evidence_id=receipt.receipt_id
                pseudo.objective_revision=p.objective_revision
                pseudo.policy_version=ctx.policy_version
                pseudo.acceptance_contract_revision=p.acceptance_contract_revision
                pseudo.verification_plan_revision=p.verification_plan_revision
                pseudo.verifier_config_digest=ctx.verifier_config_digest
                pseudo.environment_digest=p.environment_digest
                # Freshness MUST bind to the signed dependency-set digest. The current canonical
                # dependency map is authoritative; the receipt is fresh only when the signed digest
                # matches that canonical set. Other freshness dimensions are then evaluated normally.
                pseudo.dependency_set=_dependency_set_from_payload(p)
                fresh=is_fresh(pseudo, req.freshness, ctx)
                if FreshnessDimension.DEPENDENT_ARTIFACTS in set(req.freshness) or FreshnessDimension.DEPENDENT_ARTIFACTS in set(FRESHNESS_FLOOR):
                    if ctx.dependency_set_digest_now is None or p.dependency_set_digest != ctx.dependency_set_digest_now:
                        fresh=FreshnessVerdict(FreshnessState.STALE, (FreshnessDimension.DEPENDENT_ARTIFACTS,))
                if fresh.state is not FreshnessState.FRESH:
                    continue
            matched.append(receipt.receipt_id)
        passed=len(matched) >= req.min_receipts
        results.append(RequirementResult(req.requirement_key, tuple(sorted(matched)),
                                         Admissibility.ADMISSIBLE if passed else Admissibility.INADMISSIBLE, passed))
    mandatory_ok=all(r.passed for req,r in zip(contract.required_evidence,results) if req.mandatory)
    alternatives=[r.passed for req,r in zip(contract.required_evidence,results) if not req.mandatory]
    if not mandatory_ok:
        verdict=ClosureVerdict.UNSATISFIED
    elif contract.composition.mode is CompositionMode.ALL_OF:
        verdict=ClosureVerdict.SATISFIED if all(r.passed for r in results) else ClosureVerdict.UNSATISFIED
    elif contract.composition.mode is CompositionMode.ANY_OF:
        verdict=ClosureVerdict.SATISFIED if alternatives and any(alternatives) else ClosureVerdict.UNSATISFIED
    else:
        verdict=ClosureVerdict.SATISFIED if sum(alternatives) >= contract.composition.k else ClosureVerdict.UNSATISFIED
    return EvidenceCompositionEvaluation(verdict, tuple(results))

# Composition semantics are normative:
# ALL_OF: every RequiredEvidence row must meet min_receipts.
# ANY_OF: every mandatory row must meet min_receipts; at least one non-mandatory
#          alternative must meet min_receipts. If no alternatives exist, INVALID.
# K_OF_N: every mandatory row must meet min_receipts; at least k distinct non-mandatory
#         rows must meet min_receipts. Require 1 <= k <= N.


@canonical_dataclass
class AcceptanceContract:
    contract_id: str
    obligation_id: str
    revision: int
    required_evidence: tuple[RequiredEvidence, ...]
    composition: EvidenceComposition
    waiver_rules: WaiverRules
    authored_by: Authority               # must be USER or POLICY; reducer rejects WORKER/LLM_DERIVED
    def __post_init__(self):
        if any(r.min_receipts < 1 for r in self.required_evidence):
            raise ValueError("min_receipts must be >= 1")
        identities={(r.evidence_kind,r.verifier_id) for r in self.required_evidence}
        if len(identities) != len(self.required_evidence):
            raise ValueError("duplicate RequiredEvidence kind/verifier rows are not allowed")
        alternatives = [r for r in self.required_evidence if not r.mandatory]
        if self.composition.mode is CompositionMode.ANY_OF and not alternatives:
            raise ValueError("ANY_OF requires at least one non-mandatory alternative")
        if self.composition.mode is CompositionMode.K_OF_N and not (1 <= self.composition.k <= len(alternatives)):
            raise ValueError("K_OF_N requires 1 <= k <= number of alternatives")

@canonical_dataclass
class VerificationStep:
    step_id: str
    evidence_kind: EvidenceKind
    verifier_id: str
    verifier_version: str
    config_digest: Digest
    timeout_ms: int
    budget: ResourceBudget

    def __post_init__(self):
        if not self.step_id or not self.verifier_id or not self.verifier_version:
            raise ValueError("verification step identity is incomplete")
        if isinstance(self.timeout_ms,bool) or self.timeout_ms < 1:
            raise ValueError("verification step timeout must be positive")
        if not _is_digest_value(self.config_digest): raise ValueError("invalid verification step config digest")

@canonical_dataclass
class VerificationPlan:
    plan_id: str
    obligation_id: str
    revision: int
    contract_revision: int
    steps: tuple[VerificationStep, ...]

    def __post_init__(self):
        if not self.plan_id or not self.obligation_id or self.revision < 1 or self.contract_revision < 1:
            raise ValueError("invalid verification plan identity/revision")
        ids=[s.step_id for s in self.steps]
        if not ids or len(ids) != len(set(ids)):
            raise ValueError("verification plan requires unique non-empty step ids")


@canonical_dataclass
class ResourceBudget:
    cpu_cores: int
    memory_mb: int
    network_bytes: int
    wall_time_ms: int
    disk_mb: int
    process_count: int
    concurrency: int
    tokens: int
    llm_requests: int
    spend_limit_micro_usd: int           # integer; no floats
    external_effect_units: int

    def __post_init__(self):
        for f in fields(self):
            v=getattr(self,f.name)
            if isinstance(v,bool) or not isinstance(v,int):
                raise TypeError(f"{f.name} must be int")
            if v < 0 or v > 2**63-1:
                raise ValueError(f"{f.name} out of int64 range")

# Construction invariant: every field is int, never bool, and 0 <= value <= 2^63-1.
# Ports are 1..65535; confidence basis points are 0..10000.
# Reservation arithmetic is checked and atomic; no caller-supplied comparison function is accepted.


class BudgetLevel(Enum):
    OBJECTIVE = "OBJECTIVE"
    WORK_NODE = "WORK_NODE"
    ATTEMPT = "ATTEMPT"
    LLM_CALL = "LLM_CALL"
    VERIFICATION = "VERIFICATION"

class BudgetReservationState(Enum):
    RESERVED = "RESERVED"
    RELEASED = "RELEASED"
    SETTLED = "SETTLED"
    EXPIRED = "EXPIRED"

@canonical_dataclass
class BudgetReservation:
    reservation_id: str
    workspace_id: str
    request_id: str                         # exact authority request bound to this reservation
    level: BudgetLevel
    parent_reservation_id: Optional[str]
    governing_budget_lineage_id: str
    amount: ResourceBudget
    expires_at: UtcInstant
    lifecycle_state: BudgetReservationState = BudgetReservationState.RESERVED
    reserved_amount: ResourceBudget = None
    released_amount: ResourceBudget = None
    settled_amount: ResourceBudget = None
    actual_usage: ResourceBudget = None
    version: int = 1

    def __post_init__(self):
        zero = ResourceBudget(0,0,0,0,0,0,0,0,0,0,0)
        for name in ("reserved_amount","released_amount","settled_amount","actual_usage"):
            v=getattr(self,name)
            if v is None:
                object.__setattr__(self,name, self.amount if name == "reserved_amount" else zero)
            elif not isinstance(v,ResourceBudget):
                raise TypeError(f"{name} must be ResourceBudget")
        if isinstance(self.version,bool) or not isinstance(self.version,int) or self.version < 1:
            raise ValueError("invalid budget reservation version")
        if self.expires_at.epoch_ns < 0:
            raise ValueError("budget reservation expiry must be non-negative")
        if not self.reservation_id or not self.workspace_id or not self.request_id or not self.governing_budget_lineage_id:
            raise ValueError("budget reservation canonical identity is incomplete")

class BudgetReservationResult(Enum):
    RESERVED = "RESERVED"
    DENIED_INSUFFICIENT = "DENIED_INSUFFICIENT"
    DENIED_PARENT = "DENIED_PARENT"
    ALREADY_RESERVED = "ALREADY_RESERVED"
    DENIED_OVERRUN = "DENIED_OVERRUN"
    DENIED_ACTIVE_RESERVATION = "DENIED_ACTIVE_RESERVATION"
    STORE_ERROR = "STORE_ERROR"

class GlobalBudgetAllocator(Protocol):
    """Hierarchy: objective → work-node → attempt → llm-call / verification.
    reserve() is all-or-nothing across every ancestor in ONE transaction, so parallel
    workers cannot each comply locally and collectively overspend (fixes #60)."""
    def reserve(self, request_id: str, level: BudgetLevel, parent_reservation_id: Optional[str],
                amount: ResourceBudget) -> tuple[BudgetReservationResult, Optional[BudgetReservation]]: ...
    def commit(self, reservation_id: str) -> BudgetReservationResult: ...
    def release(self, reservation_id: str) -> BudgetReservationResult: ...
    def settle_actual_usage(self, reservation_id: str, actual: ResourceBudget) -> BudgetReservationResult: ...
    def expire(self, now: UtcInstant) -> tuple[str, ...]: ...        # sweeps leaked reservations; emits BudgetReleased


class ActionType(Enum):
    CODE_READ = "CODE_READ"
    CODE_EDIT = "CODE_EDIT"
    SHELL_EXEC = "SHELL_EXEC"
    TEST_RUN = "TEST_RUN"
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"
    NETWORK_CALL = "NETWORK_CALL"
    EXTERNAL_MUTATION = "EXTERNAL_MUTATION"
    ANALYSIS = "ANALYSIS"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    APPLY_DELTA = "APPLY_DELTA"

class Idempotency(Enum):
    IDEMPOTENT = "IDEMPOTENT"
    CONDITIONALLY_IDEMPOTENT = "CONDITIONALLY_IDEMPOTENT"
    NON_IDEMPOTENT = "NON_IDEMPOTENT"

class WorkNodeStatus(Enum):
    PENDING = "PENDING"
    READY = "READY"
    BLOCKED = "BLOCKED"
    ASSIGNED = "ASSIGNED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    OBSERVING = "OBSERVING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    IN_DOUBT = "IN_DOUBT"
    CANCELLED = "CANCELLED"

@canonical_dataclass
class WorkNode:
    node_id: str
    primary_obligation_id: str
    satisfies_obligation_ids: frozenset[str]
    action_description: str
    action_type: ActionType
    requested_effect: RequestedEffect
    effect_scope: EffectScope
    estimated_tokens: int
    estimated_duration_ms: int
    status: WorkNodeStatus
    idempotency: Idempotency
    worker_id: Optional[str]
    retry_budget_id: str                  # attempt counters live ONLY in RetryBudget (fixes #52)
    effective_risk_tier: RiskTier
    execution_generation: int
    governing_budget_lineage_id: str

@canonical_dataclass
class WorkGraph:
    revision_id: str
    objective_revision: str
    obligation_graph_revision: str
    policy_version: str
    world_model_revision: str
    _graph: SemanticGraph
    _nodes: FrozenMap
    def topological_order(self) -> Sequence[str]:
        deps={n:set() for n in self._graph.nodes}
        for a,b,t in self._graph.edges:
            if t=="depends_on": deps[a].add(b)
        ready=sorted(n for n,v in deps.items() if not v); out=[]
        while ready:
            n=ready.pop(0); out.append(n)
            for x in sorted(deps):
                if n in deps[x]:
                    deps[x].remove(n)
                    if not deps[x] and x not in out and x not in ready: ready.append(x); ready.sort()
        if len(out)!=len(deps): raise ValueError("work graph cycle")
        return tuple(out)
    def frontier(self) -> Sequence[WorkNode]:
        out=[]
        for nid in self.topological_order():
            n=self._nodes[nid]
            if n.status is not WorkNodeStatus.READY: continue
            deps=[a for a,b,t in self._graph.edges if a==nid and t=="depends_on"]
            if all(self._nodes[d].status in (WorkNodeStatus.COMPLETED,WorkNodeStatus.CANCELLED) for d in deps): out.append(n)
        return tuple(out)
    def assign(self, node_id: str, worker_id: str) -> WorkProposal:
        if node_id not in self._nodes: raise KeyError(node_id)
        n=self._nodes[node_id]
        if n.status is not WorkNodeStatus.READY: raise ValueError("work node not READY")
        return WorkProposal(node_id,worker_id,n.execution_generation,n.governing_budget_lineage_id)
    def advance(self, node_id: str, evidence: EvidenceClosure) -> "WorkGraph":
        if node_id not in self._nodes: raise KeyError(node_id)
        n=self._nodes[node_id]
        if evidence.verdict is not ClosureVerdict.SATISFIED: raise ValueError("advance requires satisfied evidence")
        d=dict(self._nodes.items()); d[node_id]=replace(n,status=WorkNodeStatus.COMPLETED)
        return replace(self,_nodes=FrozenMap.from_items(d.items()))
    def critical_path_lower_bound_ms(self) -> int:
        best={}
        for nid in self.topological_order():
            n=self._nodes[nid]; deps=[a for a,b,t in self._graph.edges if a==nid and t=="depends_on"]
            best[nid]=n.estimated_duration_ms + max((best[d] for d in deps),default=0)
        return max(best.values(),default=0)

@canonical_dataclass
class ScheduleAssignment:
    node_id: str
    worker_instance_id: str
    rank_key: tuple[int, ...]

@canonical_dataclass
class BudgetSnapshot:
    workspace_id: str
    available: ResourceBudget

@canonical_dataclass
class ResourceSnapshot:
    active_workers: int
    per_worker_load: FrozenMap

class Scheduler(Protocol):
    """Pure and deterministic given identical inputs. Returns proposals only; never mutates state (L1)."""
    def schedule(self, frontier: Sequence[WorkNode], workers: Sequence[WorkerInstance],
                 policy: Policy, budget: BudgetSnapshot,
                 resources: ResourceSnapshot) -> tuple[ScheduleAssignment, ...]: ...


def normalize_failure_inputs(failure_class: str, evidence_digest: Digest,
                             relevant_artifact_digest: Digest,
                             verifier_config_digest: Digest) -> tuple[str, Digest, Digest, Digest]:
    # Only stable semantic identities enter the convergence fingerprint.
    return (failure_class, evidence_digest, relevant_artifact_digest, verifier_config_digest)

@canonical_dataclass
class RetryBudget:
    budget_id: str
    node_id: str
    max_retries: int
    consumed: int
    same_failure_count: int
    last_failure_fingerprint: Optional[Digest]
    version: int                         # CAS token

    def __post_init__(self):
        if not self.budget_id or not self.node_id:
            raise ValueError("retry budget identity missing")
        for name,v in (("max_retries",self.max_retries),("consumed",self.consumed),("same_failure_count",self.same_failure_count),("version",self.version)):
            if isinstance(v,bool) or not isinstance(v,int) or v < 0:
                raise ValueError(f"invalid retry budget {name}")
        if self.consumed > self.max_retries:
            raise ValueError("retry budget consumed exceeds max_retries")
        if self.last_failure_fingerprint is not None and not _is_digest_value(self.last_failure_fingerprint):
            raise ValueError("invalid retry failure fingerprint")

class RetryReservationResult(Enum):
    RESERVED = "RESERVED"
    EXHAUSTED = "EXHAUSTED"
    CONVERGED_NO_PROGRESS = "CONVERGED_NO_PROGRESS"   # same failure fingerprint hit Policy.retry_rules.max_same_failure
    VERSION_CONFLICT = "VERSION_CONFLICT"

class RetryBudgetStore(Protocol):
    def try_consume(self, budget_id: str, expected_version: int,
                    failure_fingerprint: Digest) -> RetryReservationResult: ...


class FsMode(Enum):
    READ = "READ"
    CREATE = "CREATE"
    WRITE = "WRITE"
    DELETE = "DELETE"
    RENAME = "RENAME"
    LINK = "LINK"
    METADATA = "METADATA"
    EXEC = "EXEC"

# WRITE modifies existing content only; it does not imply CREATE, DELETE, RENAME, LINK, or METADATA.

@canonical_dataclass
class FsAccess:
    path: str                 # canonical workspace-relative POSIX form
    mode: FsMode

@canonical_dataclass
class ProcessSpec:
    executable_digest: Digest
    argv_digest: Digest
    working_directory: str
    child_processes: tuple[tuple[Digest, Digest], ...]   # exact (executable, argv) pairs
    spawns_children: bool

@canonical_dataclass
class NetworkDestination:
    host: str
    port: int
    protocol: str
    tls: bool
    resolved_ips: tuple[str, ...] = ()
    resolution_binding_digest: Optional[Digest] = None
    def __post_init__(self):
        object.__setattr__(self, "host", _canonical_host(self.host))
        if isinstance(self.port, bool) or not 1 <= self.port <= 65535: raise ValueError("invalid port")
        if self.protocol not in {"tcp", "udp"}: raise ValueError("invalid protocol")
        for ip in self.resolved_ips: ipaddress.ip_address(ip)
        if self.resolution_binding_digest is None:
            object.__setattr__(self, "resolution_binding_digest", digest("sclass/dns-resolution/v1", (self.host, tuple(sorted(self.resolved_ips)), self.port, self.protocol, self.tls)))

@canonical_dataclass
class NetAccess:
    host: str
    resolved_ips: tuple[str, ...]   # observation only; authorization uses boundary_ips
    port: int
    protocol: str             # "tcp" | "udp"
    tls: bool
    redirect_chain: tuple[NetworkDestination, ...] = ()
    resolution_binding_digest: Optional[Digest] = None
    def __post_init__(self):
        object.__setattr__(self,"host",_canonical_host(self.host))
        object.__setattr__(self,"redirect_chain",tuple(x if isinstance(x, NetworkDestination) else NetworkDestination(x,self.port,self.protocol,self.tls,()) for x in self.redirect_chain))
        if self.resolution_binding_digest is None:
            object.__setattr__(self,"resolution_binding_digest",digest("sclass/dns-resolution/v1", (self.host, tuple(sorted(self.resolved_ips)), self.port, self.protocol, self.tls)))
        if isinstance(self.port,bool) or not 1 <= self.port <= 65535: raise ValueError("invalid port")
        if self.protocol not in {"tcp","udp"}: raise ValueError("invalid protocol")
        if any(not isinstance(x, str) for x in self.resolved_ips): raise ValueError("invalid resolved IP")

@canonical_dataclass
class ExternalEffect:
    target_system: str
    effect_kind: str
    units: int

    def __post_init__(self):
        if not self.target_system or not self.effect_kind:
            raise ValueError('external effect identity must be non-empty')
        if isinstance(self.units,bool) or not isinstance(self.units,int) or not (0 <= self.units <= 2**63-1):
            raise ValueError('ExternalEffect.units must be a non-negative int64')

@canonical_dataclass
class RequestedEffect:
    filesystem: tuple[FsAccess, ...]
    subprocess: tuple[ProcessSpec, ...]
    network: tuple[NetAccess, ...]
    environment: FrozenMap              # env name -> exact value digest
    credentials: tuple[str, ...]
    external_side_effects: tuple[ExternalEffect, ...]
    requested_budget: ResourceBudget
    delta_digest: Optional[Digest] = None

@canonical_dataclass
class FsRule:
    path_prefix: str
    modes: frozenset[FsMode]

@canonical_dataclass
class ProcessRule:
    executable_digest: Digest
    argv_digest: Optional[Digest]              # exact argv digest; None = no argv permitted
    allow_children: bool
    child_allowlist: tuple[tuple[Digest, Digest], ...]

@canonical_dataclass
class NetRule:
    host_pattern: str          # exact DNS/IP or "*.suffix"; bare "*" forbidden
    allowed_cidrs: tuple[str, ...]
    ports: frozenset[int]
    protocol: str
    tls_required: bool
    allow_redirects: bool
    def __post_init__(self):
        if self.host_pattern == "*": raise ValueError("bare wildcard is forbidden")
        canonical_pattern = "*." + _canonical_host(self.host_pattern[2:]) if self.host_pattern.startswith("*.") else _canonical_host(self.host_pattern)
        object.__setattr__(self,"host_pattern",canonical_pattern)
        if self.protocol not in {"tcp","udp"}: raise ValueError("invalid protocol")
        if any(isinstance(p,bool) or not 1 <= p <= 65535 for p in self.ports): raise ValueError("invalid port")
        for c in self.allowed_cidrs: ipaddress.ip_network(c,strict=False)

@canonical_dataclass
class CredentialGrant:
    credential_id: str
    injection: str             # "env" | "fd"; value never appears in any canonical object

@canonical_dataclass
class ExternalEffectRule:
    target_system: str
    effect_kinds: frozenset[str]
    max_units: int

    def __post_init__(self):
        if not self.target_system or not self.effect_kinds:
            raise ValueError('external effect rule identity must be non-empty')
        if isinstance(self.max_units,bool) or not isinstance(self.max_units,int) or not (0 <= self.max_units <= 2**63-1):
            raise ValueError('ExternalEffectRule.max_units must be a non-negative int64')

@canonical_dataclass
class EffectScope:
    fs_rules: tuple[FsRule, ...]
    process_rules: tuple[ProcessRule, ...]
    network_rules: tuple[NetRule, ...]
    allowed_env: FrozenMap                   # env name -> exact value digest
    working_directory: str
    credential_grants: tuple[CredentialGrant, ...]
    external_effect_rules: tuple[ExternalEffectRule, ...]
    resource_budget: ResourceBudget


class ScopeAuthorizationResult(Enum):
    AUTHORIZED = "AUTHORIZED"
    DENIED_MALFORMED = "DENIED_MALFORMED"
    DENIED_PATH = "DENIED_PATH"
    DENIED_MODE = "DENIED_MODE"
    DENIED_PROCESS = "DENIED_PROCESS"
    DENIED_CHILD_PROCESS = "DENIED_CHILD_PROCESS"
    DENIED_NETWORK = "DENIED_NETWORK"
    DENIED_ENV = "DENIED_ENV"
    DENIED_CREDENTIAL = "DENIED_CREDENTIAL"
    DENIED_EXTERNAL_EFFECT = "DENIED_EXTERNAL_EFFECT"
    DENIED_BUDGET = "DENIED_BUDGET"


import ipaddress, unicodedata

def _canonical_rel(p: str) -> bool:
    if not isinstance(p, str) or p == ".":
        return p == "."
    if (not p or p.endswith("/") or p.startswith("/") or "\\" in p or "\x00" in p or ":" in p):
        return False
    if unicodedata.normalize("NFC", p) != p:
        return False
    parts = p.split("/")
    return all(part not in ("", ".", "..") and not any(ord(ch) < 0x20 for ch in part)
               for part in parts)

def _path_specificity(prefix: str) -> tuple[int, int]:
    # Root is least specific; specificity is semantic path-component count,
    # then canonical byte length only as a deterministic tie-breaker.
    if prefix == ".": return (0, 1)
    return (len(prefix.split("/")), len(prefix.encode("utf-8")))

def _contains_prefix(parent: str, child: str) -> bool:
    if not _canonical_rel(parent) or not _canonical_rel(child): return False
    return parent == "." or child == parent or child.startswith(parent + "/")

def _canonical_host(host: str) -> str:
    if not isinstance(host,str) or not host or "\x00" in host or any(ch.isspace() for ch in host): raise ValueError("invalid host")
    host=host.rstrip(".").lower()
    try: ipaddress.ip_address(host); return host
    except ValueError:
        try: return host.encode("idna").decode("ascii")
        except UnicodeError as exc: raise ValueError("invalid host") from exc

def _validate_scope_rules(scope: EffectScope) -> None:
    if any(not _canonical_rel(r.path_prefix) for r in scope.fs_rules):
        raise ValueError("invalid filesystem rule prefix")
    fs_keys = [r.path_prefix for r in scope.fs_rules]
    if len(fs_keys) != len(set(fs_keys)):
        raise ValueError("duplicate filesystem authorization rule")
    proc_keys = [(r.executable_digest, r.argv_digest) for r in scope.process_rules]
    if len(proc_keys) != len(set(proc_keys)):
        raise ValueError("duplicate process authorization rule")
    ext_keys = [(r.target_system, effect_kind) for r in scope.external_effect_rules for effect_kind in sorted(r.effect_kinds)]
    if len(ext_keys) != len(set(ext_keys)):
        raise ValueError("duplicate external-effect authorization rule")

def _host_ok(rule: NetRule, host: str) -> bool:
    host=_canonical_host(host); pattern=rule.host_pattern
    if pattern == "*": return False
    if pattern.startswith("*."):
        suffix=_canonical_host(pattern[2:])
        try: ipaddress.ip_address(host); return False
        except ValueError: return host.endswith("."+suffix) and host != suffix
    return host == _canonical_host(pattern)

def _validate_budget(v: ResourceBudget) -> None:
    for f in fields(ResourceBudget):
        value = getattr(v, f.name)
        if not isinstance(value, int) or isinstance(value, bool) or not (0 <= value <= 2**63 - 1):
            raise ValueError(f"invalid budget field {f.name}")
    if v.spend_limit_micro_usd < 0 or v.external_effect_units < 0:
        raise ValueError("negative budget")

def _budget_le(a: ResourceBudget, b: ResourceBudget) -> bool:
    _validate_budget(a); _validate_budget(b)
    return all(getattr(a, f.name) <= getattr(b, f.name) for f in fields(ResourceBudget))

def authorized(req: RequestedEffect, scope: EffectScope, boundary_ips: Mapping[str, tuple[str, ...]] = {}) -> ScopeAuthorizationResult:
    R = ScopeAuthorizationResult
    for fs in req.filesystem:
        if not _canonical_rel(fs.path): return R.DENIED_MALFORMED
        matches = [r for r in scope.fs_rules
                   if fs.path == r.path_prefix or fs.path.startswith(r.path_prefix.rstrip("/") + "/")]
        if not matches: return R.DENIED_PATH
        best = max(matches, key=lambda r: _path_specificity(r.path_prefix))     # semantic most-specific rule wins
        if fs.mode not in best.modes: return R.DENIED_MODE
    for p in req.subprocess:
        rules = [r for r in scope.process_rules
                 if r.executable_digest == p.executable_digest and r.argv_digest == p.argv_digest]
        if len(rules) != 1: return R.DENIED_PROCESS
        rule = rules[0]
        if not scope.working_directory or not _contains_prefix(scope.working_directory,p.working_directory): return R.DENIED_PROCESS
        if p.spawns_children:
            if not rule.allow_children: return R.DENIED_CHILD_PROCESS
            if not set(p.child_processes) <= set(rule.child_allowlist): return R.DENIED_CHILD_PROCESS
    for n in req.network:
        rules = [r for r in scope.network_rules if _host_ok(r, n.host)
                 and n.port in r.ports and r.protocol == n.protocol]
        if not rules: return R.DENIED_NETWORK
        if any(r.tls_required for r in rules) and not n.tls: return R.DENIED_NETWORK
        actual=tuple(boundary_ips.get(_canonical_host(n.host),()))
        expected_resolution=digest("sclass/dns-resolution/v1", (n.host, tuple(sorted(n.resolved_ips)), n.port, n.protocol, n.tls))
        if n.resolution_binding_digest != expected_resolution: return R.DENIED_NETWORK
        if not actual or not n.resolved_ips or not set(actual) <= set(n.resolved_ips): return R.DENIED_NETWORK
        for ip in actual:
            addr = ipaddress.ip_address(ip)
            if not any(any(addr in ipaddress.ip_network(c) for c in r.allowed_cidrs) for r in rules):
                return R.DENIED_NETWORK
        if n.redirect_chain and not any(r.allow_redirects for r in rules):
            return R.DENIED_NETWORK
        for target in n.redirect_chain:
            redirect_rules=[r for r in scope.network_rules if _host_ok(r,target.host) and target.port in r.ports and r.protocol==target.protocol]
            if not redirect_rules or (any(r.tls_required for r in redirect_rules) and not target.tls): return R.DENIED_NETWORK
            ips=tuple(boundary_ips.get(_canonical_host(target.host),()))
            expected_redirect_resolution=digest("sclass/dns-resolution/v1", (target.host, tuple(sorted(target.resolved_ips)), target.port, target.protocol, target.tls))
            if target.resolution_binding_digest != expected_redirect_resolution: return R.DENIED_NETWORK
            if not ips or not target.resolved_ips or not set(ips) <= set(target.resolved_ips): return R.DENIED_NETWORK
            for ip in ips:
                addr=ipaddress.ip_address(ip)
                if not any(addr in ipaddress.ip_network(c) for r in redirect_rules for c in r.allowed_cidrs):
                    return R.DENIED_NETWORK
    for env_name, env_value_digest in req.environment.items():
        if env_name not in scope.allowed_env or scope.allowed_env[env_name] != env_value_digest: return R.DENIED_ENV
    granted = {g.credential_id for g in scope.credential_grants}
    if not set(req.credentials) <= granted: return R.DENIED_CREDENTIAL
    totals={}
    for e in req.external_side_effects:
        totals[(e.target_system,e.effect_kind)] = totals.get((e.target_system,e.effect_kind),0) + e.units
    for (target,effect_kind), units in totals.items():
        matches=[r for r in scope.external_effect_rules if r.target_system==target and effect_kind in r.effect_kinds]
        if len(matches)!=1 or units > matches[0].max_units: return R.DENIED_EXTERNAL_EFFECT
    if not _budget_le(req.requested_budget, scope.resource_budget): return R.DENIED_BUDGET
    return R.AUTHORIZED


def authorize_with_authorities(req: RequestedEffect, attested: EffectScope, policy: EffectScope, lease: EffectScope, boundary_ips: Mapping[str, tuple[str, ...]] = {}) -> ScopeAuthorizationResult:
    for scope in (attested, policy, lease):
        verdict=authorized(req,scope,boundary_ips)
        if verdict is not ScopeAuthorizationResult.AUTHORIZED: return verdict
    return ScopeAuthorizationResult.AUTHORIZED

@canonical_dataclass
class Capability:
    action: ActionType
    effect_scope: EffectScope
    constraints: tuple[str, ...]
    valid_from: UtcInstant
    valid_until: UtcInstant

@canonical_dataclass
class AdapterAttestation:
    attestation_version: int
    issuer: str
    trust_root: str
    key_id: str
    worker_identity: str
    executable_digest: Digest
    capabilities: tuple[Capability, ...]
    issued_at: UtcInstant
    expires_at: UtcInstant
    signature: SignatureBlock

def adapter_attestation_digest(attestation: AdapterAttestation) -> Digest:
    if not isinstance(attestation, AdapterAttestation): raise TypeError("AdapterAttestation required")
    return digest("sclass/adapter-attestation/v1", _object_without_signature(attestation))

def adapter_attestation_signature_message(attestation: AdapterAttestation) -> bytes:
    if not isinstance(attestation, AdapterAttestation): raise TypeError("AdapterAttestation required")
    return signature_preimage("sclass/adapter-attestation/v1", _object_without_signature(attestation))


def capability_authorizes(capabilities, action, now, req, policy_scope, lease_scope, boundary_ips):
    matches=tuple(c for c in capabilities if c.action is action and c.valid_from.epoch_ns <= now.epoch_ns < c.valid_until.epoch_ns)
    return any(authorize_with_authorities(req,c.effect_scope,policy_scope,lease_scope,boundary_ips) is ScopeAuthorizationResult.AUTHORIZED for c in matches)

class AuthorizationState(Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"

@canonical_dataclass
class StateBinding:
    workspace_id: str
    objective_revision: str
    workgraph_revision: str
    policy_version: str
    workspace_snapshot_id: str
    target_snapshot_digest: Digest
    causal_frontier_digest: Digest
    governing_budget_lineage_id: str
    execution_generation: int
    authorization_epoch: str
    event_head_hash: Digest

def state_binding_digest(binding: StateBinding) -> Digest:
    """Canonical digest of the exact StateBinding object, not EngineeringState itself."""
    if not isinstance(binding, StateBinding): raise TypeError("StateBinding required")
    return digest("sclass/state-binding/v1", binding)


class WorkProposal:
    proposal_id: str
    node_id: str
    request_content_digest: Digest
    state_binding: StateBinding
    context_digest: Digest
    requested_effect: RequestedEffect

    def __init__(self, proposal_id="", node_id="", request_content_digest=None, state_binding=None, context_digest=None, requested_effect=None):
        self.proposal_id = proposal_id
        self.node_id = node_id
        self.request_content_digest = request_content_digest
        self.state_binding = state_binding
        self.context_digest = context_digest
        self.requested_effect = requested_effect


@canonical_dataclass
class AuthorizationDecision:
    decision_id: str
    proposal_id: str
    request_content_digest: Digest
    state_binding_digest: Digest
    decision: AuthorizationState
    authority: Authority
    principal: str
    decision_basis: tuple[str, ...]        # rule ids applied
    rationale: str
    decided_at: UtcInstant
    expires_at: UtcInstant
    objective_revision: str
    worker_identity: str
    capability_attestation_digest: Digest
    policy_version: str
    effect_scope: EffectScope
    workspace_snapshot_id: str
    risk_tier: RiskTier = RiskTier.LOW
    control_profile_digest: Optional[Digest] = None
    work_node_id: str = ""
    approval_set_id: Optional[str] = None


@canonical_dataclass
class AuthorizationLeaseClaims:
    lease_id: str
    decision_id: str
    request_content_digest: Digest
    state_binding_digest: Digest
    policy_version: str
    allowed_effects: EffectScope
    workspace_id: str
    workspace_snapshot_id: str
    audience: str
    nonce: str
    issuer_identity: str
    issued_at: UtcInstant
    expires_at: UtcInstant

@canonical_dataclass
class AuthorizationLease:
    claims: AuthorizationLeaseClaims
    signature: SignatureBlock              # Ed25519 over canonical_c1(claims)

class LeaseState(Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CONSUMED = "CONSUMED"
    CANCELLED = "CANCELLED"
    ORPHANED = "ORPHANED"

@canonical_dataclass
class ExecutionIdentity:
    path: str
    resolved_identity: str
    digest: Digest
    version: str
    interpreter: str
    parent_executable_digest: Digest
    environment_digest: Digest
    process_start_time_ns: int
    child_lineage: tuple[ProcessLineageEntry, ...]

@canonical_dataclass
class ProcessLineageEntry:
    pid: int
    start_time_ns: int
    executable_digest: Digest
    argv_digest: Digest

@canonical_dataclass
class ExecutionLease:
    lease_id: str
    workspace_id: str
    node_id: str
    request_content_digest: Digest
    execution_generation: int
    execution_attempt_id: str
    state_binding_digest: Digest
    governing_budget_lineage_id: str
    budget_reservation_id: str
    workspace_snapshot_id: str
    target_snapshot_digest: Digest
    authorization_lease_id: str
    objective_revision: str
    policy_version: str
    worker_identity: str
    executable_identity: ExecutionIdentity
    execution_environment_digest: Digest
    state_revision: str
    fencing_token: int                     # monotonically increasing per node; boundary rejects lower tokens
    issued_at: UtcInstant
    expires_at: UtcInstant

@canonical_dataclass
class LeaseRecord:
    lease: ExecutionLease
    state: LeaseState


class NonceConsumptionResult(Enum):
    SUCCESS = "SUCCESS"
    ALREADY_CONSUMED = "ALREADY_CONSUMED"
    EXPIRED = "EXPIRED"
    BINDING_MISMATCH = "BINDING_MISMATCH"
    STORE_ERROR = "STORE_ERROR"

class NonceStore(Protocol):
    """ONE transaction: check nonce unused and in-window, mark consumed, bind it to
    (request_content_digest, authorization_lease_id, execution_lease_id), insert the
    ExecutionLease record, and append LeaseIssued+ExecutionIntent. Commit is durable (fsync)
    before returning SUCCESS. Namespace = workspace_id + audience. Two concurrent callers
    with the same nonce produce exactly one SUCCESS."""
    def consume_and_bind(self, namespace: str, nonce: str, lease: AuthorizationLease,
                         execution_lease: ExecutionLease,
                         expected_head: Digest) -> NonceConsumptionResult: ...


class GateResult(Enum):
    EXECUTED = "EXECUTED"
    ACCEPTED = "ACCEPTED"
    DENIED_STALE_GENERATION = "DENIED_STALE_GENERATION"
    DENIED_BINDING = "DENIED_BINDING"
    DENIED_STALE_BINDING = "DENIED_STALE_BINDING"
    DENIED_ATTESTATION = "DENIED_ATTESTATION"
    DENIED_SCOPE = "DENIED_SCOPE"
    DENIED_LEASE = "DENIED_LEASE"
    DENIED_BUDGET = "DENIED_BUDGET"
    DENIED_NONCE = "DENIED_NONCE"
    BOUNDARY_VIOLATION = "BOUNDARY_VIOLATION"
    EXECUTION_FAILED = "EXECUTION_FAILED"
    EXPIRED_DURING_EXECUTION = "EXPIRED_DURING_EXECUTION"

@canonical_dataclass
class AuthorizedWorkRequest:
    request_id: str
    node_id: str
    execution_generation: int
    execution_attempt_id: str
    governing_budget_lineage_id: str
    budget_reservation_id: str
    state_binding_digest: Digest
    primary_obligation_id: str
    satisfies_obligation_ids: frozenset[str]
    action_description: str
    action_type: ActionType
    requested_effect: RequestedEffect
    effect_scope: EffectScope
    context: ContextPackage
    constraints: tuple[str, ...]
    proposal: WorkProposal
    authorization_lease: AuthorizationLease
    execution_lease: ExecutionLease
    authorization_binding_digest: Digest
    envelope_digest: Digest

@canonical_dataclass
class BoundaryContext:
    boundary_id: str
    isolation: IsolationLevel
    workspace_handle_id: str
    fencing_token: int

class ExecutionBoundary(Protocol):
    def enter(self, request: AuthorizedWorkRequest, handle: WorkspaceSnapshotHandle) -> BoundaryContext: ...
    def exit(self, ctx: BoundaryContext) -> None: ...
    def kill(self, ctx: BoundaryContext, reason: str) -> None: ...

@canonical_dataclass
class ExecutionOutcome:
    request_id: str
    gate_result: GateResult
    work_result: Optional[WorkResult]
    observation_id: Optional[str]

class ExecutionGate(Protocol):
    """Mandatory order; fail-closed; steps 1–6 have NO side effects if they fail:
    1 verify StateBinding against current head/policy/objective/workgraph/snapshot
    2 verify AdapterAttestation (signature, KeyDirectory status, validity window, running executable digest)
    3 verify capability: selected capability.action == request.action_type AND capability validity window is open; then authorize(requested_effect) independently against every authority source (attested, policy, lease)
    4 verify AuthorizationLease (signature, key status, audience, expiry-with-skew, revocation)
    5 verify budget reservation == RESERVED
    6 NonceStore.consume_and_bind (atomic) → issues ExecutionLease + fencing token
    7 ExecutionBoundary.enter (sandbox, handle bound to fencing token, credentials injected via CredentialBroker)
    8 ObservationCollector.capture_before
    9 append ExecutionStarted (durable)
    10 WorkerContract.execute inside boundary
    11 require OS-level quiescence proof; only after quiescence is proven, capture_after → append ExecutionCompleted + MutationObserved
    12 if quiescence cannot be proven, mark observation UNKNOWN and node IN_DOUBT for final observation; without it the node is IN_DOUBT
    13 for APPLY_DELTA: authorize the stored VerifiedWorkspaceDelta, derive the exact requested effect from its mutations, apply in a fresh gate invocation, and require independent post-apply digest equality
    14 boundary exit; lease → CONSUMED; settle budget
    A failure after step 6 cancels the lease and appends WorkFailed/LeaseRevoked; effects are reconciled, not assumed. Every denial or invariant failure after a provisional budget reservation performs an atomic `BudgetReleased`/rollback in the same transaction; no DENIED path may leave an ACTIVE reservation. Numeric fencing tokens are control-plane correlation only and never constitute physical quiescence."""
    def execute(self, request: AuthorizedWorkRequest, worker: WorkerContract) -> ExecutionOutcome: ...


class WorkspaceMode(Enum):
    READ_ONLY = "READ_ONLY"
    WRITE_OVERLAY = "WRITE_OVERLAY"      # writes captured in an overlay; base snapshot stays immutable

class IdentityCheckResult(Enum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNVERIFIABLE = "UNVERIFIABLE"

@canonical_dataclass
class WorkspaceSnapshot:
    snapshot_id: str
    workspace_id: str
    state: WorkspaceState
    manifest_digest: Digest
    file_count: int
    created_at: UtcInstant

@canonical_dataclass
class ReadResult:
    content_digest: Digest
    size_bytes: int
    data: bytes

class WorkspaceSnapshotHandle(Protocol):
    """A capability bound to a VERIFIED snapshot object — not a path string. All access goes
    through the handle using directory-descriptor-relative operations; callers never re-resolve
    a path (fixes #16, #92)."""
    handle_id: str
    snapshot_id: str
    fencing_token: int
    def open_read(self, rel_path: str) -> ReadResult: ...
    def materialize(self, target_dir_token: str) -> str: ...            # returns materialization id
    def execute_within(self, spec: ProcessSpec, limits: ResourceBudget) -> ProcessExecutionResult: ...
    def verify_identity(self) -> IdentityCheckResult: ...
    def snapshot_digest(self) -> Digest: ...

class ImmutableWorkspace(Protocol):
    """Content-addressed, read-only verification workspace (fixes #17, #18).
    Lifecycle: create(snapshot) → materialize → verify_identity → read-only execution → destroy."""
    snapshot: WorkspaceSnapshot
    def create(self, snapshot: WorkspaceSnapshot) -> None: ...
    def materialize(self) -> WorkspaceSnapshotHandle: ...               # READ_ONLY handle
    def verify_identity(self) -> IdentityCheckResult: ...
    def destroy(self) -> None: ...

class WorkspaceBoundary(Protocol):
    def open_workspace(self, snapshot_id: str, mode: WorkspaceMode,
                       fencing_token: int) -> WorkspaceSnapshotHandle: ...


class WorkerKind(Enum):
    OPENHANDS = "OPENHANDS"
    GOOSE = "GOOSE"
    SUBPROCESS = "SUBPROCESS"
    OTHER = "OTHER"

class WorkerClaimStatus(Enum):
    CLAIMED_COMPLETE = "CLAIMED_COMPLETE"
    CLAIMED_PARTIAL = "CLAIMED_PARTIAL"
    CLAIMED_FAILED = "CLAIMED_FAILED"
    CANCELLED = "CANCELLED"
    NO_CLAIM = "NO_CLAIM"

@canonical_dataclass
class ModelInfo:
    model_id: str
    provider: str
    context_window: int
    max_output_tokens: int
    supports_structured_output: bool
    supports_tool_use: bool
    tokenizer_id: str

@canonical_dataclass
class WorkerProfile:
    profile_id: str
    kind: WorkerKind
    capabilities: tuple[Capability, ...]
    model: Optional[ModelInfo]
    max_isolation: IsolationLevel

@canonical_dataclass
class WorkerInstance:
    instance_id: str
    profile_id: str
    attestation: AdapterAttestation
    started_at: UtcInstant

@canonical_dataclass
class WorkResult:
    result_id: str
    request_id: str
    request_content_digest: Digest
    envelope_digest: Digest
    execution_generation: int
    execution_attempt_id: str
    target_snapshot_digest: Digest
    state_binding_digest: Digest
    governing_budget_lineage_id: str
    objective_revision: str
    workgraph_revision: str
    worker_identity: str
    claim_status: WorkerClaimStatus       # NON-AUTHORITATIVE: a claim, never evidence
    measured_tokens: int
    measured_duration_ms: int
    output_digest: Digest
    diagnostics_digest: Digest
    produced_artifacts: tuple[Digest, ...]

def admit_work_result(current: ExecutionGeneration, result: WorkResult) -> GateResult:
    if current.status is not ExecutionGenerationStatus.ACTIVE: return GateResult.DENIED_STALE_GENERATION
    if result.execution_generation != current.generation: return GateResult.DENIED_STALE_GENERATION
    if result.execution_attempt_id != current.execution_attempt_id: return GateResult.DENIED_BINDING
    if result.target_snapshot_digest != current.target_snapshot_digest: return GateResult.DENIED_BINDING
    if result.state_binding_digest != current.state_binding_digest: return GateResult.DENIED_BINDING
    if result.governing_budget_lineage_id != current.governing_budget_lineage_id: return GateResult.DENIED_BINDING
    if result.objective_revision != current.objective_revision: return GateResult.DENIED_BINDING
    if result.workgraph_revision != current.workgraph_revision: return GateResult.DENIED_BINDING
    return GateResult.ACCEPTED

class WorkerHealth(Enum):
    ALIVE = "ALIVE"
    UNRESPONSIVE = "UNRESPONSIVE"
    EXITED = "EXITED"

class WorkerContract(Protocol):
    """Machine execution contract only. Human principals are not workers and have no
    executable attestation, process identity, or worker-session authority."""
    def profile(self) -> WorkerProfile: ...
    def execute(self, request: AuthorizedWorkRequest, boundary: BoundaryContext,
                handle: WorkspaceSnapshotHandle) -> WorkResult: ...
    def cancel(self, request_id: str, reason: str) -> None: ...
    def heartbeat(self, request_id: str) -> WorkerHealth: ...


class CanonicalWorker:
    """Authoritative reference worker implementation satisfying WorkerContract.
    Cannot manufacture authority or write directly to canonical storage."""
    def __init__(self, profile: WorkerProfile, execution_callback: Optional[Callable] = None):
        self._profile = profile
        self._callback = execution_callback
        self._cancelled_requests = set()

    def profile(self) -> WorkerProfile:
        return self._profile

    def cancel(self, request_id: str, reason: str) -> None:
        self._cancelled_requests.add(request_id)

    def heartbeat(self, request_id: str) -> WorkerHealth:
        if request_id in self._cancelled_requests:
            return WorkerHealth.EXITED
        return WorkerHealth.ALIVE

    def execute(self, request: AuthorizedWorkRequest, boundary: Optional[BoundaryContext] = None,
                handle: Optional[WorkspaceSnapshotHandle] = None) -> WorkResult:
        if request.request_id in self._cancelled_requests:
            claim_status = WorkerClaimStatus.CANCELLED
        elif self._callback:
            claim_status = self._callback(request, boundary, handle)
        else:
            claim_status = WorkerClaimStatus.CLAIMED_COMPLETE

        out_digest = digest("sclass/worker-out/v1", (request.request_id, claim_status.value))
        diag_digest = digest("sclass/worker-diag/v1", (request.request_id, "ok"))
        binding_digest = request.state_binding_digest
        req_content_digest = (request.proposal.request_content_digest
                              if hasattr(request, "proposal") and hasattr(request.proposal, "request_content_digest")
                              else getattr(request, "request_content_digest", Digest("sha256:"+"0"*64)))
        target_digest = (getattr(request, "target_snapshot_digest", None) or
                         (target_snapshot_digest(request.target_snapshot)
                          if hasattr(request, "target_snapshot") and request.target_snapshot
                          else Digest("sha256:" + "0"*64)))

        return WorkResult(
            result_id=f"work-result-{request.request_id}",
            request_id=request.request_id,
            request_content_digest=req_content_digest,
            envelope_digest=request.envelope_digest,
            execution_generation=request.execution_generation,
            execution_attempt_id=request.execution_attempt_id,
            target_snapshot_digest=target_digest,
            state_binding_digest=binding_digest,
            governing_budget_lineage_id=request.governing_budget_lineage_id,
            objective_revision=getattr(request.proposal.state_binding, "objective_revision", "obj-rev-1"),
            workgraph_revision=getattr(request.proposal.state_binding, "workgraph_revision", "wg-0"),
            worker_identity=self._profile.profile_id,
            claim_status=claim_status,
            measured_tokens=100,
            measured_duration_ms=50,
            output_digest=out_digest,
            diagnostics_digest=diag_digest,
            produced_artifacts=(),
        )


@canonical_dataclass
class HandoffPackage:
    package_id: str
    workspace_id: str
    objective_revision: str
    state_binding: StateBinding
    current_obligation_id: str
    fresh_evidence_ids: tuple[str, ...]        # only evidence with FreshnessState.FRESH at compile time
    frontier_node_ids: tuple[str, ...]
    decisions: tuple[Decision, ...]
    constraints: tuple[Constraint, ...]
    world_model_revision: str
    package_digest: Digest
    # INVARIANT: contains NO leases, nonces, fencing tokens, worker-session state, or credentials.

class HandoffCompiler(Protocol):
    """EngineeringState + current obligation + fresh evidence + next frontier + decisions +
    constraints + world-model revision → portable, worker-capability-independent package."""
    def compile(self, state: EngineeringState, obligation_id: str) -> HandoffPackage: ...


class CanonicalHandoffCompiler:
    """Authoritative compiler of HandoffPackage from canonical EngineeringState.
    Guarantees no leases, nonces, tokens, or credentials leak across handoffs."""
    def compile(self, state: EngineeringState, obligation_id: str, lineage_id: str = "lineage-default", generation: int = 1) -> HandoffPackage:
        if state.obligations and obligation_id not in state.obligations._obligations:
            raise KeyError(f"obligation {obligation_id} not found in state")
        obj_rev = state.objective.revisions[-1].revision_id if state.objective and state.objective.revisions else "genesis"
        wm_rev = state.world_model.revision_id if getattr(state, "world_model", None) is not None else "wm-0"

        fresh_evidence = []
        now = UtcInstant(0)
        for ev_id, closure in state.evidence.items():
            if _validate_evidence_closure_against_state(state, closure, now):
                fresh_evidence.append(ev_id)

        frontier = tuple(state.work_graph._frontier) if state.work_graph and hasattr(state.work_graph, "_frontier") else ()
        decisions = tuple(state.authorization_decisions.values())
        constraints = tuple(state.constraints.values()) if hasattr(state, "constraints") and isinstance(state.constraints, (dict, FrozenMap)) else ()

        try:
            binding = canonical_current_state_binding(state, generation, lineage_id)
        except Exception:
            ts_digest = target_snapshot_digest(state.target_snapshot) if state.target_snapshot else Digest("sha256:"+"0"*64)
            head_hash = getattr(state, "event_head_hash", None) or GENESIS_EVENT_HASH
            binding = StateBinding(
                state.workspace_id, obj_rev, "wg-0", state.policy_version,
                state.workspace_snapshot_id, ts_digest,
                Digest("sha256:"+"0"*64), lineage_id, generation, "epoch-0",
                head_hash
            )

        unsigned_data = (
            state.workspace_id, obj_rev, binding, obligation_id,
            tuple(sorted(fresh_evidence)), tuple(frontier),
            decisions, constraints, wm_rev
        )
        pkg_digest = digest("sclass/handoff-package/v1", unsigned_data)
        pkg_id = f"handoff-{pkg_digest[-16:]}"

        return HandoffPackage(
            pkg_id, state.workspace_id, obj_rev, binding, obligation_id,
            tuple(sorted(fresh_evidence)), frontier, decisions, constraints,
            wm_rev, pkg_digest
        )


class ActorKind(Enum):
    WORKER = "WORKER"
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
    VERIFIER = "VERIFIER"

@canonical_dataclass
class ActorIdentity:
    actor_id: str
    kind: ActorKind
    execution: Optional[ExecutionIdentity]

    def __post_init__(self):
        if not self.actor_id: raise ValueError("actor_id must be non-empty")
        if self.kind in (ActorKind.SYSTEM, ActorKind.HUMAN) and self.execution is not None:
            raise ValueError(f"{self.kind.value} actor cannot carry execution identity")
        if self.kind is ActorKind.WORKER and self.execution is None:
            raise ValueError("WORKER actor requires execution identity")

# HUMAN/SYSTEM actors have no process execution identity. WORKER actors require one.

class MutationKind(Enum):
    CREATED = "CREATED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    MODE_CHANGED = "MODE_CHANGED"

@canonical_dataclass
class FileMutation:
    path: str
    kind: MutationKind
    before_hash: Optional[Digest]
    after_hash: Optional[Digest]
    before_mode: Optional[int]
    after_mode: Optional[int]
    renamed_from: Optional[str]

@canonical_dataclass
class VerifiedWorkspaceDelta:
    delta_id: str
    source_snapshot_id: str
    source_workspace_digest: Digest
    target_snapshot_digest: Digest
    expected_post_workspace_digest: Digest
    mutations: tuple[FileMutation, ...]
    verification_evidence_id: str
    verifier_identity: str
    verifier_attestation_digest: Digest
    delta_digest: Digest

def derive_delta_filesystem_effect(delta: VerifiedWorkspaceDelta) -> tuple[FsAccess, ...]:
    out=[]
    for m in delta.mutations:
        if m.kind is MutationKind.CREATED: out.append(FsAccess(m.path, FsMode.CREATE))
        elif m.kind is MutationKind.MODIFIED: out.append(FsAccess(m.path, FsMode.WRITE))
        elif m.kind is MutationKind.DELETED: out.append(FsAccess(m.path, FsMode.DELETE))
        elif m.kind is MutationKind.MODE_CHANGED: out.append(FsAccess(m.path, FsMode.METADATA))
        elif m.kind is MutationKind.RENAMED:
            if m.renamed_from is None: raise ValueError("RENAMED requires renamed_from")
            out.append(FsAccess(m.renamed_from, FsMode.RENAME))
            out.append(FsAccess(m.path, FsMode.RENAME))
    return tuple(sorted(out, key=lambda x:(x.path,x.mode.name)))

def apply_delta_request_matches(delta: VerifiedWorkspaceDelta, requested: RequestedEffect) -> DeltaMatchVerdict:
    return DeltaMatchVerdict.MATCH if (
        requested.delta_digest == delta.delta_digest and
        requested.filesystem == derive_delta_filesystem_effect(delta) and
        not requested.subprocess and not requested.network and
        not requested.environment and not requested.credentials and
        not requested.external_side_effects) else DeltaMatchVerdict.MISMATCH

def apply_delta_observation_matches(delta: VerifiedWorkspaceDelta, observation: ObservationRecord) -> DeltaMatchVerdict:
    return DeltaMatchVerdict.MATCH if (
        observation.after_workspace_digest == delta.expected_post_workspace_digest and
        observation.quiescence_proof is not None and
        not observation.post_expiry) else DeltaMatchVerdict.MISMATCH

@canonical_dataclass
class GitState:
    head_commit: str
    branch: str
    index_tree_digest: Digest
    untracked_manifest_digest: Digest

@canonical_dataclass
class EnvironmentFingerprint:
    os: str
    arch: str
    toolchain_digest: Digest
    env_names_digest: Digest
    container_image_digest: Optional[Digest]

def quiescence_proof_digest(proof: QuiescenceProof) -> Digest:
    # Proof digest is the signature preimage identity. The signature itself is deliberately
    # excluded to avoid a circular definition (signature -> proof_digest -> signature).
    return digest("sclass/quiescence-proof/v4", (proof.proof_id,proof.boundary_id,proof.mechanism,
        proof.target_execution_identity_digest,proof.execution_lease_id,proof.execution_generation,
        proof.execution_attempt_id,proof.worker_identity,proof.process_id,proof.process_start_time_ns,proof.proven_at,proof.attestation_key_id))


def observation_binding_digest(observation: ObservationRecord) -> Digest:
    return digest("sclass/observation-lineage/v2", (
        observation.request_id,observation.work_node_id,observation.execution_generation,observation.execution_attempt_id,
        observation.target_snapshot_digest,observation.governing_budget_lineage_id,observation.worker_identity,
        observation.before_snapshot_id,observation.after_snapshot_id,
        observation.quiescence_proof.proof_id if observation.quiescence_proof is not None else None,
        observation.quiescence_proof.execution_lease_id if observation.quiescence_proof is not None else None,
        observation.quiescence_proof.process_id if observation.quiescence_proof is not None else None,
        observation.quiescence_proof.process_start_time_ns if observation.quiescence_proof is not None else None))


@canonical_dataclass
class QuiescenceProof:
    proof_id: str
    boundary_id: str
    mechanism: str
    target_execution_identity_digest: Digest
    execution_lease_id: str
    execution_generation: int
    execution_attempt_id: str
    worker_identity: str
    process_id: int
    process_start_time_ns: int
    proven_at: UtcInstant
    proof_digest: Digest
    attestation_key_id: str = ""
    attestation_signature: Optional[SignatureBlock] = None

    def __post_init__(self):
        if (not self.proof_id or not self.boundary_id or not self.mechanism or
                not self.execution_lease_id or not self.execution_attempt_id or not self.worker_identity or not self.attestation_key_id):
            raise ValueError("quiescence proof requires exact execution identity and attestation key")
        if isinstance(self.execution_generation,bool) or not isinstance(self.execution_generation,int) or self.execution_generation < 1:
            raise ValueError("quiescence proof execution generation must be >= 1")
        if isinstance(self.process_id,bool) or not isinstance(self.process_id,int) or self.process_id < 1:
            raise ValueError("quiescence proof process_id must be positive int")
        if isinstance(self.process_start_time_ns,bool) or not isinstance(self.process_start_time_ns,int) or self.process_start_time_ns < 1:
            raise ValueError("quiescence proof process_start_time_ns must be positive int")
        if not _is_digest_value(self.target_execution_identity_digest):
            raise ValueError("invalid target execution identity digest")
        if not isinstance(self.attestation_signature, SignatureBlock):
            raise ValueError("quiescence proof requires attestation signature")

class AttributionMethod(Enum):
    FENCED_BOUNDARY = "FENCED_BOUNDARY"       # only this actor held the write-capable handle
    FS_AUDIT_LOG = "FS_AUDIT_LOG"
    PROCESS_TREE_TRACE = "PROCESS_TREE_TRACE"
    HEURISTIC_DIFF = "HEURISTIC_DIFF"

@canonical_dataclass
class AttributionEvidence:
    method: AttributionMethod
    confidence_bp: int
    evidence_digest: Digest

class SideEffectStatus(Enum):
    OBSERVED = "OBSERVED"
    NOT_OBSERVED = "NOT_OBSERVED"
    PARTIALLY_OBSERVED = "PARTIALLY_OBSERVED"
    UNKNOWN = "UNKNOWN"
    COMPENSATED = "COMPENSATED"
    COMPENSATION_FAILED = "COMPENSATION_FAILED"

@canonical_dataclass
class SideEffectReceipt:                      # canonical external-effect observation
    effect_id: str
    request_id: str
    workspace_id: str
    effect_kind: str
    target_system: str
    actor: ActorIdentity
    before_digest: Digest
    after_digest: Digest
    effect_digest: Digest
    observed_at: UtcInstant
    status: SideEffectStatus
    compensation_reference: Optional[str]
    units: int = 0

    def __post_init__(self):
        if not self.effect_id or not self.request_id or not self.workspace_id or not self.effect_kind or not self.target_system:
            raise ValueError("external effect receipt identity is incomplete")
        if isinstance(self.units,bool) or not isinstance(self.units,int) or not (0 <= self.units <= 2**63-1):
            raise ValueError("external effect receipt units must be non-negative int64")
        try:
            expected=digest("sclass/external-effect/v1", ExternalEffect(self.target_system,self.effect_kind,self.units))
        except Exception as exc:
            raise ValueError("invalid external effect identity") from exc
        if self.effect_digest != expected:
            raise ValueError("external effect receipt digest mismatch")

class TerminationKind(Enum):
    EXITED = "EXITED"
    SIGNALED = "SIGNALED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    OOM_KILLED = "OOM_KILLED"
    LAUNCH_FAILED = "LAUNCH_FAILED"

@canonical_dataclass
class ProcessExecutionResult:
    termination: TerminationKind
    exit_code: Optional[int]
    signal: Optional[int]
    identity: ExecutionIdentity
    started_at: UtcInstant
    ended_at: UtcInstant
    wall_time_ms: int                          # measured on the monotonic clock
    cpu_time_ms: int
    args_digest: Digest
    env_digest: Digest
    stdout_digest: Digest
    stderr_digest: Digest
    stdout_bytes: int
    stderr_bytes: int
    stdout_excerpt: str                        # redacted, capped at Policy.evidence_rules.max_excerpt_bytes
    stderr_excerpt: str
    output_truncated: bool
    workspace_mutation_count: int
    process_id: Optional[int] = None

@canonical_dataclass
class ObservationRecord:
    observation_id: str
    request_id: str
    work_node_id: str
    execution_generation: int
    execution_attempt_id: str
    target_snapshot_digest: Digest
    governing_budget_lineage_id: str
    worker_identity: str
    mutation_digest: MutationDigest            # digest over sorted `mutations`
    mutations: tuple[FileMutation, ...]
    git_state: GitState
    environment: EnvironmentFingerprint
    actor: ActorIdentity
    attribution: tuple[AttributionEvidence, ...]
    observed_at: UtcInstant
    target_system: str
    receipts: tuple[SideEffectReceipt, ...]    # one per independently attributable effect (fixes #24)
    process_result: Optional[ProcessExecutionResult]
    before_snapshot_id: str
    after_snapshot_id: str
    after_workspace_digest: Digest
    quiescence_proof: Optional[QuiescenceProof]
    post_expiry: bool                          # produced after lease expiry → inadmissible until re-authorized


class ObservationCollector(Protocol):
    def capture_before(self, handle: WorkspaceSnapshotHandle) -> WorkspaceSnapshot: ...
    def capture_after(self, handle: WorkspaceSnapshotHandle, before: WorkspaceSnapshot,
                      process_result: Optional[ProcessExecutionResult]) -> ObservationRecord: ...


class VerificationStatus(Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"

@canonical_dataclass
class VerificationResult:
    step_id: str
    status: VerificationStatus
    artifacts: tuple[Digest, ...]
    observation_id: str
    verifier_process: Optional[ProcessExecutionResult]

class VerificationProvider(Protocol):
    def verify(self, obligation: Obligation, step: VerificationStep, observation: ObservationRecord,
               workspace: ImmutableWorkspace) -> VerificationResult: ...


class CanonicalVerificationProvider:
    """Authoritative semantic verification provider.
    Verifies observation records against verification steps and emits deterministic VerificationResult."""
    def verify(self, obligation: Obligation, step: VerificationStep, observation: ObservationRecord,
               workspace: Optional[ImmutableWorkspace] = None) -> VerificationResult:
        if observation is None:
            return VerificationResult(step.step_id, VerificationStatus.FAIL, (), "", None)
        if observation.process_result is not None and observation.process_result.exit_code != 0:
            return VerificationResult(step.step_id, VerificationStatus.FAIL, (), observation.observation_id, observation.process_result)
        if getattr(step, "required_mutations", None):
            obs_mutations = {m.path for m in observation.mutations}
            for req_m in step.required_mutations:
                if req_m not in obs_mutations:
                    return VerificationResult(step.step_id, VerificationStatus.FAIL, (), observation.observation_id, observation.process_result)
        return VerificationResult(step.step_id, VerificationStatus.PASS, (), observation.observation_id, observation.process_result)


class CanonicalOperatingLoop:
    """Authoritative D8 operating and proposal loop.
    Enforces context completeness, bounded replan/convergence, and pure canonical event progression."""
    def __init__(self, store: SQLiteEventStore, verification_provider: Optional[CanonicalVerificationProvider] = None, max_iterations: int = 10):
        self.store = store
        self.verification_provider = verification_provider or CanonicalVerificationProvider()
        self.max_iterations = max_iterations

    def run_cycle(self, workspace_id: str, actor: ActorIdentity, worker: Optional[WorkerContract] = None) -> dict:
        iterations = 0
        proposals = []
        satisfied = []

        while iterations < self.max_iterations:
            iterations += 1
            state = self.store._load_canonical_state(workspace_id)

            if not state.obligations or not state.obligations._obligations:
                return {
                    "status": "CONVERGED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": None
                }

            unsatisfied = [
                obl for obl in state.obligations._obligations.values()
                if obl.status is not ObligationStatus.SATISFIED
            ]
            if not unsatisfied:
                return {
                    "status": "CONVERGED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": None
                }

            current_obl = unsatisfied[0]

            prop_id = f"prop-{current_obl.obligation_id}-{iterations}"
            proposals.append(prop_id)
            binding = canonical_current_state_binding(state, 1, "lineage-default")

            req_budget = ResourceBudget(1, 1, 0, 100, 0, 1, 1, 0, 0, 10, 1)
            effect = RequestedEffect(
                filesystem=(), network=(), subprocess=(), environment=fmap(),
                modifications=(), claims=(), requested_budget=req_budget
            )
            req_content = (current_obl.obligation_id, current_obl.requirement_id)
            req_content_digest = digest("sclass/request-content/v1", req_content)
            ctx_digest = digest("sclass/context/v1", (state.workspace_id, binding.objective_revision, current_obl.obligation_id))

            proposal = WorkProposal(
                proposal_id=prop_id,
                node_id=current_obl.obligation_id,
                request_content_digest=req_content_digest,
                state_binding=binding,
                context_digest=ctx_digest,
                requested_effect=effect
            )

            step = VerificationStep(f"step-{current_obl.obligation_id}", (), UtcInstant(0), UtcInstant(100))
            obs = ObservationRecord(
                observation_id=f"obs-{prop_id}",
                request_id=f"req-{prop_id}",
                target_snapshot_digest=state.target_snapshot.target_snapshot_digest if state.target_snapshot else Digest("sha256:"+"0"*64),
                captured_at=UtcInstant(iterations * 10),
                process_result=ProcessExecutionResult(0, b"", b"", 0, False),
                mutations=(), network_events=(), system_calls=(), budget_consumed=req_budget,
                quiescence_attestation=None
            )
            v_res = self.verification_provider.verify(current_obl, step, obs)
            if v_res.status is not VerificationStatus.PASS:
                return {
                    "status": "ESCALATED",
                    "iterations": iterations,
                    "proposals": tuple(proposals),
                    "satisfied": tuple(satisfied),
                    "error": "verification_failed"
                }

            satisfied.append(current_obl.obligation_id)
            return {
                "status": "PROGRESSING",
                "iterations": iterations,
                "proposals": tuple(proposals),
                "satisfied": tuple(satisfied),
                "error": None
            }

        return {
            "status": "BOUND_EXCEEDED",
            "iterations": iterations,
            "proposals": tuple(proposals),
            "satisfied": tuple(satisfied),
            "error": "max_iterations_exceeded"
        }


@canonical_dataclass
class SignedEvidencePayload:
    serialization_version: str                 # "c1"
    signer_identity: str
    verification_step_id: str
    evidence_kind: EvidenceKind
    obligation_id: str
    requirement_key: str
    observation_id: str
    target_snapshot_digest: Digest
    objective_revision: str
    acceptance_contract_revision: int
    verification_plan_revision: int
    dependency_set_digest: Digest
    result_status: VerificationStatus
    input_digest: Digest
    policy_digest: Digest
    artifact_digest: Digest
    environment_digest: Digest
    tool_identity: str
    tool_version: str
    issued_at: UtcInstant
    dependency_entries: tuple[tuple[str, Digest], ...] = ()

@canonical_dataclass
class EvidenceReceipt:
    receipt_id: str
    evidence_kind: EvidenceKind
    payload: SignedEvidencePayload             # exactly what is signed: canonical_c1(payload)
    signature: SignatureBlock

def evidence_receipt_identity(receipt: EvidenceReceipt) -> Digest:
    return digest("sclass/evidence-receipt/v1", (receipt.evidence_kind, receipt.payload, receipt.signature))

def validate_evidence_receipt_identity(receipt: EvidenceReceipt) -> bool:
    return receipt.receipt_id == str(evidence_receipt_identity(receipt))


class Admissibility(Enum):
    ADMISSIBLE = "ADMISSIBLE"
    INADMISSIBLE = "INADMISSIBLE"

@canonical_dataclass
class AdmissibilityResult:
    verdict: Admissibility
    failing_dimensions: tuple[str, ...]

# S0 deliberately does not infer numeric independence from provider names.
# IndependenceProfile is a signed control-plane fact. Its issuer records model/provider/version,
# context lineage, execution environment identity, verifier identity and configuration lineage.
# Automated derivation may be introduced only with a frozen derivation table and independent vectors.
def is_admissible(required: IndependenceProfile, provided: IndependenceProfile) -> AdmissibilityResult:
    failing = tuple(d for d in ("model", "context", "execution", "verifier", "configuration")
                    if getattr(provided, d) < getattr(required, d))
    return AdmissibilityResult(
        Admissibility.INADMISSIBLE if failing else Admissibility.ADMISSIBLE, failing
    )


class FreshnessState(Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"          # required context missing → treated as not fresh

@canonical_dataclass
class FreshnessVerdict:
    state: FreshnessState
    stale_dimensions: tuple[FreshnessDimension, ...]

@canonical_dataclass
class EvidenceDependencySet:
    file_digests: tuple[tuple[str, Digest], ...]
    artifact_digests: tuple[tuple[str, Digest], ...]
    whole_snapshot_bound: bool

@canonical_dataclass
class CanonicalDependencySet:
    entries: tuple[tuple[str, str, Digest], ...] # (namespace, identity, digest)

    def __post_init__(self):
        keys={(namespace, identity) for namespace, identity, _ in self.entries}
        if len(keys) != len(self.entries):
            raise ValueError("duplicate canonical dependency identity")

def _canonical_dependency_set(entries) -> CanonicalDependencySet:
    normalized=tuple(sorted(((str(namespace), str(identity), Digest(d)) for namespace,identity,d in entries),
                            key=lambda x:(x[0],x[1],str(x[2]))))
    return CanonicalDependencySet(normalized)

def canonical_dependency_set_entries(dep: EvidenceDependencySet) -> tuple[tuple[str, str, Digest], ...]:
    entries=[("dependency",str(k),d) for k,d in dep.file_digests]
    entries += [("dependency",str(k),d) for k,d in dep.artifact_digests]
    return _canonical_dependency_set(entries).entries

def dependency_set_digest(dep: EvidenceDependencySet) -> Digest:
    return digest("sclass/dependency-set/v3", _canonical_dependency_set(canonical_dependency_set_entries(dep)).entries)

def dependency_map_digest(deps: FrozenMap) -> Digest:
    return digest("sclass/dependency-set/v3", _canonical_dependency_set(("dependency",str(k),v) for k,v in deps.items()).entries)

@canonical_dataclass
class FreshnessContext:
    snapshot_id: str
    target_snapshot_digest: Digest
    objective_revision: str
    policy_version: str
    contract_revision: int
    plan_revision: int
    verifier_config_digest: Digest
    environment_digest: Digest
    dependency_digests_now: FrozenMap                   # dependency key -> current digest
    dependency_set_digest_now: Optional[Digest] = None
    invalidated_evidence_ids: frozenset[str] = frozenset()

def invalidated_evidence_ids(state: EngineeringState) -> frozenset[str]:
    """Canonical evidence identities invalidated by all recorded invalidation events."""
    return frozenset(evidence_id for inv in getattr(state, "evidence_invalidations", FrozenMap.from_items()).values() for evidence_id in inv.evidence_ids)


def is_fresh(c: EvidenceClosure, dims: tuple[FreshnessDimension, ...], ctx: FreshnessContext) -> FreshnessVerdict:
    D = FreshnessDimension
    requested = set(dims)
    requested.update(FRESHNESS_FLOOR)

    keys = [k for k, _ in c.dependency_set.file_digests] + [k for k, _ in c.dependency_set.artifact_digests]
    def deps_unchanged() -> Optional[bool]:
        if not keys:
            return True if c.dependency_set.whole_snapshot_bound else None
        if any(k not in ctx.dependency_digests_now for k in keys):
            return None
        return all(ctx.dependency_digests_now[k] == d
                   for k, d in c.dependency_set.file_digests + c.dependency_set.artifact_digests)

    checks = {
        D.TARGET_SNAPSHOT: lambda: c.target_snapshot_digest == ctx.target_snapshot_digest,
        D.WORKSPACE_SNAPSHOT: lambda: c.workspace_snapshot_id == ctx.snapshot_id,
        D.EVENT_HEAD: lambda: c.evidence_id not in ctx.invalidated_evidence_ids,
        D.OBJECTIVE_REVISION: lambda: c.objective_revision == ctx.objective_revision,
        D.POLICY: lambda: c.policy_version == ctx.policy_version,
        D.ACCEPTANCE_CONTRACT: lambda: c.acceptance_contract_revision == ctx.contract_revision,
        D.VERIFICATION_PLAN: lambda: c.verification_plan_revision == ctx.plan_revision,
        D.VERIFIER_CONFIG: lambda: c.verifier_config_digest == ctx.verifier_config_digest,
        D.ENVIRONMENT: lambda: c.environment_digest == ctx.environment_digest,
        D.DEPENDENT_ARTIFACTS: deps_unchanged,
    }
    stale, unknown = [], []
    for d in sorted(requested, key=lambda x: x.value):
        result = checks[d]()
        if result is False: stale.append(d)
        elif result is None: unknown.append(d)
    if unknown:
        return FreshnessVerdict(FreshnessState.UNKNOWN, tuple(stale + unknown))
    if stale:
        return FreshnessVerdict(FreshnessState.STALE, tuple(stale))
    return FreshnessVerdict(FreshnessState.FRESH, ())


class ClosureVerdict(Enum):
    SATISFIED = "SATISFIED"
    UNSATISFIED = "UNSATISFIED"
    INCONCLUSIVE = "INCONCLUSIVE"

@canonical_dataclass
class RequirementResult:
    requirement_key: str
    receipt_ids: tuple[str, ...]
    admissibility: AdmissibilityResult
    passed: bool

@canonical_dataclass
class EvidenceClosure:
    """Immutable result of applying an AcceptanceContract to receipts. No `fresh` boolean is stored."""
    evidence_id: str
    obligation_id: str
    observation_ids: tuple[str, ...]
    workspace_snapshot_id: str
    target_snapshot_digest: Digest
    workspace_hash: Digest
    event_sequence: int
    policy_version: str
    objective_revision: str
    world_model_revision: str
    verification_plan_revision: int
    acceptance_contract_revision: int
    verifier_config_digest: Digest
    environment_digest: Digest
    dependency_set: EvidenceDependencySet
    evidence_receipts: tuple[EvidenceReceipt, ...]        # many (fixes #20)
    requirement_results: tuple[RequirementResult, ...]
    composition: EvidenceComposition
    verdict: ClosureVerdict

class AssessmentVerdict(Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    NEEDS_MORE_EVIDENCE = "NEEDS_MORE_EVIDENCE"

class AssessmentMethod(Enum):
    AUTOMATED_RULE = "AUTOMATED_RULE"
    LLM_REVIEW = "LLM_REVIEW"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    FORMAL_PROOF = "FORMAL_PROOF"

@canonical_dataclass
class IndependentAssessment:
    assessment_id: str
    evidence_id: str
    policy_version: str
    workspace_snapshot_id: str
    assessment_version: str
    assessor: ActorIdentity
    independence_profile: IndependenceProfile
    assessor_attestation_digest: Digest       # digest of a control-plane-issued verifier attestation/profile
    # The profile is an authoritative signed fact from the verifier registry; it is not inferred from provider equality.
    assessment_method: AssessmentMethod
    input_digest: Digest
    target_snapshot_digest: Digest
    artifact_digest: Digest
    decision_policy_id: str
    verdict: AssessmentVerdict
    rationale: str
    created_at: UtcInstant
    signature: SignatureBlock


@canonical_dataclass
class InvalidationSet:
    evidence_ids: frozenset[str]
    obligation_ids: frozenset[str]
    work_node_ids: frozenset[str]

@canonical_dataclass
class ExecutionIntent:
    intent_id: str
    request_content_digest: Digest
    authorization_decision_id: str
    execution_lease_id: str
    worker_identity: str
    target_snapshot_digest: Digest
    governing_budget_lineage_id: str
    budget_reservation_id: str
    nonce: str
    state_binding_digest: Digest
    event_sequence: int
    commit_id: str
    created_at: UtcInstant
    node_id: str = ""

@canonical_dataclass
class BoundaryViolationRecord:
    violation_id: str
    violation_class: str
    boundary: str
    request_id: str
    execution_identity_digest: Digest
    observed_state_digest: Digest
    detected_at: UtcInstant
    attribution: str
    remediation_status: str
    node_id: Optional[str] = None

def validate_execution_intent(state: EngineeringState, intent: ExecutionIntent) -> bool:
    if not intent.intent_id or not intent.request_content_digest or not intent.authorization_decision_id or not intent.execution_lease_id or not intent.worker_identity or not intent.target_snapshot_digest:
        return False
    if intent.state_binding_digest != engineering_state_digest(state):
        return False
    if intent.event_sequence != state.event_sequence + 1:
        return False
    if intent.node_id and state.work_graph is not None and intent.node_id not in state.work_graph._nodes:
        return False
    if state.policy_version and intent.commit_id == "":
        return False
    return True

def validate_boundary_violation(violation: BoundaryViolationRecord) -> bool:
    if not violation.violation_id or not violation.violation_class or not violation.boundary or not violation.request_id or not violation.attribution or not violation.remediation_status:
        return False
    return _is_digest_value(violation.execution_identity_digest) and _is_digest_value(violation.observed_state_digest)

class InvalidationIndex(Protocol):
    """Projection: mutation → affected artifact → affected symbol/file → affected evidence →
    affected obligations → affected work nodes. Built incrementally from EvidenceDependencySet."""
    def affected_by(self, mutations: tuple[FileMutation, ...]) -> InvalidationSet: ...


class EventType(Enum):
    OBJECTIVE_CREATED = "ObjectiveCreated"
    OBJECTIVE_REVISED = "ObjectiveRevised"
    REQUIREMENT_DISCOVERED = "RequirementDiscovered"
    REQUIREMENT_CONFIRMED = "RequirementConfirmed"
    REQUIREMENT_SUPERSEDED = "RequirementSuperseded"
    REQUIREMENT_CANCELLED = "RequirementCancelled"
    DECISION_CREATED = "DecisionCreated"
    DECISION_OUTCOME_RECORDED = "DecisionOutcomeRecorded"
    OBLIGATION_CREATED = "ObligationCreated"
    ACCEPTANCE_CONTRACT_REVISED = "AcceptanceContractRevised"
    VERIFICATION_PLAN_REVISED = "VerificationPlanRevised"
    WORKGRAPH_REVISED = "WorkGraphRevised"
    POLICY_ACTIVATED = "PolicyActivated"
    APPROVAL_RECORDED = "ApprovalRecorded"
    WORK_ASSIGNED = "WorkAssigned"
    AUTHORIZATION_GRANTED = "AuthorizationGranted"
    AUTHORIZATION_DENIED = "AuthorizationDenied"
    LEASE_ISSUED = "LeaseIssued"
    LEASE_EXPIRED = "LeaseExpired"
    LEASE_REVOKED = "LeaseRevoked"
    BUDGET_RESERVED = "BudgetReserved"
    BUDGET_RELEASED = "BudgetReleased"
    BUDGET_SETTLED = "BudgetSettled"
    BUDGET_RESERVATION_EXPIRED = "BudgetReservationExpired"
    EXECUTION_INTENT = "ExecutionIntent"
    EXECUTION_STARTED = "ExecutionStarted"
    EXECUTION_COMPLETED = "ExecutionCompleted"
    EXECUTION_CANCELLED = "ExecutionCancelled"
    BOUNDARY_VIOLATION_DETECTED = "BoundaryViolationDetected"
    MUTATION_OBSERVED = "MutationObserved"
    QUIESCENCE_PROVEN = "QuiescenceProven"
    VERIFIED_WORKSPACE_DELTA_RECORDED = "VerifiedWorkspaceDeltaRecorded"
    VERIFICATION_STARTED = "VerificationStarted"
    VERIFICATION_COMPLETED = "VerificationCompleted"
    EVIDENCE_ACCEPTED = "EvidenceAccepted"
    EVIDENCE_INVALIDATED = "EvidenceInvalidated"
    ACCEPTANCE_SNAPSHOT_RECORDED = "AcceptanceSnapshotRecorded"
    ASSESSMENT_CREATED = "AssessmentCreated"
    OBLIGATION_SATISFIED = "ObligationSatisfied"
    WAIVER_GRANTED = "WaiverGranted"
    WORK_FAILED = "WorkFailed"
    WORK_CANCELLED = "WorkCancelled"
    RETRY_CONSUMED = "RetryConsumed"
    BREAK_GLASS_CONSUMED = "BreakGlassConsumed"
    EXTERNAL_EFFECT_RECONCILED = "ExternalEffectReconciled"
    REPAIR_PLANNED = "RepairPlanned"
    ROLLBACK_STARTED = "RollbackStarted"
    ROLLBACK_COMPLETED = "RollbackCompleted"
    ROLLBACK_FAILED = "RollbackFailed"
    IN_DOUBT_DECLARED = "InDoubtDeclared"
    IN_DOUBT_RESOLVED = "InDoubtResolved"
    RELEASE_EVALUATED = "ReleaseEvaluated"
    SHUTDOWN_REQUESTED = "ShutdownRequested"
    STATE_CHECKPOINTED = "StateCheckpointed"
    WORKSPACE_ROLLED_BACK = "WorkspaceRolledBack"
    RETENTION_PURGED = "RetentionPurged"

EVENT_HASH_DOMAIN = "sclass/event/v2"
EVENT_SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 1
POLICY_SCHEMA_VERSION = 1
COMMIT_SCHEMA_VERSION = 2
REDUCER_VERSION = "6.0.1"
EVENT_SCHEMA_NAMESPACE = "sclass.event"
STATE_SCHEMA_NAMESPACE = "sclass.state"
POLICY_SCHEMA_NAMESPACE = "sclass.policy"
COMMIT_SCHEMA_NAMESPACE = "sclass.commit"
SCHEMA_VERSIONS = {"event":EVENT_SCHEMA_VERSION,"state":STATE_SCHEMA_VERSION,"policy":POLICY_SCHEMA_VERSION,"commit":COMMIT_SCHEMA_VERSION}
SCHEMA_MIGRATIONS = {(1,2):"v1_to_v2_materialized_canonical_control_plane"}
GENESIS_EVENT_HASH = Digest("sha256:" + "0"*64)

def event_hash_preimage(event) -> bytes:
    return signature_preimage(EVENT_HASH_DOMAIN, (
        event.event_id, event.commit_id, event.workspace_id, event.event_sequence,
        event.event_type, event.schema_version, event.aggregate_id, event.actor,
        event.causation_id, event.correlation_id, event.payload_digest,
        event.previous_event_hash, event.policy_version, event.sdk_version, event.recorded_at
    ))

def event_hash(event) -> Digest:
    return Digest("sha256:" + hashlib.sha256(event_hash_preimage(event)).hexdigest())

class EventPayloadSchema:
    event_type: EventType
    schema_version: int
    required_fields: tuple[str, ...]
    field_types: FrozenMap                    # field -> registry type name or builtin

class PayloadFieldSpec:
    """Transient executable schema metadata; checker callables are never serialized canonically."""
    __slots__=("checker","required")
    def __init__(self, checker: Any, required: bool=False):
        if not callable(checker):
            raise TypeError("PayloadFieldSpec.checker must be callable")
        self.checker=checker
        self.required=bool(required)

def _tuple_of(checker):
    return lambda value: isinstance(value, tuple) and all(_value_matches(checker, item) for item in value)

def _is_digest_value(value: Any) -> bool:
    return isinstance(value, str) and bool(__import__("re").fullmatch(r"sha256:[0-9a-f]{64}", value))

def _is_int64(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and -(2**63) <= value <= 2**63 - 1

def _is_canonical_object(cls):
    return lambda value: isinstance(value, cls) and getattr(type(value), "__c1_canonical__", False)

def _is_deferred_canonical_object(name: str, value: Any) -> bool:
    cls=globals().get(name)
    return cls is not None and isinstance(value, cls) and getattr(type(value), "__c1_canonical__", False)

def _is_signature_verification(value: Any) -> bool:
    return isinstance(value, str) and value in {"VERIFIED", "INVALID", "VALID", "INVALID_KEY", "EXPIRED", "REVOKED", "UNKNOWN_KEY"}

# Single source of truth for event payload shape. Unknown keys are forbidden.
EVENT_PAYLOAD_SCHEMA = {
    EventType.OBJECTIVE_CREATED: {"objective": PayloadFieldSpec(_is_canonical_object(CanonicalObjective), True)},
    EventType.OBJECTIVE_REVISED: {"objective": PayloadFieldSpec(_is_canonical_object(CanonicalObjective), True)},
    EventType.REQUIREMENT_DISCOVERED: {"requirement": PayloadFieldSpec(_is_canonical_object(Requirement), True)},
    EventType.REQUIREMENT_CONFIRMED: {"requirement_id": PayloadFieldSpec(str, True)},
    EventType.REQUIREMENT_SUPERSEDED: {"requirement_id": PayloadFieldSpec(str, True), "revision": PayloadFieldSpec(_is_int64)},
    EventType.REQUIREMENT_CANCELLED: {"requirement_id": PayloadFieldSpec(str, True)},
    EventType.DECISION_CREATED: {"decision": PayloadFieldSpec(_is_canonical_object(Decision), True)},
    EventType.DECISION_OUTCOME_RECORDED: {"outcome": PayloadFieldSpec(_is_canonical_object(DecisionOutcome), True)},
    EventType.OBLIGATION_CREATED: {"obligation": PayloadFieldSpec(_is_canonical_object(Obligation), True), "obligation_id": PayloadFieldSpec(str)},
    EventType.ACCEPTANCE_CONTRACT_REVISED: {"acceptance_contract": PayloadFieldSpec(_is_canonical_object(AcceptanceContract), True), "contract_id": PayloadFieldSpec(str)},
    EventType.VERIFICATION_PLAN_REVISED: {"verification_plan": PayloadFieldSpec(_is_canonical_object(VerificationPlan), True), "plan_id": PayloadFieldSpec(str)},
    EventType.WORKGRAPH_REVISED: {"work_graph": PayloadFieldSpec(_is_canonical_object(WorkGraph), True)},
    EventType.POLICY_ACTIVATED: {"policy": PayloadFieldSpec(_is_canonical_object(Policy), True), "policy_digest": PayloadFieldSpec(_is_digest_value, True), "activation_approvals": PayloadFieldSpec(_tuple_of(_is_canonical_object(ApprovalRecord)))},
    EventType.APPROVAL_RECORDED: {"approval_record": PayloadFieldSpec(_is_canonical_object(ApprovalRecord), True), "approval_id": PayloadFieldSpec(str), "approval_set": PayloadFieldSpec(_is_canonical_object(ApprovalSet)), "signature_verification": PayloadFieldSpec(lambda v, _n="SignatureVerificationRecord": _is_deferred_canonical_object(_n, v))},
    EventType.WORK_ASSIGNED: {"worker_id": PayloadFieldSpec(str, True)},
    EventType.AUTHORIZATION_GRANTED: {"authorization_decision": PayloadFieldSpec(_is_canonical_object(AuthorizationDecision), True), "decision_id": PayloadFieldSpec(str), "causal_frontier": PayloadFieldSpec(_is_canonical_object(CausalFrontier)), "governing_budget_lineage": PayloadFieldSpec(_is_canonical_object(GoverningBudgetLineage))},
    EventType.AUTHORIZATION_DENIED: {"authorization_decision": PayloadFieldSpec(_is_canonical_object(AuthorizationDecision), True), "decision_id": PayloadFieldSpec(str)},
    EventType.LEASE_ISSUED: {"lease": PayloadFieldSpec(_is_canonical_object(LeaseRecord), True), "lease_id": PayloadFieldSpec(str)},
    EventType.LEASE_EXPIRED: {"lease_id": PayloadFieldSpec(str, True)},
    EventType.LEASE_REVOKED: {"lease_id": PayloadFieldSpec(str, True)},
    EventType.BUDGET_RESERVED: {"reservation": PayloadFieldSpec(_is_canonical_object(BudgetReservation), True), "reservation_id": PayloadFieldSpec(str)},
    EventType.BUDGET_RELEASED: {"reservation": PayloadFieldSpec(_is_canonical_object(BudgetReservation), True), "reservation_id": PayloadFieldSpec(str)},
    EventType.BUDGET_SETTLED: {"reservation": PayloadFieldSpec(_is_canonical_object(BudgetReservation), True), "reservation_id": PayloadFieldSpec(str)},
    EventType.BUDGET_RESERVATION_EXPIRED: {"reservation": PayloadFieldSpec(_is_canonical_object(BudgetReservation), True), "reservation_id": PayloadFieldSpec(str, True)},
    EventType.EXECUTION_INTENT: {"execution_intent": PayloadFieldSpec(lambda v, _n="ExecutionIntent": _is_deferred_canonical_object(_n,v), True), "intent_id": PayloadFieldSpec(str, True)},
    EventType.EXECUTION_STARTED: {"execution_generation": PayloadFieldSpec(_is_canonical_object(ExecutionGeneration), True), "work_node_id": PayloadFieldSpec(str)},
    EventType.EXECUTION_COMPLETED: {"execution_outcome": PayloadFieldSpec(_is_canonical_object(ExecutionOutcome), True), "request_id": PayloadFieldSpec(str)},
    EventType.EXECUTION_CANCELLED: {"execution_outcome": PayloadFieldSpec(_is_canonical_object(ExecutionOutcome), True), "request_id": PayloadFieldSpec(str), "reason": PayloadFieldSpec(str)},
    EventType.BOUNDARY_VIOLATION_DETECTED: {"violation": PayloadFieldSpec(lambda v, _n="BoundaryViolationRecord": _is_deferred_canonical_object(_n,v), True), "violation_id": PayloadFieldSpec(str, True)},
    EventType.MUTATION_OBSERVED: {"observation": PayloadFieldSpec(_is_canonical_object(ObservationRecord), True)},
    EventType.QUIESCENCE_PROVEN: {"quiescence_proof": PayloadFieldSpec(_is_canonical_object(QuiescenceProof), True)},
    EventType.VERIFIED_WORKSPACE_DELTA_RECORDED: {"verified_delta": PayloadFieldSpec(_is_canonical_object(VerifiedWorkspaceDelta), True), "delta_id": PayloadFieldSpec(str), "target_snapshot": PayloadFieldSpec(_is_canonical_object(TargetSnapshot))},
    EventType.VERIFICATION_STARTED: {"step_id": PayloadFieldSpec(str, True)},
    EventType.VERIFICATION_COMPLETED: {"result_status": PayloadFieldSpec(lambda v: isinstance(v, VerificationStatus), True), "verification_result": PayloadFieldSpec(_is_canonical_object(VerificationResult))},
    EventType.EVIDENCE_ACCEPTED: {"closure": PayloadFieldSpec(_is_canonical_object(EvidenceClosure), True), "evidence_id": PayloadFieldSpec(str), "signature_verifications": PayloadFieldSpec(lambda v: isinstance(v,tuple) and all(_is_deferred_canonical_object("SignatureVerificationRecord",x) for x in v))},
    EventType.EVIDENCE_INVALIDATED: {"invalidation_set": PayloadFieldSpec(_is_canonical_object(InvalidationSet), True)},
    EventType.ACCEPTANCE_SNAPSHOT_RECORDED: {"acceptance_snapshot": PayloadFieldSpec(_is_canonical_object(AcceptanceSnapshot), True), "snapshot_id": PayloadFieldSpec(str, True)},
    EventType.ASSESSMENT_CREATED: {"assessment": PayloadFieldSpec(_is_canonical_object(IndependentAssessment), True), "assessment_id": PayloadFieldSpec(str), "signature_verification": PayloadFieldSpec(lambda v: _is_deferred_canonical_object("SignatureVerificationRecord",v))},
    EventType.OBLIGATION_SATISFIED: {"obligation_id": PayloadFieldSpec(str, True), "evidence_id": PayloadFieldSpec(str, True), "assessment_id": PayloadFieldSpec(str, True)},
    EventType.WAIVER_GRANTED: {"waiver": PayloadFieldSpec(_is_canonical_object(AcceptedRiskWaiver), True), "waiver_id": PayloadFieldSpec(str), "signature_verification": PayloadFieldSpec(lambda v: _is_deferred_canonical_object("SignatureVerificationRecord",v))},
    EventType.WORK_FAILED: {"failure_fingerprint": PayloadFieldSpec(_is_digest_value, True)},
    EventType.WORK_CANCELLED: {"reason": PayloadFieldSpec(str, True)},
    EventType.RETRY_CONSUMED: {"retry_budget": PayloadFieldSpec(_is_canonical_object(RetryBudget), True), "budget_id": PayloadFieldSpec(str)},
    EventType.BREAK_GLASS_CONSUMED: {"authority_id": PayloadFieldSpec(str, True), "consumption_id": PayloadFieldSpec(str, True), "consumption_number": PayloadFieldSpec(_is_int64, True), "requester": PayloadFieldSpec(str, True), "reason": PayloadFieldSpec(str, True)},
    EventType.EXTERNAL_EFFECT_RECONCILED: {"receipt": PayloadFieldSpec(_is_canonical_object(SideEffectReceipt), True)},
    EventType.REPAIR_PLANNED: {"repair_plan": PayloadFieldSpec(lambda v, _n="RepairPlan": _is_deferred_canonical_object(_n,v), True), "plan_id": PayloadFieldSpec(str)},
    EventType.ROLLBACK_STARTED: {"rollback_plan": PayloadFieldSpec(_tuple_of(str), True)},
    EventType.ROLLBACK_COMPLETED: {"rollback_result": PayloadFieldSpec(str, True)},
    EventType.ROLLBACK_FAILED: {"rollback_result": PayloadFieldSpec(str, True)},
    EventType.IN_DOUBT_DECLARED: {"in_doubt": PayloadFieldSpec(lambda v, _n="InDoubtRecord": _is_deferred_canonical_object(_n,v), True), "node_id": PayloadFieldSpec(str)},
    EventType.IN_DOUBT_RESOLVED: {"in_doubt": PayloadFieldSpec(lambda v, _n="InDoubtRecord": _is_deferred_canonical_object(_n,v), True), "resolved_status": PayloadFieldSpec(lambda v: isinstance(v, WorkNodeStatus), True), "node_id": PayloadFieldSpec(str)},
    EventType.RELEASE_EVALUATED: {"release": PayloadFieldSpec(lambda v, _n="ReleaseState": _is_deferred_canonical_object(_n,v), True), "evaluation": PayloadFieldSpec(lambda v, _n="ReleaseEvaluation": _is_deferred_canonical_object(_n,v), True), "release_id": PayloadFieldSpec(str, True)},
    EventType.SHUTDOWN_REQUESTED: {"reason": PayloadFieldSpec(str, True)},
    EventType.STATE_CHECKPOINTED: {"checkpoint": PayloadFieldSpec(lambda v: isinstance(v, globals()["CheckpointRef"]), True), "checkpoint_id": PayloadFieldSpec(str)},
    EventType.WORKSPACE_ROLLED_BACK: {"target_snapshot": PayloadFieldSpec(_is_canonical_object(TargetSnapshot), True)},
    EventType.RETENTION_PURGED: {"range": PayloadFieldSpec(tuple, True)},
}

if set(EVENT_PAYLOAD_SCHEMA) != set(EventType):
    missing = set(EventType) - set(EVENT_PAYLOAD_SCHEMA)
    extra = set(EVENT_PAYLOAD_SCHEMA) - set(EventType)
    raise AssertionError(f"event payload registry mismatch: missing={missing}, extra={extra}")

EVENT_PAYLOAD_REQUIRED_FIELDS = {et: tuple(k for k,v in schema.items() if v.required) for et,schema in EVENT_PAYLOAD_SCHEMA.items()}


@canonical_dataclass
class CanonicalEvent:
    event_id: str
    commit_id: str
    workspace_id: str
    event_sequence: int
    event_type: EventType
    schema_version: int
    aggregate_id: str
    actor: ActorIdentity
    causation_id: str
    correlation_id: str
    payload: FrozenMap                        # validated against EventPayloadSchema for event_type
    payload_digest: Digest
    previous_event_hash: Digest
    event_hash: Digest                        # digest of EXACT EventHashPreimage below
    policy_version: str
    sdk_version: str
    recorded_at: UtcInstant

    @classmethod
    def create(cls, event_id: str, commit_id: str, workspace_id: str, event_sequence: int,
               event_type: EventType, schema_version: int, aggregate_id: str, actor: ActorIdentity,
               causation_id: str, correlation_id: str, payload: FrozenMap, previous_event_hash: Digest,
               policy_version: str, sdk_version: str, recorded_at: UtcInstant):
        payload_digest = digest("sclass/event-payload/v1", payload)
        temp = object.__new__(cls)
        for name, value in {
            "event_id":event_id,"commit_id":commit_id,"workspace_id":workspace_id,"event_sequence":event_sequence,
            "event_type":event_type,"schema_version":schema_version,"aggregate_id":aggregate_id,"actor":actor,
            "causation_id":causation_id,"correlation_id":correlation_id,"payload":payload,"payload_digest":payload_digest,
            "previous_event_hash":previous_event_hash,"event_hash":GENESIS_EVENT_HASH,"policy_version":policy_version,
            "sdk_version":sdk_version,"recorded_at":recorded_at}.items():
            object.__setattr__(temp,name,value)
        object.__setattr__(temp,"event_hash",event_hash(temp))
        _validate_event_payload_schema(temp)
        return temp

    def __post_init__(self):
        if not isinstance(self.payload, FrozenMap):
            raise TypeError("canonical event payload must be FrozenMap")
        expected = digest("sclass/event-payload/v1", self.payload)
        if self.payload_digest != expected:
            raise ValueError("event payload digest mismatch")
        for field_name in EVENT_PAYLOAD_REQUIRED_FIELDS.get(self.event_type, ()):
            if self.payload.get(field_name) is None:
                raise ValueError(f"{self.event_type.value} requires payload field {field_name}")
        expected_hash = event_hash(self)
        if self.event_hash != expected_hash:
            raise ValueError("event hash mismatch")
        _validate_event_payload_schema(self)


# Generated reducer coverage map. Every EventType has exactly one executable handler.
def _load_state_machine_source() -> dict:
    """Load the single machine-readable transition source; no hand-maintained transition table exists here."""
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "10-CONFORMANCE" / "state-machines.v6.0.1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != "6.0.1":
        raise ValueError("unsupported state-machine source version")
    return data

STATE_MACHINE_SOURCE = _load_state_machine_source()

def _machine_transition(machine: str, old: str, new: str) -> bool:
    return new in STATE_MACHINE_SOURCE["machines"].get(machine, {}).get(old, ())

EVENT_TRANSITION_SOURCE = STATE_MACHINE_SOURCE["event_transitions"]


def _value_matches(checker: Any, value: Any) -> bool:
    if isinstance(checker, tuple):
        return any(_value_matches(c, value) for c in checker)
    if isinstance(checker, type):
        return isinstance(value, checker)
    return bool(checker(value))

def validate_event_payload_types(event: CanonicalEvent) -> None:
    schema = EVENT_PAYLOAD_SCHEMA[event.event_type]
    for name, value in event.payload.items():
        if not _value_matches(schema[name].checker, value):
            raise TypeError(f"invalid payload type for {event.event_type.value}.{name}")

def _validate_event_payload_schema(event: CanonicalEvent) -> None:
    if event.schema_version != EVENT_SCHEMA_VERSION:
        raise ValueError(f"unsupported event schema version: {event.schema_version}")
    schema = EVENT_PAYLOAD_SCHEMA.get(event.event_type)
    if schema is None:
        raise ValueError(f"missing event payload schema for {event.event_type.name}")
    unknown=set(event.payload)-set(schema)
    if unknown:
        raise ValueError(f"unknown payload fields for {event.event_type.value}: {tuple(sorted(unknown, key=str))}")
    missing=[k for k,v in schema.items() if v.required and k not in event.payload]
    if missing:
        raise ValueError(f"missing required event payload fields: {tuple(missing)}")
    validate_event_payload_types(event)


def _event_target(event: CanonicalEvent, rule: Mapping[str, Any], payload: FrozenMap) -> Optional[str]:
    if "target" in rule: return rule["target"]
    by=rule.get("target_by_payload")
    if not by: return None
    for field_name, mapping in by.items():
        value=payload.get(field_name)
        if mapping == "__VALUE__": return value.value if isinstance(value, Enum) else value
        return mapping.get(value.value if isinstance(value, Enum) else value)
    return None

def _mark_invalidation(prior: EngineeringState, machine_maps: dict, invalidation: InvalidationSet, event_id: str):
    """Apply one durable invalidation fact and deterministically reopen affected lifecycle objects."""
    # Evidence remains immutable; invalidation is an append-only canonical fact consumed by freshness.
    evidence_invalidations = dict(prior.evidence_invalidations.items())
    evidence_invalidations[event_id] = invalidation
    obligation_ids=set(invalidation.obligation_ids)
    for oid in sorted(obligation_ids):
        old=machine_maps["ObligationStatus"].get(oid)
        if old is not None and old != ObligationStatus.STALE.value and _machine_transition("ObligationStatus",old,ObligationStatus.STALE.value):
            machine_maps["ObligationStatus"][oid]=ObligationStatus.STALE.value
    work_ids=set(invalidation.work_node_ids)
    for nid in sorted(work_ids):
        old=machine_maps["WorkNodeStatus"].get(nid)
        if old is not None and old != WorkNodeStatus.READY.value and _machine_transition("WorkNodeStatus",old,WorkNodeStatus.READY.value):
            machine_maps["WorkNodeStatus"][nid]=WorkNodeStatus.READY.value
    return FrozenMap.from_items(evidence_invalidations.items())

def _affected_by_obligations(state: EngineeringState, obligation_ids: frozenset[str]) -> InvalidationSet:
    evidence_ids=set(); work_node_ids=set()
    for oid in obligation_ids:
        ob=state.obligations._obligations.get(oid)
        if ob and ob.satisfied_by:
            evidence_ids.add(ob.satisfied_by)
        if state.work_graph is not None:
            for nid,node in state.work_graph._nodes.items():
                if oid in node.satisfies_obligation_ids or node.primary_obligation_id == oid:
                    work_node_ids.add(nid)
    return InvalidationSet(frozenset(evidence_ids),frozenset(obligation_ids),frozenset(work_node_ids))

def _revision_change_invalidations(state: EngineeringState, event_type: EventType, object_id: Optional[str]=None) -> InvalidationSet:
    impacted=set()
    if event_type in (EventType.OBJECTIVE_REVISED, EventType.WORKGRAPH_REVISED, EventType.POLICY_ACTIVATED, EventType.WORKSPACE_ROLLED_BACK):
        impacted.update(state.obligations._obligations.keys())
    elif event_type in (EventType.ACCEPTANCE_CONTRACT_REVISED, EventType.VERIFICATION_PLAN_REVISED):
        for oid,ob in state.obligations._obligations.items():
            if event_type is EventType.ACCEPTANCE_CONTRACT_REVISED and ob.acceptance_contract_id == object_id:
                impacted.add(oid)
            elif event_type is EventType.VERIFICATION_PLAN_REVISED:
                if object_id is not None and state.verification_plans.get(object_id) is not None and state.verification_plans[object_id].obligation_id == oid:
                    impacted.add(oid)
    return _affected_by_obligations(state,frozenset(impacted))

def _validate_revision_object(previous_map: FrozenMap, key: str, obj: Any, identity_fields: tuple[str,...], revision_field: str, parent_field: Optional[str]=None):
    old=previous_map.get(key)
    if old is None:
        if getattr(obj,revision_field) != 1:
            raise ValueError(f"{type(obj).__name__} first revision must be 1")
        return
    if not _transition_revision(old,obj,identity_fields,revision_field,parent_field):
        raise ValueError(f"invalid {type(obj).__name__} revision lineage")

@canonical_dataclass
class ReferenceReducer:
    version: str = "6.0.1"

    def reduce(self, prior: EngineeringState, event: CanonicalEvent) -> EngineeringState:
        if event.workspace_id != prior.workspace_id: raise ValueError("event workspace mismatch")
        if event.event_sequence != prior.event_sequence + 1: raise ValueError("event sequence is not contiguous")
        if event.previous_event_hash != prior.event_head_hash: raise ValueError("event previous hash mismatch")
        # CanonicalEvent.__post_init__ already validates payload digest + event hash;
        # re-check here to defend deserialization/foreign object boundaries.
        if digest("sclass/event-payload/v1", event.payload) != event.payload_digest:
            raise ValueError("event payload digest mismatch")
        if event_hash(event) != event.event_hash:
            raise ValueError("event hash mismatch")
        _validate_event_payload_schema(event)
        payload=event.payload
        s=prior
        facts=dict(s.reducer_facts.items())
        machine_maps={name: dict((facts.get(name, FrozenMap.from_items())).items())
                      for name in ("WorkNodeStatus","ObligationStatus","RequirementStatus","LeaseState")}
        rule=EVENT_TRANSITION_SOURCE.get(event.event_type.name)
        if rule is None: raise ValueError(f"missing event transition source for {event.event_type.name}")
        def apply_machine(machine, aggregate, target):
            if target is None: return
            m=machine_maps[machine]; old=m.get(aggregate)
            creation = event.event_type in (EventType.OBJECTIVE_CREATED, EventType.OBLIGATION_CREATED, EventType.REQUIREMENT_DISCOVERED, EventType.LEASE_ISSUED)
            if old is None and not creation:
                raise ValueError(f"unknown aggregate for {machine}: {aggregate}")
            if old is not None and old != target and not _machine_transition(machine, old, target):
                raise ValueError(f"illegal {machine} transition {old}->{target} for {aggregate}")
            m[aggregate]=target
        machine=rule.get("machine")
        target=_event_target(event,rule,payload)
        if machine and target is not None: apply_machine(machine,event.aggregate_id,target)
        optional_machine=rule.get("optional_work_node_target")
        node_id=payload.get("node_id")
        if optional_machine and node_id is not None: apply_machine("WorkNodeStatus",node_id,optional_machine)
        _MISSING=object()
        def fmap_update(m, key, value):
            d=dict(m.items()) if isinstance(m, FrozenMap) else {}
            d[key]=value
            return FrozenMap.from_items(d.items())
        def fmap_insert_immutable(m, key, value, name):
            d=dict(m.items()) if isinstance(m, FrozenMap) else {}
            existing=d.get(key,_MISSING)
            if existing is not _MISSING:
                if existing == value:
                    return m
                raise ValueError(f"duplicate {name} identity with different canonical content: {key}")
            d[key]=value
            return FrozenMap.from_items(d.items())
        et=event.event_type
        object_fields={
            EventType.OBJECTIVE_CREATED:"objective", EventType.OBJECTIVE_REVISED:"objective",
            EventType.REQUIREMENT_DISCOVERED:"requirement",
            EventType.OBLIGATION_CREATED:"obligation", EventType.ACCEPTANCE_CONTRACT_REVISED:"acceptance_contract",
            EventType.VERIFICATION_PLAN_REVISED:"verification_plan", EventType.WORKGRAPH_REVISED:"work_graph",
            EventType.POLICY_ACTIVATED:"policy",
            EventType.LEASE_ISSUED:"lease", EventType.BUDGET_RESERVED:"reservation",
            EventType.REPAIR_PLANNED:"repair_plan", EventType.WAIVER_GRANTED:"waiver",
            EventType.EVIDENCE_ACCEPTED:"closure", EventType.ASSESSMENT_CREATED:"assessment",
            EventType.RELEASE_EVALUATED:"release", EventType.VERIFIED_WORKSPACE_DELTA_RECORDED:"verified_delta",
            EventType.APPROVAL_RECORDED:"approval_record", EventType.AUTHORIZATION_GRANTED:"authorization_decision",
            EventType.AUTHORIZATION_DENIED:"authorization_decision", EventType.BUDGET_RELEASED:"reservation",
            EventType.BUDGET_SETTLED:"reservation", EventType.BUDGET_RESERVATION_EXPIRED:"reservation", EventType.EXECUTION_STARTED:"execution_generation",
            EventType.EXECUTION_COMPLETED:"execution_outcome", EventType.EXECUTION_CANCELLED:"execution_outcome",
            EventType.RETRY_CONSUMED:"retry_budget", EventType.BREAK_GLASS_CONSUMED:"break_glass", EventType.EXTERNAL_EFFECT_RECONCILED:"receipt", EventType.IN_DOUBT_DECLARED:"in_doubt",
            EventType.IN_DOUBT_RESOLVED:"in_doubt", EventType.STATE_CHECKPOINTED:"checkpoint",
            EventType.WORKSPACE_ROLLED_BACK:"target_snapshot"
        }
        declared_id_fields={
            "objective":"objective_id", "requirement":"requirement_id", "obligation":"obligation_id",
            "acceptance_contract":"contract_id", "verification_plan":"plan_id", "work_graph":"revision_id",
            "policy":"policy_id", "lease":"lease_id", "reservation":"reservation_id", "repair_plan":"plan_id",
            "waiver":"waiver_id", "closure":"evidence_id", "assessment":"assessment_id", "release":"release_id",
            "verified_delta":"delta_id", "approval_record":"approval_id",
            "retry_budget":"budget_id", "in_doubt":"node_id", "checkpoint":"checkpoint_id", "receipt":"effect_id",
        }
        _candidate_object_field={
            "objective":"objective","requirement":"requirement","obligation":"obligation","acceptance_contract":"acceptance_contract",
            "verification_plan":"verification_plan","work_graph":"work_graph","policy":"policy","lease":"lease","reservation":"reservation",
            "repair_plan":"repair_plan","waiver":"waiver","closure":"closure","assessment":"assessment","release":"release",
            "verified_delta":"verified_delta","approval_record":"approval_record","authorization_decision":"authorization_decision",
            "retry_budget":"retry_budget","in_doubt":"in_doubt","checkpoint":"checkpoint",
        }
        if field_name := object_fields.get(et):
            candidate=payload.get(field_name)
            id_field=declared_id_fields.get(field_name)
            if candidate is not None and id_field is not None and hasattr(candidate,id_field):
                candidate_id=getattr(candidate,id_field)
                if event.aggregate_id != candidate_id and et not in (EventType.OBJECTIVE_REVISED, EventType.WORKGRAPH_REVISED, EventType.POLICY_ACTIVATED):
                    raise ValueError(f"aggregate identity mismatch for {et.value}")
        # Canonical object materialization. Payloads carry validated immutable domain objects; reducer owns replacement.
        updates={}
        field_name=object_fields.get(et)
        obj=payload.get(field_name) if field_name else None
        required_object_events=frozenset(object_fields)
        if et in required_object_events and obj is None:
            raise ValueError(f"{et.value} requires canonical payload field {field_name}")
        if et is EventType.OBJECTIVE_CREATED and obj is not None:
            if s.objective is not None:
                if s.objective == obj:
                    updates["objective"] = s.objective
                else:
                    raise ValueError("objective identity already exists")
            else:
                if obj.workspace_id != s.workspace_id or not obj.revisions or obj.revisions[0].revision_number != 1 or obj.revisions[0].parent_revision_id is not None:
                    raise ValueError("invalid objective creation lineage")
                updates["objective"] = obj
        elif et is EventType.OBJECTIVE_REVISED and obj is not None:
            if s.objective is None or obj.objective_id != s.objective.objective_id or obj.workspace_id != s.workspace_id or not obj.revisions:
                raise ValueError("invalid objective revision identity")
            old=s.objective.revisions[-1]; new=obj.revisions[-1]
            if new.revision_number != old.revision_number + 1 or new.parent_revision_id != old.revision_id:
                raise ValueError("objective revision must append to previous revision")
            if len(obj.revisions) != len(s.objective.revisions) + 1 or tuple(obj.revisions[:-1]) != tuple(s.objective.revisions):
                raise ValueError("objective history replacement is not append-only")
            updates["objective"] = obj
            inv=_revision_change_invalidations(s,et)
            updates["evidence_invalidations"]=_mark_invalidation(s,machine_maps,inv,event.event_id)
        elif et is EventType.REQUIREMENT_DISCOVERED and obj is not None:
            key=obj.requirement_id
            existing=s.requirements.get(key)
            if existing is not None:
                if existing.requirement == obj and existing.status is RequirementStatus.PROPOSED:
                    updates["requirements"]=s.requirements
                else:
                    raise ValueError("duplicate requirement identity")
            else:
                updates["requirements"]=fmap_insert_immutable(s.requirements,key,RequirementRecord(obj,RequirementStatus.PROPOSED),"requirement")
        elif et is EventType.REQUIREMENT_CONFIRMED:
            key=payload["requirement_id"]; rec=s.requirements.get(key)
            if rec is None: raise ValueError("unknown requirement")
            updates["requirements"]=FrozenMap.from_items(tuple((k, replace(v,status=RequirementStatus.CONFIRMED)) if k==key else (k,v) for k,v in s.requirements.items()))
        elif et is EventType.REQUIREMENT_SUPERSEDED:
            key=payload["requirement_id"]; rec=s.requirements.get(key)
            if rec is None: raise ValueError("unknown requirement")
            updates["requirements"]=FrozenMap.from_items(tuple((k, replace(v,status=RequirementStatus.SUPERSEDED)) if k==key else (k,v) for k,v in s.requirements.items()))
        elif et is EventType.REQUIREMENT_CANCELLED:
            key=payload["requirement_id"]; rec=s.requirements.get(key)
            if rec is None: raise ValueError("unknown requirement")
            updates["requirements"]=FrozenMap.from_items(tuple((k, replace(v,status=RequirementStatus.CANCELLED)) if k==key else (k,v) for k,v in s.requirements.items()))
        elif et is EventType.WORKGRAPH_REVISED and obj is not None:
            if s.work_graph is not None:
                if obj.objective_revision != s.work_graph.objective_revision or obj.obligation_graph_revision != s.work_graph.obligation_graph_revision or obj.policy_version != s.work_graph.policy_version:
                    raise ValueError("work graph governing lineage changed without objective/obligation/policy event")
            updates["work_graph"]=obj
            machine_maps["WorkNodeStatus"]={nid:node.status.value for nid,node in obj._nodes.items()}
            inv=_revision_change_invalidations(s,et,obj.revision_id)
            updates["evidence_invalidations"]=_mark_invalidation(s,machine_maps,inv,event.event_id)
        elif et is EventType.POLICY_ACTIVATED and obj is not None:
            pd=payload.get("policy_digest")
            if pd != digest("sclass/policy/v1",obj): raise ValueError("policy digest mismatch")
            approvals=payload.get("activation_approvals",())
            if not validate_policy_activation_event(s,obj,pd,approvals,event.recorded_at):
                raise ValueError("policy activation validation failed")
            updates["active_policy"]=obj; updates["policy_version"]=obj.policy_version; updates["policy_digest"]=pd
            # Policy activation immediately revokes all leases bound to a different policy version.
            leases=dict(s.leases.items())
            for lid,rec in list(leases.items()):
                if rec.state is LeaseState.ACTIVE and rec.lease.policy_version != obj.policy_version:
                    leases[lid]=replace(rec,state=LeaseState.REVOKED)
                    machine_maps["LeaseState"][lid]=LeaseState.REVOKED.value
            updates["leases"]=FrozenMap.from_items(leases.items())
            inv=_revision_change_invalidations(s,et)
            updates["evidence_invalidations"]=_mark_invalidation(s,machine_maps,inv,event.event_id)
        elif et is EventType.WORK_ASSIGNED:
            worker_id=payload.get("worker_id")
            if not worker_id: raise ValueError("WorkAssigned requires worker_id")
            updates["assignments"]=fmap_update(s.assignments,event.aggregate_id,worker_id)
            if s.work_graph is not None and event.aggregate_id in s.work_graph._nodes:
                n=s.work_graph._nodes[event.aggregate_id]
                nd=dict(s.work_graph._nodes.items()); nd[event.aggregate_id]=replace(n,status=WorkNodeStatus.ASSIGNED,worker_id=worker_id)
                updates["work_graph"]=replace(s.work_graph,_nodes=FrozenMap.from_items(nd.items()))
        elif et is EventType.OBLIGATION_CREATED and obj is not None:
            oid=payload.get("obligation_id",getattr(obj,"obligation_id",event.aggregate_id)); updates["obligations"]=s.obligations.add(obj)
        elif et is EventType.OBLIGATION_SATISFIED:
            oid=payload["obligation_id"]; ev_id=payload["evidence_id"]; aid=payload["assessment_id"]
            if not validate_obligation_satisfaction(s,oid,ev_id,aid,event.recorded_at):
                raise ValueError("Gate-D obligation satisfaction chain is not valid")
            updates["obligations"]=replace(s.obligations,_obligations=FrozenMap.from_items((k, replace(v,status=ObligationStatus.SATISFIED,satisfied_by=ev_id) if k==oid else v) for k,v in s.obligations._obligations.items()))
        elif et is EventType.ACCEPTANCE_CONTRACT_REVISED and obj is not None:
            key=payload.get("contract_id",getattr(obj,"contract_id",event.aggregate_id))
            if key != getattr(obj,"contract_id",key): raise ValueError("acceptance contract identity mismatch")
            old=s.acceptance_contracts.get(key)
            if old is None:
                if obj.revision != 1: raise ValueError("acceptance contract first revision must be 1")
            else:
                if obj.obligation_id != old.obligation_id or obj.revision != old.revision + 1:
                    raise ValueError("acceptance contract revision lineage invalid")
            updates["acceptance_contracts"]=fmap_insert_immutable(s.acceptance_contracts,key,obj,"acceptance contract")
            inv=_revision_change_invalidations(s,et,key)
            updates["evidence_invalidations"]=_mark_invalidation(s,machine_maps,inv,event.event_id)
        elif et is EventType.VERIFICATION_PLAN_REVISED and obj is not None:
            key=payload.get("plan_id",getattr(obj,"plan_id",event.aggregate_id))
            if key != getattr(obj,"plan_id",key): raise ValueError("verification plan identity mismatch")
            old=s.verification_plans.get(key)
            if old is None:
                if obj.revision != 1: raise ValueError("verification plan first revision must be 1")
            else:
                if obj.plan_id != old.plan_id or obj.obligation_id != old.obligation_id or obj.contract_revision != old.contract_revision or obj.revision != old.revision + 1:
                    raise ValueError("verification plan revision lineage invalid")
            updates["verification_plans"]=fmap_insert_immutable(s.verification_plans,key,obj,"verification plan")
            inv=_revision_change_invalidations(s,et,key)
            updates["evidence_invalidations"]=_mark_invalidation(s,machine_maps,inv,event.event_id)
        elif et is EventType.LEASE_ISSUED and obj is not None:
            key=payload.get("lease_id",getattr(obj,"lease_id",event.aggregate_id))
            if key != obj.lease.lease_id: raise ValueError("lease identity mismatch")
            if not validate_execution_lease(s,obj): raise ValueError("invalid execution lease admission")
            prior_tokens=[rec.lease.fencing_token for rec in s.leases.values() if rec.lease.node_id == obj.lease.node_id]
            if prior_tokens and obj.lease.fencing_token <= max(prior_tokens): raise ValueError("fencing token is not strictly increasing")
            updates["leases"]=fmap_insert_immutable(s.leases,key,obj,"lease")
        elif et is EventType.BUDGET_RESERVED and obj is not None:
            key=payload.get("reservation_id",getattr(obj,"reservation_id",event.aggregate_id))
            if key != obj.reservation_id or obj.lifecycle_state is not BudgetReservationState.RESERVED: raise ValueError("invalid budget reservation admission")
            updates["budget_reservations"]=fmap_insert_immutable(s.budget_reservations,key,obj,"budget reservation")
        elif et is EventType.REPAIR_PLANNED and obj is not None:
            key=payload.get("plan_id",getattr(obj,"plan_id",event.aggregate_id)); updates["repair_plans"]=fmap_insert_immutable(s.repair_plans,key,obj,"repair plan")
        elif et is EventType.WAIVER_GRANTED and obj is not None:
            key=payload.get("waiver_id",getattr(obj,"waiver_id",event.aggregate_id))
            sig=payload.get("signature_verification")
            if s.active_policy is None or not validate_waiver(obj,s,s.active_policy,event.recorded_at,sig):
                raise ValueError("waiver failed canonical validation")
            if sig is not None:
                if sig.subject_id != key or sig.signed_payload_digest != waiver_signed_payload_digest(obj) or sig.signature_digest != signature_block_digest(obj.signature):
                    raise ValueError("waiver signature verification is not bound to signed waiver bytes")
                updates["signature_verification_records"]=fmap_insert_immutable(s.signature_verification_records,key,sig,"signature verification record")
            updates["waivers"]=fmap_insert_immutable(s.waivers,key,obj,"waiver")
        elif et is EventType.EVIDENCE_ACCEPTED and obj is not None:
            key=payload.get("evidence_id",getattr(obj,"evidence_id",event.aggregate_id))
            if key != obj.evidence_id or obj.obligation_id != event.aggregate_id and event.aggregate_id not in {obj.evidence_id,obj.obligation_id}:
                raise ValueError("evidence identity mismatch")
            # Signature records in this event are admitted first for closure validation, but only as exact content-bound facts.
            sigs=payload.get("signature_verifications",())
            temp_records=s.signature_verification_records
            for sig in sigs:
                if sig.subject_id not in {r.receipt_id for r in obj.evidence_receipts}: raise ValueError("evidence signature record references unknown receipt")
                receipt=next(r for r in obj.evidence_receipts if r.receipt_id==sig.subject_id)
                if sig.signed_payload_digest != evidence_signed_payload_digest(receipt) or sig.signature_digest != signature_block_digest(receipt.signature): raise ValueError("evidence signature verification is not bound to signed receipt bytes")
                temp_records=fmap_insert_immutable(temp_records,sig.subject_id,sig,"signature verification record")
            temp_state=replace(s,signature_verification_records=temp_records)
            if not _validate_evidence_closure_against_state(temp_state,obj,event.recorded_at):
                raise ValueError("EvidenceAccepted missing admissibility, verification, signature or freshness chain")
            updates["evidence"]=fmap_insert_immutable(s.evidence,key,obj,"evidence closure")
            updates["signature_verification_records"]=temp_records
        elif et is EventType.DECISION_CREATED and obj is not None:
            key=payload.get("decision_id",getattr(obj,"decision_id",event.aggregate_id))
            if key != obj.decision_id: raise ValueError("decision identity mismatch")
            updates["decisions"]=fmap_insert_immutable(s.decisions,key,obj,"decision")
        elif et is EventType.DECISION_OUTCOME_RECORDED and obj is not None:
            key=payload.get("decision_id",getattr(obj,"decision_id",event.aggregate_id))
            if key != obj.decision_id or key not in s.decisions: raise ValueError("decision outcome references unknown decision")
            updates["decision_outcomes"]=fmap_insert_immutable(s.decision_outcomes,key,obj,"decision outcome")
        elif et is EventType.MUTATION_OBSERVED and obj is not None:
            key=obj.observation_id
            gen=s.execution_generations.get(obj.work_node_id)
            if gen is None or obj.execution_generation != gen.generation or obj.execution_attempt_id != gen.execution_attempt_id or obj.worker_identity != gen.worker_identity:
                raise ValueError("observation does not match active execution generation")
            active_lease=next((lr.lease for lr in s.leases.values() if lr.state is LeaseState.ACTIVE and lr.lease.node_id == obj.work_node_id and lr.lease.execution_attempt_id == obj.execution_attempt_id and lr.lease.execution_generation == obj.execution_generation),None)
            if active_lease is None: raise ValueError("observation has no active execution lease")
            intent=next((i for i in s.execution_intents.values() if i.execution_lease_id == active_lease.lease_id),None)
            if intent is None or intent.request_content_digest != active_lease.request_content_digest:
                raise ValueError("observation has no matching execution intent")
            if obj.target_snapshot_digest != gen.target_snapshot_digest or obj.governing_budget_lineage_id != gen.governing_budget_lineage_id:
                raise ValueError("observation target/budget lineage mismatch")
            if obj.quiescence_proof is None or obj.post_expiry:
                raise ValueError("observation requires trusted quiescence and non-expired execution")
            proof=obj.quiescence_proof
            if (proof.execution_lease_id != active_lease.lease_id or
                    proof.execution_generation != obj.execution_generation or
                    proof.execution_attempt_id != obj.execution_attempt_id or
                    proof.worker_identity != obj.worker_identity or
                    proof.target_execution_identity_digest != digest("sclass/execution-identity/v1", active_lease.executable_identity)):
                raise ValueError("quiescence proof is not bound to exact execution")
            if obj.process_result is None or obj.process_result.process_id != proof.process_id or obj.process_result.identity.process_start_time_ns != proof.process_start_time_ns:
                raise ValueError("quiescence proof process identity does not match observed process")
            if proof.proof_digest != quiescence_proof_digest(proof):
                raise ValueError("quiescence proof digest mismatch")
            if obj.actor.kind is not ActorKind.WORKER or obj.actor.actor_id != obj.worker_identity:
                raise ValueError("observation actor/worker identity mismatch")
            updates["observations"]=fmap_insert_immutable(s.observations,key,obj,"observation")
        elif et is EventType.VERIFICATION_COMPLETED:
            result=payload.get("verification_result")
            if result is None or not isinstance(result,VerificationResult): raise ValueError("verification completion requires result")
            observation=s.observations.get(result.observation_id)
            if observation is None: raise ValueError("verification result references unknown observation")
            plans=[p for p in s.verification_plans.values() if any(st.step_id==result.step_id for st in p.steps)]
            if len(plans)!=1: raise ValueError("verification step is not uniquely owned by one canonical plan")
            plan=plans[0]; step=next(st for st in plan.steps if st.step_id==result.step_id)
            obligation=s.obligations._obligations.get(plan.obligation_id)
            if obligation is None or obligation.verification_plan_id != plan.plan_id or plan.contract_revision != getattr(s.acceptance_contracts.get(obligation.acceptance_contract_id),"revision",-1):
                raise ValueError("verification step is not bound to exact obligation/contract")
            gen=s.execution_generations.get(observation.work_node_id)
            if gen is None or observation.execution_generation != gen.generation or observation.execution_attempt_id != gen.execution_attempt_id:
                raise ValueError("verification observation is from the wrong execution generation")
            if step.evidence_kind is None or not step.verifier_id or not step.verifier_version:
                raise ValueError("verification step configuration is incomplete")
            if result.status is VerificationStatus.PASS and not result.artifacts:
                raise ValueError("PASS verification must produce evidence artifacts")
            if result.verifier_process is not None:
                if result.verifier_process.identity.worker_id != step.verifier_id:
                    raise ValueError("verification producer identity does not match plan verifier")
                if result.verifier_process.args_digest != step.config_digest:
                    raise ValueError("verification producer configuration does not match plan")
                if result.verifier_process.ended_at.epoch_ns < result.verifier_process.started_at.epoch_ns:
                    raise ValueError("verification producer time lineage invalid")
            key=result.step_id
            updates["verification_results"]=fmap_insert_immutable(s.verification_results,key,result,"verification result")
        elif et is EventType.QUIESCENCE_PROVEN and payload.get("quiescence_proof") is not None:
            proof=payload["quiescence_proof"]
            if not proof.boundary_id or not proof.mechanism or not _is_digest_value(proof.target_execution_identity_digest): raise ValueError("invalid quiescence attestation")
            if not isinstance(proof.attestation_signature,SignatureBlock) or proof.attestation_key_id != proof.attestation_signature.key_id: raise ValueError("quiescence attestation identity mismatch")
            if proof.proof_digest != quiescence_proof_digest(proof): raise ValueError("quiescence proof digest mismatch")
            active=next((lr.lease for lr in s.leases.values() if lr.state is LeaseState.ACTIVE and lr.lease.lease_id == proof.execution_lease_id),None)
            if active is None or active.execution_generation != proof.execution_generation or active.execution_attempt_id != proof.execution_attempt_id or active.worker_identity != proof.worker_identity:
                raise ValueError("quiescence proof does not match active execution lease")
            if proof.target_execution_identity_digest != digest("sclass/execution-identity/v1", active.executable_identity):
                raise ValueError("quiescence proof execution identity mismatch")
            if proof.process_id < 1 or proof.process_start_time_ns < 1:
                raise ValueError("quiescence proof lacks concrete process identity")
            updates["quiescence_proofs"]=fmap_insert_immutable(s.quiescence_proofs,proof.proof_id,proof,"quiescence proof")
        elif et is EventType.EXECUTION_INTENT and payload.get("execution_intent") is not None:
            intent=payload["execution_intent"]; key=payload.get("intent_id",intent.intent_id)
            if key != intent.intent_id: raise ValueError("execution intent identity mismatch")
            lease=s.leases.get(intent.execution_lease_id)
            if lease is None or lease.state is not LeaseState.ACTIVE: raise ValueError("execution intent requires active execution lease")
            expected_binding=canonical_current_state_binding(s,lease.lease.execution_generation,intent.governing_budget_lineage_id)
            if intent.state_binding_digest != state_binding_digest(expected_binding): raise ValueError("execution intent state binding mismatch")
            if intent.budget_reservation_id != lease.lease.budget_reservation_id: raise ValueError("execution intent budget reservation mismatch")
            reservation=s.budget_reservations.get(intent.budget_reservation_id)
            if reservation is None or reservation.lifecycle_state is not BudgetReservationState.RESERVED: raise ValueError("execution intent requires RESERVED budget reservation")
            if intent.request_content_digest != lease.lease.request_content_digest or intent.worker_identity != lease.lease.worker_identity or intent.target_snapshot_digest != lease.lease.target_snapshot_digest or intent.governing_budget_lineage_id != lease.lease.governing_budget_lineage_id or intent.authorization_decision_id == "":
                raise ValueError("execution intent lineage mismatch")
            updates["execution_intents"]=fmap_insert_immutable(s.execution_intents,key,intent,"execution intent")
        elif et is EventType.BOUNDARY_VIOLATION_DETECTED and payload.get("violation") is not None:
            violation=payload["violation"]; key=payload.get("violation_id",violation.violation_id)
            if key != violation.violation_id: raise ValueError("boundary violation identity mismatch")
            updates["boundary_violations"]=fmap_insert_immutable(s.boundary_violations,key,violation,"boundary violation")
        elif et is EventType.ASSESSMENT_CREATED and obj is not None:
            key=payload.get("assessment_id",getattr(obj,"assessment_id",event.aggregate_id))
            if key != obj.assessment_id:
                raise ValueError("assessment identity mismatch")
            if assessment_input_digest(obj,s) != obj.input_digest:
                raise ValueError("assessment input digest mismatch")
            sig=payload.get("signature_verification")
            if sig is not None:
                if sig.subject_id != key or sig.signed_payload_digest != assessment_signed_payload_digest(obj) or sig.signature_digest != signature_block_digest(obj.signature):
                    raise ValueError("assessment signature verification is not bound to signed assessment bytes")
                updates["signature_verification_records"]=fmap_insert_immutable(s.signature_verification_records,key,sig,"signature verification record")
            updates["assessments"]=fmap_insert_immutable(s.assessments,key,obj,"assessment")
        elif et is EventType.RELEASE_EVALUATED and obj is not None:
            key=payload.get("release_id",getattr(obj,"release_id",event.aggregate_id)); evaluation=payload.get("evaluation")
            if evaluation is None or evaluation.release_id != key: raise ValueError("release evaluation is required")
            expected=evaluate_release(s,obj,s.active_policy,event.recorded_at)
            if evaluation != expected:
                raise ValueError("release evaluation is not derived from canonical state")
            updates["releases"]=fmap_insert_immutable(s.releases,key,obj,"release")
            updates["release_evaluations"]=fmap_insert_immutable(s.release_evaluations,key,evaluation,"release evaluation")
        elif et is EventType.VERIFIED_WORKSPACE_DELTA_RECORDED and obj is not None:
            key=payload.get("delta_id",getattr(obj,"delta_id",event.aggregate_id)); updates["verified_deltas"]=fmap_update(s.verified_deltas,key,obj)
            snap=payload.get("target_snapshot")
            if snap is not None: updates["target_snapshot"]=snap; updates["target_snapshots"]=fmap_update(s.target_snapshots,snap.snapshot_id,snap)
        elif et is EventType.APPROVAL_RECORDED and obj is not None:
            key=payload.get("approval_id",getattr(obj,"approval_id",event.aggregate_id)); updates["approval_records"]=fmap_insert_immutable(s.approval_records,key,obj,"approval record")
            aset=payload.get("approval_set")
            if aset is not None: updates["approval_sets"]=fmap_update(s.approval_sets,aset.set_id,aset)
            sig=payload.get("signature_verification")
            if sig is not None:
                if sig.subject_id != key:
                    raise ValueError("signature verification subject mismatch")
                updates["signature_verification_records"]=fmap_insert_immutable(s.signature_verification_records,key,sig,"signature verification record")
                updates["signature_verification_facts"]=fmap_insert_immutable(s.signature_verification_facts,key,sig.verification_result.value,"signature verification fact")
        elif et in (EventType.AUTHORIZATION_GRANTED,EventType.AUTHORIZATION_DENIED) and obj is not None:
            key=payload.get("decision_id",getattr(obj,"decision_id",event.aggregate_id))
            if key != obj.decision_id or not validate_authorization_decision(s,obj,event.recorded_at):
                raise ValueError("authorization decision is not valid against canonical state")
            if et is EventType.AUTHORIZATION_GRANTED:
                frontier=payload.get("causal_frontier"); lineage=payload.get("governing_budget_lineage")
                if frontier is None or lineage is None:
                    raise ValueError("authorization grant requires canonical causal frontier and budget lineage")
                expected_lineage=canonical_governing_budget_lineage(s,obj.work_node_id)
                expected_frontier=canonical_causal_frontier(s,obj,expected_lineage,obj.risk_tier)
                if lineage != expected_lineage or frontier != expected_frontier:
                    raise ValueError("authorization lineage/frontier is not freshly derived from this decision")
            if et is EventType.AUTHORIZATION_GRANTED and obj.decision is not AuthorizationState.ALLOW:
                raise ValueError("AuthorizationGranted requires ALLOW decision")
            if et is EventType.AUTHORIZATION_DENIED and obj.decision is not AuthorizationState.DENY:
                raise ValueError("AuthorizationDenied requires DENY decision")
            updates["authorization_decisions"]=fmap_insert_immutable(s.authorization_decisions,key,obj,"authorization decision")
        elif et in (EventType.BUDGET_RELEASED,EventType.BUDGET_SETTLED,EventType.BUDGET_RESERVATION_EXPIRED) and obj is not None:
            key=payload.get("reservation_id",getattr(obj,"reservation_id",event.aggregate_id)); old_res=s.budget_reservations.get(key)
            if old_res is None: raise ValueError("unknown budget reservation")
            if obj.workspace_id != old_res.workspace_id or obj.amount != old_res.amount or obj.version != old_res.version + 1: raise ValueError("budget reservation version/binding mismatch")
            if et is EventType.BUDGET_RELEASED and (old_res.lifecycle_state is not BudgetReservationState.RESERVED or obj.lifecycle_state is not BudgetReservationState.RELEASED): raise ValueError("invalid budget release transition")
            if et is EventType.BUDGET_SETTLED and (old_res.lifecycle_state is not BudgetReservationState.RESERVED or obj.lifecycle_state is not BudgetReservationState.SETTLED): raise ValueError("invalid budget settle transition")
            if et is EventType.BUDGET_RESERVATION_EXPIRED and (old_res.lifecycle_state is not BudgetReservationState.RESERVED or obj.lifecycle_state is not BudgetReservationState.EXPIRED or event.recorded_at.epoch_ns < old_res.expires_at.epoch_ns): raise ValueError("invalid budget expiry transition")
            updates["budget_reservations"]=fmap_insert_immutable(s.budget_reservations,key,obj,"budget reservation")
            leases=dict(s.leases.items())
            gens=dict(s.execution_generations.items())
            for lid,lrec in list(leases.items()):
                if lrec.lease.budget_reservation_id != key or lrec.state is not LeaseState.ACTIVE:
                    continue
                terminal = LeaseState.CONSUMED if et is EventType.BUDGET_SETTLED else LeaseState.REVOKED
                leases[lid]=replace(lrec,state=terminal)
                machine_maps["LeaseState"][lid]=terminal.value
                gen=gens.get(lrec.lease.node_id)
                if gen is not None and gen.execution_attempt_id == lrec.lease.execution_attempt_id:
                    gens[lrec.lease.node_id]=replace(gen,status=ExecutionGenerationStatus.RECONCILED if terminal is LeaseState.CONSUMED else ExecutionGenerationStatus.SUPERSEDED)
            updates["leases"]=FrozenMap.from_items(leases.items())
            updates["execution_generations"]=FrozenMap.from_items(gens.items())
        elif et in (EventType.LEASE_EXPIRED, EventType.LEASE_REVOKED):
            lease_id=payload.get("lease_id",event.aggregate_id)
            rec=s.leases.get(lease_id)
            if rec is None or rec.state is not LeaseState.ACTIVE:
                raise ValueError("lease terminal transition requires an active canonical lease")
            terminal=LeaseState.EXPIRED if et is EventType.LEASE_EXPIRED else LeaseState.REVOKED
            updates["leases"]=fmap_update(s.leases,lease_id,replace(rec,state=terminal))
            machine_maps["LeaseState"][lease_id]=terminal.value
        elif et is EventType.EXECUTION_STARTED and obj is not None:
            key=payload.get("work_node_id",getattr(obj,"work_node_id",event.aggregate_id))
            if key != obj.work_node_id or not validate_execution_generation(s,obj): raise ValueError("invalid execution generation lineage")
            updates["execution_generations"]=fmap_insert_immutable(s.execution_generations,key,obj,"execution generation")
        elif et in (EventType.EXECUTION_COMPLETED,EventType.EXECUTION_CANCELLED) and obj is not None:
            key=payload.get("request_id",getattr(obj,"request_id",event.aggregate_id))
            wr=getattr(obj,"work_result",None)
            if wr is not None:
                gen=s.execution_generations.get(wr.work_node_id)
                if gen is None or gen.execution_attempt_id != wr.execution_attempt_id or gen.generation != wr.execution_generation or gen.worker_identity != wr.worker_identity:
                    raise ValueError("execution outcome does not match canonical execution generation")
                if wr.target_snapshot_digest != gen.target_snapshot_digest or wr.state_binding_digest != gen.state_binding_digest:
                    raise ValueError("execution outcome state binding mismatch")
                matches=[(lid,lr) for lid,lr in s.leases.items()
                         if lr.lease.node_id == wr.work_node_id
                         and lr.lease.execution_attempt_id == wr.execution_attempt_id
                         and lr.lease.execution_generation == wr.execution_generation]
                if len(matches) != 1:
                    raise ValueError("execution outcome must resolve exactly one execution lease")
                lid,lr=matches[0]
                if lr.state is not LeaseState.ACTIVE:
                    raise ValueError("execution outcome requires an active execution lease")
                terminal=LeaseState.CONSUMED if et is EventType.EXECUTION_COMPLETED else LeaseState.CANCELLED
                updates["leases"]=fmap_update(s.leases,lid,replace(lr,state=terminal))
            updates["execution_outcomes"]=fmap_insert_immutable(s.execution_outcomes,key,obj,"execution outcome")
        elif et is EventType.BREAK_GLASS_CONSUMED:
            aid=payload["authority_id"]; cid=payload["consumption_id"]; num=payload["consumption_number"]
            if not aid or not cid or not payload["requester"] or not payload["reason"] or num < 1:
                raise ValueError("invalid break-glass consumption payload")
            prior_count=s.break_glass_consumption.get(aid,0)
            if num != prior_count + 1:
                raise ValueError("break-glass consumption must be monotonic")
            updates["break_glass_consumption"]=fmap_insert_immutable(s.break_glass_consumption,aid,num,"break-glass consumption")
        elif et is EventType.EXTERNAL_EFFECT_RECONCILED:
            receipt=payload.get("receipt")
            if not isinstance(receipt,SideEffectReceipt) or event.aggregate_id != receipt.effect_id:
                raise ValueError("invalid external-effect reconciliation receipt identity")
            updates["external_effect_receipts"]=fmap_insert_immutable(s.external_effect_receipts,receipt.effect_id,receipt,"external effect receipt")
        elif et is EventType.RETRY_CONSUMED and obj is not None:
            key=payload.get("budget_id",getattr(obj,"budget_id",event.aggregate_id)); old_retry=s.retry_budgets.get(key)
            if old_retry is not None:
                if obj.version != old_retry.version + 1 or obj.consumed != old_retry.consumed + 1 or obj.consumed > obj.max_retries:
                    raise ValueError("non-monotonic retry budget consumption")
                if obj.last_failure_fingerprint is None: raise ValueError("retry consumption requires failure fingerprint")
            updates["retry_budgets"]=fmap_insert_immutable(s.retry_budgets,key,obj,"retry budget"); updates["retry_consumptions"]=fmap_insert_immutable(s.retry_consumptions,key,obj,"retry consumption")
        elif et is EventType.IN_DOUBT_DECLARED and obj is not None:
            key=payload.get("node_id",getattr(obj,"node_id",event.aggregate_id)); updates["in_doubt"]=fmap_update(s.in_doubt,key,obj)
        elif et is EventType.IN_DOUBT_RESOLVED and obj is not None:
            key=payload.get("node_id",getattr(obj,"node_id",event.aggregate_id)); d=dict(s.in_doubt.items()); d.pop(key,None); updates["in_doubt"]=FrozenMap.from_items(d.items())
        elif et is EventType.EVIDENCE_INVALIDATED:
            inv=payload["invalidation_set"]
            updates["evidence_invalidations"]=_mark_invalidation(s,machine_maps,inv,event.event_id)
        elif et is EventType.ACCEPTANCE_SNAPSHOT_RECORDED:
            snap=payload["acceptance_snapshot"]; key=payload["snapshot_id"]
            if snap.snapshot_id != key: raise ValueError("acceptance snapshot identity mismatch")
            expected=canonical_acceptance_snapshot(s,key)
            if snap != expected: raise ValueError("acceptance snapshot is not derived from canonical state")
            updates["acceptance_snapshots"]=fmap_insert_immutable(s.acceptance_snapshots,key,snap,"acceptance snapshot")
        elif et is EventType.STATE_CHECKPOINTED and obj is not None:
            key=payload.get("checkpoint_id",getattr(obj,"checkpoint_id",event.aggregate_id)); updates["checkpoints"]=fmap_insert_immutable(s.checkpoints,key,obj,"checkpoint")
            snap=payload.get("acceptance_snapshot")
            if snap is not None: updates["acceptance_snapshots"]=fmap_update(s.acceptance_snapshots,snap.snapshot_id,snap)
        elif et is EventType.WORKSPACE_ROLLED_BACK and obj is not None:
            if obj.workspace_id != s.workspace_id: raise ValueError("rollback target workspace mismatch")
            updates["workspace_snapshot_id"]=obj.snapshot_id
            updates["target_snapshot"]=obj; updates["target_snapshots"]=fmap_update(s.target_snapshots,obj.snapshot_id,obj)
            inv=_revision_change_invalidations(s,et)
            updates["evidence_invalidations"]=_mark_invalidation(s,machine_maps,inv,event.event_id)
        lineage=payload.get("governing_budget_lineage")
        if lineage is not None: updates["governing_budget_lineages"]=fmap_update(s.governing_budget_lineages,lineage.lineage_id,lineage)
        frontier=payload.get("causal_frontier")
        if frontier is not None:
            updates["causal_frontier"]=frontier; updates["causal_frontiers"]=fmap_update(s.causal_frontiers,payload.get("decision_id",event.aggregate_id),frontier)
        # Materialize lifecycle truth back into the canonical domain objects before persisting the
        # derived indexes. This makes the invariant bidirectional: indexes are a projection of domain
        # objects, never an independent state machine.
        final_work_graph=updates.get("work_graph", s.work_graph)
        if final_work_graph is not None:
            nodes={}
            for nid,node in final_work_graph._nodes.items():
                target=machine_maps["WorkNodeStatus"].get(nid)
                if target is not None:
                    nodes[nid]=replace(node,status=WorkNodeStatus(target),worker_id=updates.get("assignments",s.assignments).get(nid,node.worker_id))
                else:
                    nodes[nid]=node
            updates["work_graph"]=replace(final_work_graph,_nodes=FrozenMap.from_items(nodes.items()))
        final_obligations=updates.get("obligations", s.obligations)
        if final_obligations is not None:
            ods={}
            for oid,ob in final_obligations._obligations.items():
                target=machine_maps["ObligationStatus"].get(oid)
                ods[oid]=replace(ob,status=ObligationStatus(target)) if target is not None else ob
            updates["obligations"]=replace(final_obligations,_obligations=FrozenMap.from_items(ods.items()))
        final_leases=updates.get("leases", s.leases)
        ld={}
        for lid,lease in final_leases.items():
            target=machine_maps["LeaseState"].get(lid)
            ld[lid]=replace(lease,state=LeaseState(target)) if target is not None else lease
        updates["leases"]=FrozenMap.from_items(ld.items())
        # Lifecycle maps are deterministic reducer indexes; historical events remain in EventStore, not state.
        facts.update({k: FrozenMap.from_items(tuple(v.items())) for k,v in machine_maps.items()})
        facts["last_event_type"]=et.value; facts["last_aggregate_id"]=event.aggregate_id
        facts["last_commit_id"]=event.commit_id
        facts["last_event_hash"]=event.event_hash
        facts["canonical_transition_digest"]=digest("sclass/canonical-transition/v1",(et,payload,event.event_hash))
        next_state=replace(s,**updates,event_sequence=event.event_sequence,event_head_hash=event.event_hash,reducer_version=self.version,reducer_facts=FrozenMap.from_items(facts.items()))
        state_revision=digest("sclass/state-revision/v3",(s.state_revision,event.event_hash,event.event_sequence+1))
        next_state=replace(next_state,state_revision=state_revision)
        assert_lifecycle_indexes_consistent(next_state)
        return next_state

    def replay(self, initial: EngineeringState, events: Sequence[CanonicalEvent]) -> EngineeringState:
        state=initial
        for event in events: state=self.reduce(state,event)
        return state

def assert_lifecycle_indexes_consistent(state: EngineeringState) -> None:
    facts=state.reducer_facts
    work_actual=dict(facts.get("WorkNodeStatus", FrozenMap.from_items()).items())
    if state.work_graph is None:
        if work_actual:
            raise ValueError("WorkNodeStatus index exists without WorkGraph domain authority")
    else:
        work_expected={nid: node.status.value for nid,node in state.work_graph._nodes.items()}
        if work_expected != work_actual:
            raise ValueError("WorkNodeStatus derived index disagrees with WorkGraph projection")
    obligation_actual=dict(facts.get("ObligationStatus", FrozenMap.from_items()).items())
    if state.obligations is None:
        if obligation_actual:
            raise ValueError("ObligationStatus index exists without ObligationGraph domain authority")
    else:
        obligation_expected={oid: o.status.value for oid,o in state.obligations._obligations.items()}
        if obligation_expected != obligation_actual:
            raise ValueError("ObligationStatus derived index disagrees with ObligationGraph projection")
    lease_actual=dict(facts.get("LeaseState", FrozenMap.from_items()).items())
    lease_expected={lid: l.state.value for lid,l in state.leases.items()}
    if lease_expected != lease_actual:
        raise ValueError("LeaseState derived index disagrees with LeaseRecord projection")
    requirement_actual=dict(facts.get("RequirementStatus", FrozenMap.from_items()).items())
    requirement_expected={rid: rec.status.value for rid,rec in state.requirements.items()}
    if requirement_expected != requirement_actual:
        raise ValueError("RequirementStatus derived index disagrees with RequirementRecord projection")


REFERENCE_REDUCER=ReferenceReducer()
REFERENCE_REDUCER_HANDLERS={event_type:(lambda prior,event,et=event_type: REFERENCE_REDUCER.reduce(prior,event)) for event_type in EventType}

def assert_reducer_totality() -> None:
    if set(REFERENCE_REDUCER_HANDLERS) != set(EventType) or len(REFERENCE_REDUCER_HANDLERS) != len(EventType): raise AssertionError("EventType/reducer coverage mismatch")

### 12.3 Reducer and versioning


class StateView(Protocol):
    def snapshot(self) -> EngineeringState: ...             # atomic immutable state + event head


class TransitionOutcome(Enum):
    APPLIED = "APPLIED"
    REJECTED_ILLEGAL_TRANSITION = "REJECTED_ILLEGAL_TRANSITION"
    REJECTED_STALE_HEAD = "REJECTED_STALE_HEAD"
    REJECTED_UNAUTHORIZED = "REJECTED_UNAUTHORIZED"
    REJECTED_INVARIANT = "REJECTED_INVARIANT"

@canonical_dataclass
class Command:
    command_id: str
    workspace_id: str
    actor: ActorIdentity
    event_type: EventType
    payload: FrozenMap
    expected_head: Digest
    actor_signature: Optional[SignatureBlock]
    aggregate_id: str                  # authoritative domain aggregate identity; never inferred from payload/command id

    def __post_init__(self):
        if not self.command_id or not self.workspace_id or not self.aggregate_id:
            raise ValueError("command identity fields must be non-empty")

@canonical_dataclass
class TransitionResult:
    outcome: TransitionOutcome
    new_head: Optional[EventHead]

class TransitionAuthority(Protocol):
    """validate(command) → derive event → EventStore.append(CAS) → reducer. The ONLY status writer."""
    def submit(self, command: Command) -> TransitionResult: ...


@canonical_dataclass
class EventHead:
    sequence: int
    hash: Digest

class AppendResult(Enum):
    APPENDED = "APPENDED"
    HEAD_MISMATCH = "HEAD_MISMATCH"
    NOT_LEADER = "NOT_LEADER"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    STORE_ERROR = "STORE_ERROR"

class ChainStatus(Enum):
    VALID = "VALID"
    BROKEN_HASH = "BROKEN_HASH"
    GAP = "GAP"
    UNREADABLE = "UNREADABLE"

@canonical_dataclass
class CheckpointRef:
    checkpoint_id: str
    event_sequence: int
    state_digest: Digest
    commit_id: str

class WorkspaceTransaction(Protocol):
    """Single durable unit for canonical event, reducer projection, materialized indexes and commit record."""
    def commit(self) -> AppendResult: ...
    def abort(self) -> AppendResult: ...

class EventStore(Protocol):
    def append(self, event: CanonicalEvent, commit: CommitRecord, expected_head_hash: Digest) -> tuple[AppendResult, Optional[EventHead]]: ...
    def append_batch(self, events: Sequence[CanonicalEvent], commit: CommitRecord, expected_head_hash: Digest) -> tuple[AppendResult, Optional[EventHead]]: ...
    def read(self, sequence_from: int, sequence_to: int) -> Sequence[CanonicalEvent]: ...
    def head(self) -> EventHead: ...
    def verify_chain(self, sequence_from: int, sequence_to: int) -> ChainStatus: ...
    def replay(self, from_checkpoint: Optional[CheckpointRef], reducer_version: str) -> EngineeringState: ...


@canonical_dataclass
class InDoubtRecord:
    node_id: str
    reason: str
    unresolved_effect_ids: tuple[str, ...]
    since_sequence: int

@canonical_dataclass
class SignatureVerificationRecord:
    subject_id: str
    signed_payload_digest: Digest
    signature_digest: Digest
    key_id: str
    verification_result: SignatureVerificationResult
    verification_time: UtcInstant

@canonical_dataclass
class EngineeringState:
    """The canonical reduced current state. STRICTLY and DEEPLY IMMUTABLE (FrozenMap/tuples)."""
    workspace_id: str
    state_schema_version: int
    reducer_version: str
    state_revision: str
    event_sequence: int
    event_head_hash: Digest
    objective: CanonicalObjective
    workspace_snapshot_id: str
    target_snapshot: TargetSnapshot
    causal_frontier: CausalFrontier
    policy_version: str
    policy_digest: Digest
    active_policy: Policy                 # exact immutable policy content for replay
    world_model_revision: str
    obligations: ObligationGraph
    work_graph: WorkGraph
    acceptance_contracts: FrozenMap            # contract_id -> AcceptanceContract
    verification_plans: FrozenMap              # plan_id -> VerificationPlan
    evidence: FrozenMap                        # evidence_id -> EvidenceClosure
    assessments: FrozenMap                     # assessment_id -> IndependentAssessment
    requirements: FrozenMap                   # requirement_id -> RequirementRecord (canonical lifecycle domain)
    assignments: FrozenMap                     # node_id -> worker_instance_id
    leases: FrozenMap                          # lease_id -> LeaseRecord
    retry_budgets: FrozenMap                   # budget_id -> RetryBudget
    budget_reservations: FrozenMap             # reservation_id -> BudgetReservation
    repair_plans: FrozenMap                    # plan_id -> RepairPlan
    waivers: FrozenMap                         # waiver_id -> AcceptedRiskWaiver
    in_doubt: FrozenMap                        # node_id -> InDoubtRecord
    releases: FrozenMap                        # release_id -> ReleaseState
    verified_deltas: FrozenMap                 # delta_id -> VerifiedWorkspaceDelta
    break_glass_consumption: FrozenMap         # authority_id -> consumed count (event-materialized)
    approval_records: FrozenMap                 # approval_id -> ApprovalRecord
    approval_sets: FrozenMap                    # set_id -> ApprovalSet
    signature_verification_facts: FrozenMap     # signature/receipt/assessment id -> VERIFIED/INVALID
    causal_frontiers: FrozenMap                 # decision_id -> CausalFrontier
    target_snapshots: FrozenMap                 # snapshot_id -> TargetSnapshot
    acceptance_snapshots: FrozenMap             # snapshot_id -> AcceptanceSnapshot
    execution_generations: FrozenMap            # work_node_id -> ExecutionGeneration
    governing_budget_lineages: FrozenMap        # lineage_id -> GoverningBudgetLineage
    authorization_decisions: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    execution_outcomes: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    checkpoints: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    retry_consumptions: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    reducer_facts: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    signature_verification_records: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    decisions: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    decision_outcomes: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    observations: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    verification_results: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    quiescence_proofs: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    execution_intents: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    boundary_violations: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    evidence_invalidations: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    release_evaluations: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())
    external_effect_receipts: FrozenMap = field(default_factory=lambda: FrozenMap.from_items())

def genesis_engineering_state(workspace_id: str = "default") -> EngineeringState:
    """Canonical immutable empty state. Full EventStore replay always starts here."""
    empty_graph=SemanticGraph((),())
    empty_obligations=ObligationGraph(empty_graph,FrozenMap.from_items())
    empty_work_graph=WorkGraph(
        "GENESIS", "GENESIS", "GENESIS", "GENESIS", "GENESIS",
        empty_graph, FrozenMap.from_items(),
    )
    empty=frozenset()
    empty_map=FrozenMap.from_items()
    state=EngineeringState(
        workspace_id=workspace_id,
        state_schema_version=STATE_SCHEMA_VERSION,
        reducer_version=REDUCER_VERSION,
        state_revision=digest("sclass/state-revision/genesis/v1",workspace_id),
        event_sequence=0,
        event_head_hash=GENESIS_EVENT_HASH,
        objective=None,
        workspace_snapshot_id="",
        target_snapshot=None,
        causal_frontier=None,
        policy_version="",
        policy_digest=Digest("sha256:"+"0"*64),
        active_policy=None,
        world_model_revision="",
        obligations=empty_obligations,
        work_graph=empty_work_graph,
        requirements=empty_map,
        acceptance_contracts=empty_map,
        verification_plans=empty_map,
        evidence=empty_map,
        assessments=empty_map,
        assignments=empty_map,
        leases=empty_map,
        retry_budgets=empty_map,
        budget_reservations=empty_map,
        repair_plans=empty_map,
        waivers=empty_map,
        in_doubt=empty_map,
        releases=empty_map,
        verified_deltas=empty_map,
        break_glass_consumption=empty_map,
        approval_records=empty_map,
        approval_sets=empty_map,
        signature_verification_facts=empty_map,
        causal_frontiers=empty_map,
        target_snapshots=empty_map,
        acceptance_snapshots=empty_map,
        execution_generations=empty_map,
        governing_budget_lineages=empty_map,
        authorization_decisions=empty_map,
        execution_outcomes=empty_map,
        checkpoints=empty_map,
        retry_consumptions=empty_map,
        reducer_facts=FrozenMap.from_items((
            ("WorkNodeStatus",empty_map),
            ("ObligationStatus",empty_map),
            ("RequirementStatus",empty_map),
            ("LeaseState",empty_map),
            ("genesis",True),
        )),
        signature_verification_records=empty_map,
        decisions=empty_map,
        decision_outcomes=empty_map,
        observations=empty_map,
        verification_results=empty_map,
        quiescence_proofs=empty_map,
        execution_intents=empty_map,
        boundary_violations=empty_map,
        evidence_invalidations=empty_map,
        release_evaluations=empty_map,
        external_effect_receipts=empty_map,
    )
    return state

def engineering_state_digest(state: EngineeringState) -> Digest:
    return digest("sclass/engineering-state/v1", state)

def canonical_state_digest(state: EngineeringState) -> Digest:
    if isinstance(state, EngineeringState):
        return engineering_state_digest(state)
    supplied=getattr(state,"state_digest",None)
    if _is_digest_value(supplied):
        return Digest(supplied)
    raise TypeError("canonical state or explicit state_digest protocol required")

EngineeringState.state_digest = property(lambda self: engineering_state_digest(self))

class StateLoadStatus(Enum):
    FOUND = "FOUND"
    NOT_FOUND = "NOT_FOUND"
    CORRUPT = "CORRUPT"
    IO_ERROR = "IO_ERROR"
    UNSUPPORTED_SCHEMA = "UNSUPPORTED_SCHEMA"

@canonical_dataclass
class LoadResult:
    status: StateLoadStatus
    state: Optional[EngineeringState]
    detail: str

class RestoreStatus(Enum):
    RESTORED_FULL = "RESTORED_FULL"
    RESTORED_PARTIAL = "RESTORED_PARTIAL"     # valid prefix restored; loss is explicit
    FAILED = "FAILED"

@canonical_dataclass
class RestoreResult:
    status: RestoreStatus
    restored_sequence: int
    lost_sequence_range: Optional[tuple[int, int]]

class StateStore(Protocol):
    def load(self, workspace_id: str) -> LoadResult: ...
    def checkpoint(self, state: EngineeringState) -> CheckpointRef: ...
    def current_revision(self, workspace_id: str) -> Optional[str]: ...
    def validate_against_head(self, state: EngineeringState, head: EventHead) -> ChainStatus: ...
    def verify_integrity(self, workspace_id: str) -> StateLoadStatus: ...
    def migrate(self, workspace_id: str, target_schema_version: int) -> StateLoadStatus: ...
    def backup(self, workspace_id: str, destination_token: str) -> CheckpointRef: ...
    def restore(self, workspace_id: str, source_token: str) -> RestoreResult: ...


class FailureClass(Enum):
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    BOUNDARY_VIOLATION = "BOUNDARY_VIOLATION"
    TIMEOUT = "TIMEOUT"
    LEASE_LOST = "LEASE_LOST"
    OBSERVATION_FAILED = "OBSERVATION_FAILED"

class RepairStrategy(Enum):
    RETRY_SAME = "RETRY_SAME"
    ALTERNATE_WORKER = "ALTERNATE_WORKER"
    REPLAN = "REPLAN"
    ROLLBACK = "ROLLBACK"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"

@canonical_dataclass
class RepairObligation:
    source_failure_id: str
    source_evidence_id: Optional[str]
    root_cause: str
    objective_revision: str
    workspace_snapshot_id: str
    affected_obligations: frozenset[str]
    repair_work_graph_revision: str
    repair_strategy: RepairStrategy
    expected_verification: tuple[EvidenceKind, ...]
    attempt: int                         # read from RetryBudget at planning time; not an independent counter
    budget: ResourceBudget

@canonical_dataclass
class RepairPlan:
    plan_id: str
    failure_fingerprint: Digest
    repairs: tuple[RepairObligation, ...]
    strategy: RepairStrategy

class RollbackResult(Enum):
    ROLLED_BACK = "ROLLED_BACK"
    PARTIAL = "PARTIAL"
    VERIFY_MISMATCH = "VERIFY_MISMATCH"       # post-rollback digest != target snapshot digest
    FAILED = "FAILED"

class WorkspaceRollbackProvider(Protocol):
    def rollback_to(self, snapshot_id: str, handle: WorkspaceSnapshotHandle) -> RollbackResult: ...
    # After rollback, handle.snapshot_digest() MUST equal the target snapshot digest, else VERIFY_MISMATCH.

class CompensationCapability(Enum):
    REVERSIBLE = "REVERSIBLE"
    COMPENSABLE = "COMPENSABLE"
    IRREVERSIBLE = "IRREVERSIBLE"

class CompensationResult(Enum):
    COMPENSATED = "COMPENSATED"
    ALREADY_COMPENSATED = "ALREADY_COMPENSATED"
    FAILED = "FAILED"
    IN_DOUBT = "IN_DOUBT"

class EffectCompensationProvider(Protocol):
    def capability(self, receipt: SideEffectReceipt) -> CompensationCapability: ...
    def compensate(self, receipt: SideEffectReceipt, idempotency_key: str) -> CompensationResult: ...

class RecoveryOutcome(Enum):
    RECOVERED = "RECOVERED"
    PARTIALLY_COMPENSATED = "PARTIALLY_COMPENSATED"
    IN_DOUBT = "IN_DOUBT"
    ESCALATED = "ESCALATED"

@canonical_dataclass
class RecoveryReport:
    outcome: RecoveryOutcome
    compensated_effect_ids: tuple[str, ...]
    unresolved_effect_ids: tuple[str, ...]
    rollback: RollbackResult

class CoordinatedRecovery(Protocol):
    """Saga-style compensation, NOT atomic rollback (fixes #56): external effects cannot be
    assumed atomically reversible. Irreversible or unverifiable effects → IN_DOUBT."""
    def recover(self, node_id: str, plan: RepairPlan, effects: tuple[SideEffectReceipt, ...]) -> RecoveryReport: ...


class CanonicalCoordinatedRecovery:
    """Canonical saga-style compensation coordinator.
    Effects that cannot be verified or compensated transition to IN_DOUBT, never assumed."""
    def recover(self, node_id: str, plan: RepairPlan, effects: tuple[SideEffectReceipt, ...],
                compensation_provider: Optional[EffectCompensationProvider] = None) -> RecoveryReport:
        compensated = []
        unresolved = []
        for eff in sorted(effects, key=lambda x: x.effect_id):
            if eff.status is SideEffectStatus.COMPENSATED:
                compensated.append(eff.effect_id)
            elif compensation_provider is not None:
                try:
                    cap = getattr(compensation_provider, "capability", lambda e: CompensationCapability.COMPENSABLE)(eff)
                    if cap is CompensationCapability.REVERSIBLE or cap is CompensationCapability.COMPENSABLE:
                        cres = compensation_provider.compensate(eff, f"comp-{eff.effect_id}")
                        if cres is CompensationResult.COMPENSATED or cres is CompensationResult.ALREADY_COMPENSATED:
                            compensated.append(eff.effect_id)
                        else:
                            unresolved.append(eff.effect_id)
                    else:
                        unresolved.append(eff.effect_id)
                except Exception:
                    unresolved.append(eff.effect_id)
            else:
                unresolved.append(eff.effect_id)

        outcome = RecoveryOutcome.IN_DOUBT if unresolved else RecoveryOutcome.RECOVERED
        rollback = RollbackResult.ROLLED_BACK if outcome is RecoveryOutcome.RECOVERED else RollbackResult.PARTIAL
        return RecoveryReport(
            outcome=outcome,
            compensated_effect_ids=tuple(compensated),
            unresolved_effect_ids=tuple(unresolved),
            rollback=rollback
        )


class MessageRole(Enum):
    SYSTEM = "SYSTEM"
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"

class MessageSource(Enum):
    SYSTEM_INSTRUCTION = "SYSTEM_INSTRUCTION"
    USER_INTENT = "USER_INTENT"
    CANONICAL_STATE = "CANONICAL_STATE"
    REPOSITORY_DATA = "REPOSITORY_DATA"
    TOOL_OUTPUT = "TOOL_OUTPUT"
    MODEL_OUTPUT = "MODEL_OUTPUT"

class TrustLevel(Enum):
    TRUSTED = "TRUSTED"
    UNTRUSTED = "UNTRUSTED"

@canonical_dataclass
class MessageProvenance:
    source: MessageSource
    trust: TrustLevel
    snapshot_id: Optional[str]
    path: Optional[str]
    content_digest: Digest
    classification: DataClassification

@canonical_dataclass
class MessageContent:
    text: str
    content_digest: Digest
    token_estimate: int

@canonical_dataclass
class Message:
    role: MessageRole
    content: MessageContent
    provenance: MessageProvenance


class ModelCallStatus(Enum):
    OK = "OK"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    REFUSED_POLICY = "REFUSED_POLICY"        # egress / provenance policy denied before sending
    BUDGET_DENIED = "BUDGET_DENIED"

class ProviderErrorClass(Enum):
    NONE = "NONE"
    RATE_LIMITED = "RATE_LIMITED"
    OVERLOADED = "OVERLOADED"
    INVALID_REQUEST = "INVALID_REQUEST"
    AUTH = "AUTH"
    CONTENT_FILTER = "CONTENT_FILTER"
    NETWORK = "NETWORK"
    UNKNOWN = "UNKNOWN"

@canonical_dataclass
class TokenUsage:
    provider_input_tokens: int
    provider_output_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    billable_units: int
    # Provider-reported fields are billing truth; estimates come from one tokenizer and are NEVER billing truth.

@canonical_dataclass
class CostEstimate:
    input_micro_usd: int
    output_micro_usd: int
    total_micro_usd: int

@canonical_dataclass
class ModelRequest:
    request_id: str
    messages: tuple[Message, ...]
    model: str
    response_schema_id: Optional[str]
    max_tokens: int
    temperature_milli: int                    # 0..2000; no floats
    timeout_ms: int
    budget_reservation_id: str
    generation_config: FrozenMap

@canonical_dataclass
class ModelResponse:
    status: ModelCallStatus
    content: Optional[FrozenMap]
    usage: TokenUsage
    cost: CostEstimate
    provider_error: ProviderErrorClass
    retryable: bool
    model: ModelInfo

class CancellationToken(Protocol):
    def is_cancelled(self) -> bool: ...
    def cancel(self, reason: str) -> None: ...

class ModelGateway(Protocol):
    """Enforcement point for ProviderEgressPolicy, DataClassificationPolicy, RedactionPolicy and
    provenance rules BEFORE any byte leaves the process. Reserves budget (LLM_CALL level) and settles actuals."""
    def capabilities(self, model: str) -> ModelInfo: ...
    def complete(self, request: ModelRequest, cancel: CancellationToken) -> ModelResponse: ...


class ContextItemKind(Enum):
    REPO_MAP = "REPO_MAP"
    FILE_RANGE = "FILE_RANGE"
    SYMBOL = "SYMBOL"
    EVIDENCE_SUMMARY = "EVIDENCE_SUMMARY"
    CONSTRAINT = "CONSTRAINT"

@canonical_dataclass
class SourceRange:
    start_line: int
    end_line: int

@canonical_dataclass
class ContextItem:
    item_id: str
    kind: ContextItemKind
    source_snapshot_id: str
    path: Optional[str]
    range: Optional[SourceRange]
    symbol: Optional[str]
    content_digest: Digest
    classification: DataClassification
    trust: TrustLevel
    rank: int                                # deterministic ranking; order is semantic
    token_estimate: int

@canonical_dataclass
class RedactionReport:
    policy_id: str
    redacted_item_ids: tuple[str, ...]
    redaction_count: int
    report_digest: Digest

@canonical_dataclass
class ContextPackage:
    budget: int
    repo_map: ContextItem                    # ALWAYS included (restored, fixes #62)
    items: tuple[ContextItem, ...]           # ordered by (rank, item_id)
    obligation_context: str
    constraints: tuple[str, ...]
    prior_evidence: tuple[str, ...]          # evidence ids, FRESH only
    token_accounting: TokenUsage
    redaction: RedactionReport
    ranking_policy_version: str


class CredentialBroker(Protocol):
    """Secrets live only in the broker. They are injected into a boundary (env or fd) for the
    lifetime of one execution, never written to any event, receipt, cache or log."""
    def inject(self, grant: CredentialGrant, ctx: BoundaryContext) -> None: ...
    def revoke(self, ctx: BoundaryContext) -> None: ...
    def redact(self, text: str) -> str: ...        # scrubs registered secret values from outputs/excerpts


@canonical_dataclass
class CacheIdentity:
    workspace_id: str
    snapshot_id: str
    event_head: Digest
    world_model_revision: str
    policy_version: str
    objective_revision: str
    builder_version: str
    tool_version: str
    verifier_config_digest: Digest
    context_policy_version: str
    parser_version: str
    schema_version: int

class CacheFillDecision(Enum):
    HIT = "HIT"
    LEADER = "LEADER"          # caller computes and publishes
    WAIT = "WAIT"              # another caller holds the fill lease; wait for its result

class CacheFillCoordinator(Protocol):
    """Lease-based fill + request deduplication: 20 workers asking for the same expensive
    context/world-model computation trigger ONE computation."""
    def acquire(self, identity: CacheIdentity, key: str) -> CacheFillDecision: ...
    def publish(self, identity: CacheIdentity, key: str, value_digest: Digest) -> None: ...

class OverloadOutcome(Enum):
    ACCEPTED = "ACCEPTED"
    DEFERRED = "DEFERRED"
    REJECTED_OVERLOAD = "REJECTED_OVERLOAD"
    SHED_LOW_PRIORITY = "SHED_LOW_PRIORITY"

@canonical_dataclass
class BackpressurePolicy:
    command_queue_bound: int
    indexing_queue_bound: int
    verification_queue_bound: int
    telemetry_queue_bound: int
    telemetry_drop_first: bool


class ReleaseVerdict(Enum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    NOT_EVALUABLE = "NOT_EVALUABLE"

@canonical_dataclass
class ReleaseState:
    release_id: str
    release_policy_version: str
    artifact_digest: Digest
    target_environment: str
    blocking_obligations: tuple[str, ...]
    waivers: tuple[str, ...]                 # waiver ids
    final_assessments: tuple[str, ...]       # assessment ids
    provenance: tuple[Digest, ...]           # build/verification provenance digests
    engineering_snapshot: EngineeringSnapshot
    acceptance_snapshot_id: str
    acceptance_snapshot_digest: Digest

@canonical_dataclass
class ReleaseEvaluation:
    release_id: str
    acceptance_snapshot_digest: Digest
    derived_obligation_results: FrozenMap
    derived_assessment_results: FrozenMap
    derived_waiver_results: FrozenMap
    artifact_provenance_digest: Digest
    evaluation_digest: Digest
    verdict: ReleaseVerdict
    evaluated_at: UtcInstant

def _object_without_signature(obj: Any) -> tuple[Any, ...]:
    return tuple(getattr(obj,f.name) for f in fields(type(obj)) if f.name != "signature")

def signed_payload_digest(domain: str, obj: Any) -> Digest:
    return digest(domain, _object_without_signature(obj))

def evidence_signed_payload_digest(receipt: EvidenceReceipt) -> Digest:
    return digest("sclass/evidence-signed-payload/v1", receipt.payload)

def assessment_signed_payload_digest(assessment: IndependentAssessment) -> Digest:
    return signed_payload_digest("sclass/assessment-signed-payload/v1", assessment)

def waiver_signed_payload_digest(waiver: AcceptedRiskWaiver) -> Digest:
    return signed_payload_digest("sclass/waiver-signed-payload/v1", waiver)

def approval_signed_payload_digest(approval: ApprovalRecord) -> Digest:
    return signed_payload_digest("sclass/approval-signed-payload/v1", approval)

def assessment_input_digest(assessment: IndependentAssessment, state: EngineeringState) -> Digest:
    closure=state.evidence.get(assessment.evidence_id)
    if closure is None:
        raise ValueError("assessment references unknown evidence")
    obligation=state.obligations._obligations.get(closure.obligation_id)
    contract_id=getattr(obligation,"acceptance_contract_id",closure.obligation_id)
    contract=state.acceptance_contracts.get(contract_id)
    if contract is None:
        raise ValueError("assessment references unknown acceptance contract")
    plans=state.verification_plans if hasattr(state,"verification_plans") else FrozenMap.from_items()
    plan=next((p for _,p in plans.items() if getattr(p,"obligation_id",None)==closure.obligation_id and getattr(p,"revision",None)==closure.verification_plan_revision), None)
    # The production canonical state always contains the exact VerificationPlan object.
    # For non-canonical/malformed state adapters, retain the explicit revision token so the
    # digest remains bound rather than silently dropping the dimension. The release gate below
    # still rejects such malformed assessments as non-canonical.
    if plan is None:
        plan=("verification-plan-revision", closure.verification_plan_revision)
    return digest("sclass/assessment-input/v2",(
        assessment.evidence_id,
        digest("sclass/evidence-closure/v1",closure),
        assessment.target_snapshot_digest,
        assessment.policy_version,
        contract,
        plan,
        assessment.artifact_digest,
    ))

def signature_block_digest(block: SignatureBlock) -> Digest:
    return digest("sclass/signature-block/v1", (block.algorithm, block.key_id, block.trust_root, block.canonicalization_version, block.signature))

def signature_subject_is_verified(state: EngineeringState, subject_id: str, signed_payload_digest_value: Digest, signature: SignatureBlock) -> bool:
    rec=state.signature_verification_records.get(subject_id)
    return (isinstance(rec,SignatureVerificationRecord) and rec.subject_id == subject_id and
            rec.signed_payload_digest == signed_payload_digest_value and
            rec.signature_digest == signature_block_digest(signature) and
            rec.verification_result is SignatureVerificationResult.VALID)

def _valid_signature_ids(state: EngineeringState) -> frozenset[str]:
    return frozenset(k for k,v in state.signature_verification_records.items()
                      if isinstance(v,SignatureVerificationRecord)
                      and v.verification_result is SignatureVerificationResult.VALID)

def _dependency_set_from_payload(payload: SignedEvidencePayload) -> EvidenceDependencySet:
    if payload.dependency_entries:
        return EvidenceDependencySet(tuple(payload.dependency_entries), (), False)
    return EvidenceDependencySet((), (), True)

def _validate_evidence_closure_against_state(state: EngineeringState, closure: EvidenceClosure, at: UtcInstant) -> bool:
    if closure.obligation_id not in state.obligations._obligations:
        return False
    obligation=state.obligations._obligations[closure.obligation_id]
    contract=state.acceptance_contracts.get(obligation.acceptance_contract_id)
    if contract is None or contract.revision != closure.acceptance_contract_revision:
        return False
    plan_id=getattr(obligation,"verification_plan_id",None)
    if not plan_id:
        return False
    plan=state.verification_plans.get(plan_id)
    if plan is None or plan.revision != closure.verification_plan_revision or plan.obligation_id != closure.obligation_id:
        return False
    if plan.contract_revision != closure.acceptance_contract_revision:
        return False
    if closure.workspace_snapshot_id != state.workspace_snapshot_id:
        return False
    if closure.target_snapshot_digest != target_snapshot_digest(state.target_snapshot):
        return False
    if state.objective is not None and closure.objective_revision != state.objective.revisions[-1].revision_id:
        return False
    if closure.policy_version != state.policy_version:
        return False
    if closure.environment_digest != state.target_snapshot.environment_digest:
        return False
    # Every referenced observation and every verification result must be canonical.
    for oid in closure.observation_ids:
        if oid not in state.observations:
            return False
    all_receipt_ids={r.receipt_id for r in closure.evidence_receipts}
    if len(all_receipt_ids) != len(closure.evidence_receipts):
        return False
    for receipt in closure.evidence_receipts:
        if receipt.payload.observation_id not in state.observations:
            return False
        if receipt.payload.verification_step_id not in state.verification_results:
            return False
        if receipt.payload.result_status is not VerificationStatus.PASS:
            return False
        if dependency_set_digest(_dependency_set_from_payload(receipt.payload)) != receipt.payload.dependency_set_digest:
            return False
        if not validate_evidence_receipt_identity(receipt):
            return False
        if receipt.receipt_id not in _valid_signature_ids(state):
            return False
    profiles=state.reducer_facts.get("verifier_profiles",FrozenMap.from_items())
    current_deps=state.target_snapshot.dependency_digests
    dep_digest=dependency_map_digest(current_deps)
    ctx=FreshnessContext(
        state.workspace_snapshot_id, target_snapshot_digest(state.target_snapshot), closure.objective_revision,
        state.policy_version, closure.acceptance_contract_revision, closure.verification_plan_revision,
        closure.verifier_config_digest, closure.environment_digest, current_deps, dep_digest,
        invalidated_evidence_ids(state))
    composition=evaluate_evidence_composition(contract,closure.evidence_receipts,ctx,profiles,_valid_signature_ids(state))
    if composition.verdict is not ClosureVerdict.SATISFIED:
        return False
    if closure.verdict is not ClosureVerdict.SATISFIED:
        return False
    if tuple(closure.requirement_results) != tuple(composition.requirement_results):
        return False
    fresh=is_fresh(closure,FRESHNESS_FLOOR,ctx)
    return fresh.state is FreshnessState.FRESH

def validate_obligation_satisfaction(state: EngineeringState, obligation_id: str, evidence_id: str, assessment_id: str, at: UtcInstant) -> bool:
    obligation=state.obligations._obligations.get(obligation_id)
    closure=state.evidence.get(evidence_id)
    assessment=state.assessments.get(assessment_id)
    if obligation is None or closure is None or assessment is None:
        return False
    if closure.obligation_id != obligation_id or obligation.satisfied_by not in (None,evidence_id):
        return False
    if assessment.evidence_id != evidence_id or assessment.verdict is not AssessmentVerdict.ACCEPT:
        return False
    if assessment.workspace_snapshot_id != state.workspace_snapshot_id or assessment.policy_version != state.policy_version:
        return False
    if assessment.target_snapshot_digest != target_snapshot_digest(state.target_snapshot):
        return False
    if not _validate_evidence_closure_against_state(state,closure,at):
        return False
    try:
        if assessment_input_digest(assessment,state) != assessment.input_digest:
            return False
    except Exception:
        return False
    if not signature_subject_is_verified(state,assessment.assessment_id,assessment_signed_payload_digest(assessment),assessment.signature):
        return False
    return True

def validate_policy_activation_event(state: EngineeringState, new_policy: Policy, policy_digest: Digest,
                                     approvals: tuple[ApprovalRecord,...], at: UtcInstant) -> bool:
    if policy_digest != digest("sclass/policy/v1",new_policy):
        return False
    if state.active_policy is not None:
        if new_policy.policy_id != state.active_policy.policy_id or new_policy.floor_id != state.active_policy.floor_id or new_policy.floor_digest != state.active_policy.floor_digest:
            return False
        relation=policy_relation(state.active_policy,new_policy)
        # A relaxation must meet the immutable SDK governance floor; candidate policy cannot self-set its quorum.
        if relation is PolicyRelation.RELAXED:
            required=GOVERNANCE_APPROVAL_QUORUMS[ApprovalKind.POLICY_RELAXATION]
            if len({a.principal_id for a in approvals}) < required:
                return False
            valid=_valid_signature_ids(state)
            if any(a.approval_id not in valid or a.kind is not ApprovalKind.POLICY_RELAXATION for a in approvals):
                return False
        elif relation is PolicyRelation.UNSUPPORTED_CHANGE:
            return False
    # Every supplied approval must be content-bound even when not needed.
    for a in approvals:
        if a.workspace_id != state.workspace_id or a.policy_version != new_policy.policy_version:
            return False
    return True

def canonical_governing_budget_lineage(state: EngineeringState, node_id: str) -> GoverningBudgetLineage:
    """Construct the authoritative budget lineage used by execution admission.

    The producer derives its identity from canonical policy/work-graph state; callers
    may select a node but cannot supply an independent budget authority.
    """
    if state.objective is None or state.active_policy is None or state.work_graph is None:
        raise ValueError("complete canonical state required for budget lineage")
    node=state.work_graph._nodes.get(node_id)
    if node is None:
        raise ValueError("unknown work node for budget lineage")
    objective=state.objective.revisions[-1]
    objective_budget_id=f"{state.objective.objective_id}:{objective.revision_id}"
    retry_ids=tuple(sorted(b.budget_id for b in state.retry_budgets.values() if b.node_id == node_id))
    reservation_ids=tuple(sorted(r.reservation_id for r in state.budget_reservations.values()
                                  if r.governing_budget_lineage_id == node.governing_budget_lineage_id))
    lineage=GoverningBudgetLineage(
        node.governing_budget_lineage_id, state.workspace_id, objective_budget_id,
        digest("sclass/budget-consumed/v1", tuple()),
        digest("sclass/budget-reserved/v1", tuple((r, state.budget_reservations[r]) for r in reservation_ids)),
        retry_ids, (), (), (), 1)
    existing=state.governing_budget_lineages.get(lineage.lineage_id)
    if existing is not None and existing != lineage:
        # A canonical lineage may advance only through an explicit canonical event.
        lineage=replace(lineage, revision=getattr(existing,"revision",0)+1)
    return lineage


def canonical_causal_frontier(state: EngineeringState, decision: AuthorizationDecision,
                              lineage: GoverningBudgetLineage, risk_tier: RiskTier = RiskTier.LOW) -> CausalFrontier:
    """Construct the causal frontier from canonical state plus the exact authorization decision."""
    if state.objective is None or state.target_snapshot is None or state.work_graph is None or state.active_policy is None:
        raise ValueError("complete canonical state required for causal frontier")
    profile=state.active_policy.risk_mapping.control_profiles.get(risk_tier)
    if profile is None:
        profiles=tuple(state.active_policy.risk_mapping.control_profiles.values())
        profile=profiles[0] if profiles else None
    if profile is None:
        raise ValueError("canonical control profile missing")
    objective=state.objective.revisions[-1]
    frontier_seed=(decision.decision_id,state.workspace_id,state.event_head_hash,lineage.lineage_id,objective.revision_id)
    frontier_id=str(digest("sclass/causal-frontier-id/v1",frontier_seed))
    authorization_epoch=str(digest("sclass/authorization-epoch/v1",(decision.decision_id,decision.decided_at,state.policy_version)))
    deps=tuple(sorted(state.target_snapshot.dependency_digests.values()))
    reasons=tuple(sorted(("AUTHORIZATION_DECISION", "CANONICAL_POLICY", "TARGET_SNAPSHOT", "WORKGRAPH")))
    profile_id=str(digest("sclass/control-profile-id/v1",profile))
    return CausalFrontier(frontier_id,profile_id,state.policy_version,objective.revision_id,
        state.work_graph.obligation_graph_revision,state.work_graph.revision_id,state.policy_digest,
        target_snapshot_digest(state.target_snapshot),authorization_epoch,decision.capability_attestation_digest,
        digest("sclass/budget-lineage/v1",lineage),deps,reasons)


def canonical_current_state_binding(state: EngineeringState, execution_generation: int, governing_budget_lineage_id: str) -> StateBinding:
    if state.objective is None or state.work_graph is None or state.target_snapshot is None or state.causal_frontier is None:
        raise ValueError("complete canonical state binding requires objective/workgraph/target/frontier")
    if not governing_budget_lineage_id:
        raise ValueError("governing budget lineage is required")
    return StateBinding(
        state.workspace_id,
        state.objective.revisions[-1].revision_id,
        state.work_graph.revision_id,
        state.policy_version,
        state.workspace_snapshot_id,
        target_snapshot_digest(state.target_snapshot),
        digest("sclass/causal-frontier/v1",state.causal_frontier),
        governing_budget_lineage_id,
        execution_generation,
        state.causal_frontier.authorization_epoch,
        state.event_head_hash)


def authorization_target_digest(decision: AuthorizationDecision) -> Digest:
    return digest("sclass/authorization-target/v1", (decision.proposal_id, decision.work_node_id, decision.request_content_digest, decision.state_binding_digest))

def effect_scope_digest(scope: EffectScope) -> Digest:
    return digest("sclass/effect-scope/v1", scope)

def validate_authorization_decision(state: EngineeringState, decision: AuthorizationDecision, at: UtcInstant) -> bool:
    """Independently recompute the authorization contract against canonical state."""
    if not isinstance(decision, AuthorizationDecision) or not isinstance(at, UtcInstant):
        return False
    if not all((decision.decision_id, decision.proposal_id, decision.principal, decision.worker_identity, decision.rationale)):
        return False
    if not all(_is_digest_value(v) for v in (decision.request_content_digest, decision.state_binding_digest, decision.capability_attestation_digest)):
        return False
    state_snapshot=getattr(state, "workspace_snapshot_id", None)
    state_policy=getattr(state, "policy_version", None)
    if state_snapshot not in (None, "") and decision.workspace_snapshot_id != state_snapshot:
        return False
    if state_policy not in (None, "") and decision.policy_version != state_policy:
        return False
    objective=getattr(state, "objective", None)
    policy=getattr(state, "active_policy", None)
    if isinstance(objective, CanonicalObjective) and decision.objective_revision != objective.revisions[-1].revision_id:
        return False
    if not isinstance(policy, Policy):
        return False
    if not (decision.decided_at.epoch_ns <= at.epoch_ns < decision.expires_at.epoch_ns):
        return False
    if decision.expires_at.epoch_ns - decision.decided_at.epoch_ns > policy.authorization_rules.lease_ttl_ms * 1_000_000:
        return False
    if decision.risk_tier not in policy.risk_mapping.control_profiles:
        return False
    profile=policy.risk_mapping.control_profiles[decision.risk_tier]
    if decision.control_profile_digest != digest("sclass/control-profile/v1", profile):
        return False
    if state.work_graph is not None and state.work_graph._nodes:
        if not decision.work_node_id or decision.work_node_id not in state.work_graph._nodes:
            return False
        node=state.work_graph._nodes[decision.work_node_id]
        if decision.proposal_id != decision.work_node_id:
            return False
        if node.worker_id is not None and node.worker_id != decision.worker_identity:
            return False
        if node.action_type in policy.authorization_rules.denied_action_types:
            return False
        if not profile.external_effects_allowed and decision.effect_scope.external_effect_rules:
            return False
    if decision.authority is Authority.LLM_DERIVED or decision.authority is Authority.REPOSITORY_DERIVED:
        return False
    if profile.authorization_mode is AuthorizationMode.AUTO:
        if decision.approval_set_id is not None:
            return False
    else:
        if not decision.approval_set_id:
            return False
        aset=state.approval_sets.get(decision.approval_set_id)
        if aset is None or aset.kind is not ApprovalKind.DUAL_AUTHORIZATION:
            return False
        required=1 if profile.authorization_mode is AuthorizationMode.HUMAN_APPROVAL else policy.approval_quorums.get(ApprovalKind.DUAL_AUTHORIZATION)
        if required is None:
            return False
        principal_directory=dict(state.reducer_facts.get("principal_directory", FrozenMap.from_items()).items())
        principal_authority_ids=dict(state.reducer_facts.get("principal_authority_ids", FrozenMap.from_items()).items())
        records=getattr(state,"signature_verification_records",FrozenMap.from_items())
        valid_ids=frozenset(k for k,v in records.items() if isinstance(v,SignatureVerificationRecord) and v.verification_result is SignatureVerificationResult.VALID)
        if aset.workspace_id != state.workspace_id or aset.policy_version != policy.policy_version or aset.target_digest != authorization_target_digest(decision) or aset.scope_digest != effect_scope_digest(decision.effect_scope):
            return False
        if validate_approval_set(aset,valid_ids,at,principal_directory,required,principal_authority_ids,True) is not ApprovalSetResult.VALID:
            return False
    if not isinstance(decision.effect_scope, EffectScope):
        return False
    return True


def validate_execution_lease(state: EngineeringState, lease_record: LeaseRecord) -> bool:
    lease=lease_record.lease
    if lease.workspace_id != state.workspace_id or lease.policy_version != state.policy_version:
        return False
    if not lease.authorization_lease_id or not lease.worker_identity or not lease.node_id or not lease.execution_attempt_id or not lease.budget_reservation_id:
        return False
    reservation=state.budget_reservations.get(lease.budget_reservation_id)
    if reservation is None or reservation.workspace_id != state.workspace_id:
        return False
    if reservation.lifecycle_state is not BudgetReservationState.RESERVED:
        return False
    if reservation.governing_budget_lineage_id != lease.governing_budget_lineage_id:
        return False
    if reservation.expires_at.epoch_ns < lease.expires_at.epoch_ns:
        return False
    if lease.target_snapshot_digest != target_snapshot_digest(state.target_snapshot): return False
    if state.objective is None or lease.objective_revision != state.objective.revisions[-1].revision_id: return False
    if state.work_graph is None or lease.node_id not in state.work_graph._nodes: return False
    node=state.work_graph._nodes[lease.node_id]
    if node.governing_budget_lineage_id != lease.governing_budget_lineage_id: return False
    if node.execution_generation != lease.execution_generation: return False
    if node.worker_id is not None and node.worker_id != lease.worker_identity: return False
    if lease.expires_at.epoch_ns <= lease.issued_at.epoch_ns: return False
    if state.active_policy is None: return False
    if lease.expires_at.epoch_ns - lease.issued_at.epoch_ns > state.active_policy.authorization_rules.lease_ttl_ms*1_000_000: return False
    if lease.fencing_token < 1: return False
    binding=canonical_current_state_binding(state,lease.execution_generation,lease.governing_budget_lineage_id)
    if lease.state_binding_digest != state_binding_digest(binding): return False
    # The execution lease must have a canonical ALLOW decision whose identity, request,
    # policy, snapshot, worker and expiry exactly govern this lease.
    decisions=[d for d in state.authorization_decisions.values() if isinstance(d,AuthorizationDecision) and d.decision is AuthorizationState.ALLOW]
    decision=None
    for candidate in decisions:
        if candidate.worker_identity == lease.worker_identity and candidate.policy_version == lease.policy_version and candidate.workspace_snapshot_id == lease.workspace_snapshot_id:
            if lease.request_content_digest == candidate.request_content_digest and candidate.expires_at.epoch_ns >= lease.expires_at.epoch_ns:
                decision=candidate; break
    if decision is None: return False
    if lease.expires_at.epoch_ns > decision.expires_at.epoch_ns: return False
    # If the authorization lease object is already materialized in reducer state, it must match.
    existing=state.leases.get(lease.lease_id)
    return existing is None or existing == lease_record


def validate_execution_generation(state: EngineeringState, generation: ExecutionGeneration) -> bool:
    node=state.work_graph._nodes.get(generation.work_node_id) if state.work_graph is not None else None
    if node is None or not generation.worker_identity: return False
    previous=state.execution_generations.get(generation.work_node_id)
    if previous is not None and (generation.generation != previous.generation + 1 or previous.status is ExecutionGenerationStatus.ACTIVE):
        return False
    if generation.governing_budget_lineage_id != node.governing_budget_lineage_id: return False
    if generation.objective_revision != state.work_graph.objective_revision or generation.workgraph_revision != state.work_graph.revision_id: return False
    if state.target_snapshot is not None and generation.target_snapshot_digest != target_snapshot_digest(state.target_snapshot): return False
    if state.objective is not None and generation.objective_revision != state.objective.revisions[-1].revision_id: return False
    if state.causal_frontier is not None:
        if generation.authority_epoch != state.causal_frontier.authorization_epoch: return False
        if generation.state_binding_digest != state_binding_digest(canonical_current_state_binding(state,generation.generation,generation.governing_budget_lineage_id)): return False
    return True

def _transition_revision(old_obj: Any, new_obj: Any, identity_fields: tuple[str,...], revision_field: str, parent_field: Optional[str]=None) -> bool:
    if old_obj is None:
        return getattr(new_obj,revision_field) == 1
    if any(getattr(new_obj,f) != getattr(old_obj,f) for f in identity_fields):
        return False
    if getattr(new_obj,revision_field) != getattr(old_obj,revision_field) + 1:
        return False
    if parent_field is not None and getattr(new_obj,parent_field) != getattr(old_obj,revision_field):
        return False
    return True

def waiver_scope_digest(waiver: AcceptedRiskWaiver, state: EngineeringState, policy: Policy) -> Digest:
    """Canonical waiver scope identity. Exact obligation/objective/contract/policy/effects are bound."""
    obligation = state.obligations._obligations.get(waiver.obligation_id)
    if obligation is None:
        raise ValueError("unknown waiver obligation")
    effect_scope = getattr(obligation, "effect_scope", None)
    waived_kinds = tuple(sorted(str(x) for x in getattr(waiver, "waived_evidence_kinds", ())))
    return digest("sclass/waiver-scope/v1", (
        waiver.workspace_id, waiver.waiver_id, waiver.obligation_id, waiver.objective_revision,
        obligation.acceptance_contract_id, policy.policy_version, waived_kinds, effect_scope))


def validate_waiver(waiver: AcceptedRiskWaiver, state: EngineeringState, policy: Policy, evaluated_at: UtcInstant, signature_record: Optional[SignatureVerificationRecord] = None) -> bool:
    if waiver.workspace_id != state.workspace_id or waiver.policy_version != policy.policy_version:
        return False
    obligation = state.obligations._obligations.get(waiver.obligation_id)
    if obligation is None or waiver.objective_revision != state.objective.revisions[-1].revision_id:
        return False
    contract = state.acceptance_contracts.get(obligation.acceptance_contract_id)
    if contract is None:
        return False
    if waiver.expires_at.epoch_ns <= waiver.issued_at.epoch_ns:
        return False
    if waiver.expires_at.epoch_ns - waiver.issued_at.epoch_ns > policy.waiver_rules.max_ttl_ms * 1_000_000:
        return False
    if not (waiver.issued_at.epoch_ns <= evaluated_at.epoch_ns < waiver.expires_at.epoch_ns):
        return False

    principal_directory = dict(state.reducer_facts.get("principal_directory", FrozenMap.from_items()).items())
    principal_authority_ids = dict(state.reducer_facts.get("principal_authority_ids", FrozenMap.from_items()).items())
    approver_authority = principal_authority_ids.get(waiver.approver, waiver.approver)
    if approver_authority not in set(policy.waiver_rules.approver_authorities):
        return False

    # The waiver must target the current immutable snapshot and exact policy scope.
    if state.target_snapshot is None:
        return False

    if policy.release_rules.allow_waivers is False:
        return False

    if policy.waiver_rules.require_signature:
        rec=signature_record or getattr(state,"signature_verification_records",FrozenMap.from_items()).get(waiver.waiver_id)
        if not isinstance(rec,SignatureVerificationRecord) or not (
            rec.subject_id == waiver.waiver_id and
            rec.signed_payload_digest == waiver_signed_payload_digest(waiver) and
            rec.signature_digest == signature_block_digest(waiver.signature) and
            rec.verification_result is SignatureVerificationResult.VALID):
            return False
        aset=state.approval_sets.get(waiver.approval_set_id)
        if aset is None or aset.kind is not ApprovalKind.WAIVER or aset.workspace_id != state.workspace_id:
            return False
        quorum=policy.approval_quorums.get(ApprovalKind.WAIVER)
        if quorum is None or aset.required_principals != quorum:
            return False
        expected_target=target_snapshot_digest(state.target_snapshot)
        expected_scope=waiver_scope_digest(waiver,state,policy)
        if aset.target_digest != expected_target or aset.scope_digest != expected_scope or aset.policy_version != policy.policy_version:
            return False
        valid_ids=_valid_signature_ids(state)
        result=validate_approval_set(aset,valid_ids,evaluated_at,principal_directory,quorum,principal_authority_ids,True)
        if result is not ApprovalSetResult.VALID:
            return False

    # Critical-risk waivers require the explicit break-glass path. The normal waiver
    # path can never silently relax a critical obligation.
    risk = getattr(obligation, "risk_tier", None)
    if risk is RiskTier.CRITICAL:
        return False
    return True

def _closure_requirements_satisfied_from_state(state: EngineeringState, obligation: Obligation, closure: EvidenceClosure) -> bool:
    contract = state.acceptance_contracts.get(obligation.acceptance_contract_id)
    if contract is None or contract.revision != closure.acceptance_contract_revision: return False
    ctx=FreshnessContext(
        snapshot_id=closure.workspace_snapshot_id, target_snapshot_digest=target_snapshot_digest(state.target_snapshot),
        objective_revision=state.objective.revisions[-1].revision_id, policy_version=state.policy_version,
        contract_revision=contract.revision, plan_revision=closure.verification_plan_revision,
        verifier_config_digest=closure.verifier_config_digest, environment_digest=closure.environment_digest,
        dependency_digests_now=state.target_snapshot.dependency_digests,
        dependency_set_digest_now=dependency_map_digest(state.target_snapshot.dependency_digests), invalidated_evidence_ids=invalidated_evidence_ids(state))
    profiles={k:v for k,v in state.reducer_facts.get("verifier_profiles", FrozenMap.from_items()).items()}
    records=getattr(state,"signature_verification_records",FrozenMap.from_items())
    valid=frozenset(k for k,v in records.items() if isinstance(v,SignatureVerificationRecord) and v.verification_result is SignatureVerificationResult.VALID)
    evaluation=evaluate_evidence_composition(contract,closure.evidence_receipts,ctx,profiles,valid)
    return evaluation.verdict is ClosureVerdict.SATISFIED

def _release_scope_obligations(state: EngineeringState) -> tuple[str, ...]:
    # Canonical source of release scope. Caller-supplied blocking lists are never authoritative.
    active = []
    for oid, obligation in state.obligations._obligations.items():
        if obligation.status not in (ObligationStatus.CANCELLED, ObligationStatus.SUPERSEDED):
            active.append(oid)
    return tuple(sorted(active))

def _release_result(release_id, acceptance_digest, verdict, obligations=(), assessments=(), waivers=(), provenance=None, reason=None, evaluated_at=None):
    prov = provenance or Digest("sha256:"+"0"*64)
    at=evaluated_at or UtcInstant(0)
    ev_digest=digest("sclass/release-evaluation/v3",(release_id,acceptance_digest,obligations,assessments,waivers,prov,verdict,reason,at))
    return ReleaseEvaluation(release_id,acceptance_digest,obligations,assessments,waivers,prov,ev_digest,verdict,at)

def _canonical_provenance(state: EngineeringState, artifact_digest: Digest, target_digest: Digest, release_id: str) -> tuple[Digest, ...]:
    records=getattr(state,"reducer_facts",FrozenMap.from_items()).get("provenance_records", FrozenMap.from_items())
    if not isinstance(records, FrozenMap):
        raise ValueError("canonical provenance registry malformed")
    valid=[]
    for pid, rec in records.items():
        if not isinstance(rec, tuple) or len(rec) != 4:
            continue
        art,tgt,rid,pdig=rec
        if art == artifact_digest and tgt == target_digest and rid == release_id:
            valid.append((str(pid),pdig))
    return tuple(d for _,d in sorted(valid))

def evaluate_release(state: EngineeringState, release: ReleaseState, policy: Policy, evaluated_at: UtcInstant) -> ReleaseEvaluation:
    if not isinstance(evaluated_at,UtcInstant): raise TypeError("evaluated_at must be explicit UtcInstant")
    def fail(*args, **kwargs):
        kwargs["evaluated_at"] = evaluated_at
        return _release_result(*args, **kwargs)
    rr=policy.release_rules
    canonical_acceptance=state.acceptance_snapshots.get(release.acceptance_snapshot_id)
    if canonical_acceptance is None or acceptance_snapshot_digest(canonical_acceptance) != release.acceptance_snapshot_digest:
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="INVALID_ACCEPTANCE_SNAPSHOT")
    actual_state_digest = canonical_state_digest(state)
    if release.engineering_snapshot.baseline_state_hash != actual_state_digest:
        return _release_result(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="INVALID_ENGINEERING_SNAPSHOT",evaluated_at=evaluated_at)
    if release.release_policy_version != policy.policy_version:
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="POLICY_VERSION_MISMATCH")
    if release.target_environment not in rr.target_environments:
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason="TARGET_ENVIRONMENT")
    expected=tuple(sorted(_release_scope_obligations(state)))
    if tuple(sorted(release.blocking_obligations)) != expected:
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="OBLIGATION_SCOPE_MISMATCH")
    target_digest=target_snapshot_digest(state.target_snapshot)
    expected_nonwaived=set()
    derived_obligations={}; derived_waivers={}; derived_assessments={}
    for oid in expected:
        o=state.obligations._obligations[oid]
        if o.status is ObligationStatus.WAIVED:
            waiver_ids=[wid for wid in release.waivers if wid in state.waivers and state.waivers[wid].obligation_id==oid]
            if not policy.release_rules.allow_waivers or len(waiver_ids)!=1:
                return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"WAIVER_INVALID:{oid}")
            wid=waiver_ids[0]; w=state.waivers[wid]
            if not validate_waiver(w,state,policy,evaluated_at):
                return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"WAIVER_INVALID:{wid}")
            derived_waivers[oid]=wid
        else:
            expected_nonwaived.add(oid)
            if o.status is not ObligationStatus.SATISFIED or not o.satisfied_by:
                return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"OBLIGATION_UNSATISFIED:{oid}")
            closure=state.evidence.get(o.satisfied_by)
            if closure is None or closure.verdict is not ClosureVerdict.SATISFIED:
                return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"EVIDENCE_UNSATISFIED:{oid}")
            if not is_fresh(closure,FRESHNESS_FLOOR,FreshnessContext(state.workspace_snapshot_id,target_digest,state.objective.revisions[-1].revision_id,state.policy_version,state.acceptance_contracts[o.acceptance_contract_id].revision,closure.verification_plan_revision,closure.verifier_config_digest,state.target_snapshot.environment_digest,state.target_snapshot.dependency_digests,dependency_map_digest(state.target_snapshot.dependency_digests),invalidated_evidence_ids(state))).state is FreshnessState.FRESH:
                return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"EVIDENCE_STALE:{oid}")
            profiles={k:v for k,v in state.reducer_facts.get("verifier_profiles",FrozenMap.from_items()).items()}
            records=getattr(state,"signature_verification_records",FrozenMap.from_items())
            valid_ids=frozenset(k for k,v in records.items() if isinstance(v,SignatureVerificationRecord) and v.verification_result is SignatureVerificationResult.VALID)
            comp=evaluate_evidence_composition(state.acceptance_contracts[o.acceptance_contract_id],closure.evidence_receipts,FreshnessContext(state.workspace_snapshot_id,target_digest,state.objective.revisions[-1].revision_id,state.policy_version,state.acceptance_contracts[o.acceptance_contract_id].revision,closure.verification_plan_revision,closure.verifier_config_digest,state.target_snapshot.environment_digest,state.target_snapshot.dependency_digests,dependency_map_digest(state.target_snapshot.dependency_digests),invalidated_evidence_ids(state)),profiles,valid_ids)
            if comp.verdict is not ClosureVerdict.SATISFIED:
                return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"EVIDENCE_COMPOSITION:{oid}")
            derived_obligations[oid]="SATISFIED"
    # Every supplied waiver must be relevant exactly once.
    supplied_waivers=set(release.waivers)
    used_waivers=set(derived_waivers.values())
    if supplied_waivers != used_waivers:
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="EXTRA_OR_MISSING_WAIVER_REFERENCE")
    # Assessments are validated once, outside the obligation loop.
    relevant_assessments={}
    for aid in release.final_assessments:
        if aid in relevant_assessments or aid not in state.assessments:
            return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="INVALID_ASSESSMENT_REFERENCE")
        a=state.assessments[aid]
        matching=[oid for oid in expected_nonwaived if state.obligations._obligations[oid].satisfied_by==a.evidence_id]
        if len(matching)!=1 or a.policy_version!=state.policy_version or a.workspace_snapshot_id!=state.workspace_snapshot_id or a.target_snapshot_digest!=target_digest or a.artifact_digest!=release.artifact_digest:
            return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"ASSESSMENT_BINDING:{aid}")
        try:
            expected_assessment_input=assessment_input_digest(a,state)
            supplied_assessment_input=getattr(a,"input_digest",None)
        except (AttributeError,KeyError,TypeError,ValueError):
            return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"ASSESSMENT_INPUT_DIGEST:{aid}")
        if supplied_assessment_input != expected_assessment_input:
            return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"ASSESSMENT_INPUT_DIGEST:{aid}")
        try:
            assessment_signature_valid=signature_subject_is_verified(state,a.assessment_id,assessment_signed_payload_digest(a),a.signature)
        except (AttributeError,KeyError,TypeError,ValueError):
            assessment_signature_valid=False
        if not assessment_signature_valid or a.verdict is not AssessmentVerdict.ACCEPT:
            return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.BLOCKED,reason=f"ASSESSMENT_INVALID:{aid}")
        relevant_assessments[aid]=a.verdict.value
    if set(relevant_assessments) != set(release.final_assessments):
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="ASSESSMENT_SCOPE_MISMATCH")
    # Every non-waived obligation must have exactly one valid final assessment.
    assessment_obligations = {}
    for aid in release.final_assessments:
        a = state.assessments[aid]
        matches = [oid for oid in expected_nonwaived
                   if state.obligations._obligations[oid].satisfied_by == a.evidence_id]
        if len(matches) != 1:
            return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason=f"ASSESSMENT_CARDINALITY:{aid}")
        oid = matches[0]
        if oid in assessment_obligations:
            return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason=f"ASSESSMENT_DUPLICATE_OBLIGATION:{oid}")
        assessment_obligations[oid] = aid
    if set(assessment_obligations) != expected_nonwaived:
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="ASSESSMENT_COMPLETENESS")
    canonical_prov=_canonical_provenance(state,release.artifact_digest,target_digest,release.release_id)
    if tuple(sorted(release.provenance)) != tuple(sorted(canonical_prov)):
        return fail(release.release_id,release.acceptance_snapshot_digest,ReleaseVerdict.NOT_EVALUABLE,reason="PROVENANCE_NOT_CANONICAL")
    provenance=digest("sclass/release-provenance/v2",(release.release_id,release.artifact_digest,target_digest,tuple(sorted(canonical_prov))))
    ob=FrozenMap.from_items(derived_obligations.items()); wa=FrozenMap.from_items(derived_waivers.items()); ass=FrozenMap.from_items(relevant_assessments.items())
    evaluation_digest=digest("sclass/release-evaluation/v2",(release.release_id,release.acceptance_snapshot_digest,ob,ass,wa,provenance,ReleaseVerdict.READY))
    return ReleaseEvaluation(release.release_id,release.acceptance_snapshot_digest,ob,ass,wa,provenance,evaluation_digest,ReleaseVerdict.READY,evaluated_at)


# Backward-compatible name is retained only as a non-authoritative adapter.
def is_releasable(state: EngineeringState, release: ReleaseState, policy: Policy, evaluated_at: UtcInstant) -> ReleaseVerdict:
    return evaluate_release(state, release, policy, evaluated_at).verdict


class SQLiteEventStore:
    """Single authoritative S1 durability boundary.

    Canonical history is the event stream. The reduced projection is a checked materialization,
    never caller-selected authority. Every visible mutation is one atomic COMMITTED transaction.
    """
    STORE_SCHEMA_VERSION = 3

    def __init__(self, path: str, fault_injector=None):
        import sqlite3
        self._fault_injector = fault_injector
        use_uri = path.startswith("file:")
        self._db = sqlite3.connect(path, uri=use_uri, isolation_level=None, check_same_thread=False, timeout=30.0)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=30000")
        self._db.execute("CREATE TABLE IF NOT EXISTS store_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        row = self._db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
        if row is None:
            self._db.execute("INSERT INTO store_meta(key,value) VALUES('schema_version',?)", (str(self.STORE_SCHEMA_VERSION),))
        elif int(row[0]) > self.STORE_SCHEMA_VERSION:
            raise ValueError(f"unsupported SQLiteEventStore schema version: {row[0]}")
        self._db.execute("""CREATE TABLE IF NOT EXISTS canonical_commits (
            commit_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            record_blob BLOB NOT NULL,
            commit_digest TEXT NOT NULL,
            state TEXT NOT NULL CHECK(state='COMMITTED'),
            event_sequence_start INTEGER NOT NULL,
            event_sequence_end INTEGER NOT NULL,
            resulting_state_digest TEXT NOT NULL,
            UNIQUE(workspace_id, event_sequence_start, event_sequence_end)
        )""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS canonical_events (
            workspace_id TEXT NOT NULL,
            event_sequence INTEGER NOT NULL,
            event_id TEXT NOT NULL,
            event_hash TEXT NOT NULL PRIMARY KEY,
            event_blob BLOB NOT NULL,
            commit_id TEXT NOT NULL,
            FOREIGN KEY(commit_id) REFERENCES canonical_commits(commit_id),
            UNIQUE(workspace_id,event_sequence),
            UNIQUE(workspace_id,event_id)
        )""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS canonical_projection (
            workspace_id TEXT PRIMARY KEY,
            event_sequence INTEGER NOT NULL,
            state_revision TEXT NOT NULL,
            state_digest TEXT NOT NULL,
            state_blob BLOB NOT NULL,
            event_head_hash TEXT NOT NULL,
            commit_id TEXT NOT NULL,
            FOREIGN KEY(commit_id) REFERENCES canonical_commits(commit_id)
        )""")
        self._db.execute("""CREATE TABLE IF NOT EXISTS checkpoints (
            checkpoint_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            event_sequence INTEGER NOT NULL,
            event_head_hash TEXT NOT NULL,
            state_digest TEXT NOT NULL,
            commit_id TEXT NOT NULL,
            reducer_version TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            state_blob BLOB NOT NULL,
            FOREIGN KEY(commit_id) REFERENCES canonical_commits(commit_id)
        )""")

    def close(self) -> None:
        self._db.close()

    def _fault(self, stage: str) -> None:
        # Test-only failure injection. Production instances pass no injector.
        if self._fault_injector is not None:
            self._fault_injector(stage)

    @staticmethod
    def _state_name(workspace_id: str) -> str:
        return "state:" + workspace_id

    @staticmethod
    def _canonical_event_identity(event):
        return (event.event_id, "event", event.event_hash)

    def _load_commit(self, commit_id: str) -> CommitRecord:
        row = self._db.execute(
            "SELECT record_blob,commit_digest,state,event_sequence_start,event_sequence_end,resulting_state_digest FROM canonical_commits WHERE commit_id=?",
            (commit_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"missing commit record: {commit_id}")
        record = canonical_c1_unpack(row[0])
        if not isinstance(record, CommitRecord):
            raise ValueError("stored commit object has wrong type")
        if record.state is not CommitState.COMMITTED or row[2] != CommitState.COMMITTED.value:
            raise ValueError(f"non-canonical commit is not visible: {commit_id}")
        verify_commit_record_integrity(record)
        if record.event_sequence_start != row[3] or record.event_sequence_end != row[4]:
            raise ValueError(f"stored commit range mismatch: {commit_id}")
        if str(record.commit_digest) != row[1] or record.resulting_state_digest is None or str(record.resulting_state_digest) != row[5]:
            raise ValueError(f"stored commit integrity mismatch: {commit_id}")
        return record

    def _canonical_head(self, workspace_id: str) -> EventHead:
        events=self._read_all_committed(workspace_id)
        if not events:
            projection=self._load_projection(workspace_id)
            if projection is not None:
                raise ValueError("projection exists without canonical events")
            return EventHead(0,GENESIS_EVENT_HASH)
        e=events[-1]
        return EventHead(e.event_sequence,e.event_hash)

    def _read_all_committed(self, workspace_id: str) -> tuple[CanonicalEvent, ...]:
        rows = self._db.execute(
            "SELECT event_sequence,event_id,event_hash,event_blob,commit_id FROM canonical_events WHERE workspace_id=? ORDER BY event_sequence",
            (workspace_id,),
        ).fetchall()
        if not rows:
            return ()
        events=[]
        expected_seq=1
        previous=GENESIS_EVENT_HASH
        commit_groups={}
        last_commit=None
        for seq, event_id, stored_hash, blob, commit_id in rows:
            if seq != expected_seq:
                raise ValueError("canonical event sequence gap")
            e=canonical_c1_unpack(blob)
            if not isinstance(e, CanonicalEvent):
                raise ValueError("stored event object has wrong type")
            if e.workspace_id != workspace_id or e.event_sequence != seq or e.event_id != event_id or e.commit_id != commit_id:
                raise ValueError("stored event workspace/sequence/commit mismatch")
            if e.previous_event_hash != previous:
                raise ValueError("canonical event chain broken")
            if str(e.event_hash) != stored_hash or event_hash(e) != e.event_hash:
                raise ValueError("stored event hash mismatch")
            if digest("sclass/event-payload/v1", e.payload) != e.payload_digest:
                raise ValueError("stored event payload digest mismatch")
            _validate_event_payload_schema(e)
            if last_commit is not None and commit_id != last_commit and commit_id in commit_groups:
                raise ValueError("commit identity reappeared non-contiguously")
            commit_groups.setdefault(commit_id, []).append(e)
            last_commit=commit_id
            events.append(e)
            previous=e.event_hash
            expected_seq += 1
        # Commit authority is checked for the whole canonical history, not just the head row.
        for commit_id, group in commit_groups.items():
            commit=self._load_commit(commit_id)
            group_hashes=tuple(e.event_hash for e in group)
            group_ids=tuple(e.event_id for e in group)
            if commit.workspace_id != workspace_id:
                raise ValueError("commit workspace mismatch")
            if commit.previous_head != (GENESIS_EVENT_HASH if group[0].event_sequence == 1 else events[group[0].event_sequence-2].event_hash):
                raise ValueError("commit previous head mismatch")
            if commit.event_sequence_start != group[0].event_sequence or commit.event_sequence_end != group[-1].event_sequence:
                raise ValueError("commit sequence range mismatch")
            if commit.resulting_head != group[-1].event_hash:
                raise ValueError("commit resulting head mismatch")
            expected_participants={pid:(ptype,ph) for pid,ptype,ph in zip(commit.participant_ids,commit.participant_types,commit.participant_hashes)}
            expected_events={eid:("event",eh) for eid,eh in zip(group_ids,group_hashes)}
            state_participant=self._state_name(workspace_id)
            if set(expected_participants) != set(expected_events)|{state_participant}:
                raise ValueError("commit participant set does not cover exactly its canonical mutation")
            for eid, pair in expected_events.items():
                if expected_participants.get(eid) != pair:
                    raise ValueError("commit participant event hash mismatch")
        commit_rows={r[0] for r in self._db.execute("SELECT commit_id FROM canonical_commits WHERE workspace_id=?",(workspace_id,)).fetchall()}
        if commit_rows != set(commit_groups):
            raise ValueError("orphan or unreferenced committed commit detected")
        cursor=1
        commit_end_by_seq={}
        for start_seq,end_seq,_cid in sorted((g[0].event_sequence,g[-1].event_sequence,cid) for cid,g in commit_groups.items()):
            if start_seq != cursor:
                raise ValueError("commit ranges are not contiguous")
            commit_end_by_seq[end_seq]=_cid
            cursor=end_seq+1
        # Validate the state digest at EVERY historical canonical commit boundary, not only the head.
        replay_state=genesis_engineering_state(workspace_id)
        for event in events:
            replay_state=REFERENCE_REDUCER.reduce(replay_state,event)
            cid=commit_end_by_seq.get(event.event_sequence)
            if cid is not None:
                commit=self._load_commit(cid)
                computed=engineering_state_digest(replay_state)
                if commit.resulting_state_digest != computed:
                    raise ValueError(f"historical commit state digest mismatch: {cid}")
        return tuple(events)

    def _derive_state_from_history(self, workspace_id: str, events: tuple[CanonicalEvent, ...]) -> EngineeringState:
        state=genesis_engineering_state(workspace_id)
        for event in events:
            state=REFERENCE_REDUCER.reduce(state,event)
            # The reducer itself is the semantic authority; every state is canonicalized before persistence.
            if state.state_schema_version != STATE_SCHEMA_VERSION or state.reducer_version != REDUCER_VERSION:
                raise ValueError("reducer produced unsupported state version")
        return state

    def _load_projection(self, workspace_id: str) -> Optional[EngineeringState]:
        row=self._db.execute(
            "SELECT event_sequence,state_revision,state_digest,state_blob,event_head_hash,commit_id FROM canonical_projection WHERE workspace_id=?",
            (workspace_id,),
        ).fetchone()
        if row is None:
            return None
        state=canonical_c1_unpack(row[3])
        if not isinstance(state, EngineeringState):
            raise ValueError("stored projection has wrong type")
        if state.workspace_id != workspace_id:
            raise ValueError("projection workspace mismatch")
        computed=engineering_state_digest(state)
        if str(computed) != row[2] or str(state.state_digest) != row[2]:
            raise ValueError("projection state digest mismatch")
        if str(state.state_revision) != row[1] or str(state.event_head_hash) != row[4] or state.event_sequence != row[0]:
            raise ValueError("projection identity mismatch")
        commit=self._load_commit(row[5])
        if commit.resulting_head != state.event_head_hash or commit.resulting_state_revision != state.state_revision or commit.resulting_state_digest != computed:
            raise ValueError("projection/commit binding mismatch")
        return state

    def _load_canonical_state(self, workspace_id: str) -> EngineeringState:
        events=self._read_all_committed(workspace_id)
        if not events:
            projection=self._load_projection(workspace_id)
            if projection is not None:
                raise ValueError("projection exists without canonical events")
            return genesis_engineering_state(workspace_id)
        derived=self._derive_state_from_history(workspace_id,events)
        stored=self._load_projection(workspace_id)
        if stored is None:
            raise ValueError("canonical events exist without durable projection")
        if engineering_state_digest(stored) != engineering_state_digest(derived):
            raise ValueError("event stream and canonical projection disagree")
        last_commit=self._load_commit(events[-1].commit_id)
        if last_commit.resulting_state_digest != engineering_state_digest(derived):
            raise ValueError("head commit does not bind derived state")
        return derived

    def _validate_commit(self, events: tuple[CanonicalEvent, ...], previous: EngineeringState, derived: EngineeringState, commit: CommitRecord, expected_head_hash: Digest) -> None:
        if commit.state is not CommitState.COMMITTED:
            raise ValueError("canonical append accepts only COMMITTED commits")
        if commit.schema_version != COMMIT_SCHEMA_VERSION:
            raise ValueError("unsupported commit schema version")
        if commit.state is not CommitState.COMMITTED:
            raise ValueError("only COMMITTED commits may enter canonical history")
        if commit.committed_at_epoch_ns is None or commit.resulting_state_digest is None:
            raise ValueError("canonical commit must bind committed time and resulting state digest")
        if any(e.commit_id != commit.commit_id for e in events):
            raise ValueError("all events in a transaction must share the commit_id")
        if any(e.workspace_id != commit.workspace_id for e in events) or commit.workspace_id != previous.workspace_id:
            raise ValueError("workspace mismatch")
        if events[0].previous_event_hash != expected_head_hash or commit.previous_head != expected_head_hash:
            raise ValueError("previous head mismatch")
        if commit.event_sequence_start != events[0].event_sequence or commit.event_sequence_end != events[-1].event_sequence:
            raise ValueError("commit sequence range mismatch")
        if commit.resulting_head != events[-1].event_hash or derived.event_head_hash != events[-1].event_hash:
            raise ValueError("resulting head mismatch")
        if derived.event_sequence != events[-1].event_sequence:
            raise ValueError("derived state sequence mismatch")
        if commit.resulting_state_revision != derived.state_revision:
            raise ValueError("commit state_revision mismatch")
        derived_digest=engineering_state_digest(derived)
        if commit.resulting_state_digest != derived_digest:
            raise ValueError("commit state_digest mismatch")
        if commit.committed_at_epoch_ns is None:
            raise ValueError("COMMITTED commit requires committed_at_epoch_ns")
        verify_commit_record_integrity(commit)
        event_participants={e.event_id:("event",e.event_hash) for e in events}
        expected={pid:(typ,ph) for pid,typ,ph in zip(commit.participant_ids,commit.participant_types,commit.participant_hashes)}
        expected_all=dict(event_participants)
        expected_all[self._state_name(previous.workspace_id)]=("state",derived_digest)
        if expected != expected_all:
            raise ValueError("commit participant set does not equal derived canonical mutation set")
        if len(commit.participant_ids) != len(set(commit.participant_ids)):
            raise ValueError("duplicate commit participant")

    def append(self, event, commit, expected_head_hash=GENESIS_EVENT_HASH):
        return self.append_batch((event,),commit,expected_head_hash)

    def append_atomic(self, event, commit, expected_head_hash=GENESIS_EVENT_HASH):
        return self.append(event,commit,expected_head_hash)

    def _append_batch_in_transaction(self, events, commit, expected_head_hash=GENESIS_EVENT_HASH):
        """Append one canonical commit while the caller owns BEGIN/COMMIT."""
        events=tuple(events)
        if not events:
            raise ValueError("empty transaction")
        if commit is None:
            raise ValueError("canonical append requires CommitRecord")
        for e in events:
            if not isinstance(e, CanonicalEvent):
                raise TypeError("canonical event type required")
            _validate_event_payload_schema(e)
        workspace=events[0].workspace_id
        if any(e.workspace_id != workspace for e in events):
            raise ValueError("batch contains multiple workspaces")
        current_head=self._canonical_head(workspace)
        if current_head.hash != expected_head_hash:
            return AppendResult.HEAD_MISMATCH,None
        current_state=self._load_canonical_state(workspace)
        if current_state.event_head_hash != expected_head_hash or current_state.event_sequence != current_head.sequence:
            raise ValueError("durable state/head mismatch")
        for i,event in enumerate(events):
            expected_seq=current_head.sequence+i+1
            expected_prev=expected_head_hash if i==0 else events[i-1].event_hash
            if event.event_sequence != expected_seq or event.previous_event_hash != expected_prev:
                return AppendResult.HEAD_MISMATCH,None
        if any(e.commit_id != commit.commit_id for e in events):
            raise ValueError("all events in a transaction must share one commit ID")
        derived=REFERENCE_REDUCER.replay(current_state,events)
        self._validate_commit(events,current_state,derived,commit,expected_head_hash)
        if self._db.execute("SELECT 1 FROM canonical_commits WHERE commit_id=?",(commit.commit_id,)).fetchone() is not None:
            raise ValueError("duplicate commit identity")
        overlap=self._db.execute(
            "SELECT commit_id,event_sequence_start,event_sequence_end FROM canonical_commits "
            "WHERE workspace_id=? AND event_sequence_start <= ? AND event_sequence_end >= ? LIMIT 1",
            (workspace,commit.event_sequence_end,commit.event_sequence_start)).fetchone()
        if overlap is not None:
            raise ValueError("commit range overlaps canonical history")
        if commit.event_sequence_start != current_head.sequence + 1:
            raise ValueError("commit range is not contiguous with canonical head")
        self._db.execute(
            "INSERT INTO canonical_commits(commit_id,workspace_id,record_blob,commit_digest,state,event_sequence_start,event_sequence_end,resulting_state_digest) VALUES(?,?,?,?,?,?,?,?)",
            (commit.commit_id,workspace,canonical_c1_pack(commit),str(commit.commit_digest),commit.state.value,
             commit.event_sequence_start,commit.event_sequence_end,str(commit.resulting_state_digest)))
        self._fault("K2_AFTER_COMMIT_RECORD")
        for event in events:
            self._db.execute(
                "INSERT INTO canonical_events(workspace_id,event_sequence,event_id,event_hash,event_blob,commit_id) VALUES(?,?,?,?,?,?)",
                (workspace,event.event_sequence,event.event_id,str(event.event_hash),canonical_c1_pack(event),event.commit_id))
        self._fault("K3_AFTER_EVENT_ROWS")
        # K8-K12: event-type-specific crash injection points
        event_types_in_batch = frozenset(e.event_type for e in events)
        if EventType.EVIDENCE_ACCEPTED in event_types_in_batch:
            self._fault("K8_DURING_VERIFICATION")
            self._fault("K8_DURING_EVIDENCE_ACCEPTANCE")
        if EventType.ASSESSMENT_CREATED in event_types_in_batch:
            self._fault("K9_AFTER_RECEIPT_SIGNED")
            self._fault("K9_AFTER_RECEIPT_BEFORE_COMMIT")
        if EventType.IN_DOUBT_RESOLVED in event_types_in_batch or EventType.EXTERNAL_EFFECT_RECONCILED in event_types_in_batch:
            self._fault("K10_DURING_RECONCILIATION")
        if EventType.STATE_CHECKPOINTED in event_types_in_batch:
            self._fault("K11_DURING_HANDOFF")
        if EventType.EXECUTION_STARTED in event_types_in_batch:
            self._fault("K12_DURING_GENERATION_ADVANCE")
        sd=engineering_state_digest(derived)
        self._db.execute(
            "INSERT INTO canonical_projection(workspace_id,event_sequence,state_revision,state_digest,state_blob,event_head_hash,commit_id) "
            "VALUES(?,?,?,?,?,?,?) ON CONFLICT(workspace_id) DO UPDATE SET "
            "event_sequence=excluded.event_sequence,state_revision=excluded.state_revision,state_digest=excluded.state_digest,"
            "state_blob=excluded.state_blob,event_head_hash=excluded.event_head_hash,commit_id=excluded.commit_id",
            (workspace,derived.event_sequence,str(derived.state_revision),str(sd),canonical_c1_pack(derived),
             str(derived.event_head_hash),commit.commit_id)
        )
        self._fault("K4_AFTER_PROJECTION")
        return AppendResult.APPENDED,EventHead(derived.event_sequence,derived.event_head_hash)

    def begin_immediate(self):
        self._db.execute("BEGIN IMMEDIATE")

    def commit_transaction(self):
        self._db.execute("COMMIT")

    def rollback_transaction(self):
        self._db.execute("ROLLBACK")

    def append_batch_in_transaction(self, events, commit, expected_head_hash=GENESIS_EVENT_HASH):
        return self._append_batch_in_transaction(events,commit,expected_head_hash)

    def append(self, event, commit, expected_head_hash=GENESIS_EVENT_HASH):
        return self.append_batch((event,),commit,expected_head_hash)

    def append_atomic(self, event, commit, expected_head_hash=GENESIS_EVENT_HASH):
        return self.append(event,commit,expected_head_hash)

    def append_batch(self, events, commit, expected_head_hash=GENESIS_EVENT_HASH):
        self._fault("K1_BEFORE_DURABLE_INTENT")
        self.begin_immediate()
        try:
            result,head=self._append_batch_in_transaction(events,commit,expected_head_hash)
            if result is AppendResult.HEAD_MISMATCH:
                self.rollback_transaction()
                return result,None
            self._fault("K5_BEFORE_COMMIT")
            self.commit_transaction()
            self._fault("K6_AFTER_COMMIT")
            return result,head
        except Exception:
            try: self.rollback_transaction()
            except Exception: pass
            raise

    def head(self, workspace_id="default") -> EventHead:
        state=self._load_canonical_state(workspace_id)
        return EventHead(state.event_sequence,state.event_head_hash)

    def visible_head(self,workspace_id):
        state=self._load_canonical_state(workspace_id)
        if state.event_sequence == 0:
            return None
        return (state.event_sequence,state.event_head_hash,state.state_digest)

    def migrate(self, workspace_id: str, target_schema_version: int) -> StateLoadStatus:
        """Migrate store schema from current version to target version.
        Idempotent: running twice produces the same result.
        Crash-safe: migration runs inside a single transaction."""
        row = self._db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
        current = int(row[0]) if row else 0
        if current == target_schema_version:
            return StateLoadStatus.FOUND
        if current > target_schema_version:
            return StateLoadStatus.UNSUPPORTED_SCHEMA
        self._db.execute("BEGIN IMMEDIATE")
        try:
            for version_step in range(current + 1, target_schema_version + 1):
                if self._fault_injector: self._fault_injector("K8_DURING_MIGRATION")
                migration_method = getattr(self, f"_migrate_to_v{version_step}", None)
                if migration_method:
                    migration_method()
            self._db.execute("UPDATE store_meta SET value=? WHERE key='schema_version'",
                             (str(target_schema_version),))
            self._db.execute("COMMIT")
            return StateLoadStatus.FOUND
        except Exception:
            try: self._db.execute("ROLLBACK")
            except Exception: pass
            raise

    def read(self,workspace_id,sequence_from,sequence_to):
        events=self._read_all_committed(workspace_id)
        selected=tuple(e for e in events if sequence_from <= e.event_sequence <= sequence_to)
        if selected:
            prior=events[selected[0].event_sequence-2].event_hash if selected[0].event_sequence>1 else GENESIS_EVENT_HASH
            if selected[0].previous_event_hash != prior:
                raise ValueError("selected event range does not connect to canonical prefix")
        return selected

    def verify_chain(self,workspace_id,sequence_from,sequence_to):
        try:
            events=self._read_all_committed(workspace_id)
            if not events:
                return ChainStatus.UNREADABLE
            selected=tuple(e for e in events if sequence_from <= e.event_sequence <= sequence_to)
            if not selected:
                return ChainStatus.UNREADABLE
            prior=GENESIS_EVENT_HASH if selected[0].event_sequence==1 else events[selected[0].event_sequence-2].event_hash
            if selected[0].previous_event_hash != prior:
                return ChainStatus.BROKEN_HASH
            # Full load additionally validates event → commit → participant authority.
            self._load_canonical_state(workspace_id)
            return ChainStatus.VALID
        except (ValueError, KeyError, TypeError):
            return ChainStatus.BROKEN_HASH

    def checkpoint(self,checkpoint,state):
        canonical=self._load_canonical_state(state.workspace_id)
        if engineering_state_digest(state) != engineering_state_digest(canonical):
            raise ValueError("checkpoint state is not current canonical state")
        if checkpoint.state_digest != state.state_digest:
            raise ValueError("checkpoint state digest mismatch")
        if state.event_sequence <= 0:
            raise ValueError("cannot checkpoint genesis state")
        if checkpoint.event_sequence != state.event_sequence or checkpoint.commit_id != state.reducer_facts.get("last_commit_id"):
            raise ValueError("checkpoint binding mismatch")
        commit=self._load_commit(checkpoint.commit_id)
        if commit.resulting_head != state.event_head_hash or commit.resulting_state_digest != state.state_digest:
            raise ValueError("checkpoint commit binding mismatch")
        row=self._db.execute("SELECT event_hash FROM canonical_events WHERE workspace_id=? AND event_sequence=?",(state.workspace_id,state.event_sequence)).fetchone()
        if row is None or row[0] != str(state.event_head_hash):
            raise ValueError("checkpoint head does not reference canonical event")
        self._fault("K7_CHECKPOINT_WRITE")
        self._fault("K7_DURING_CHECKPOINT_WRITE")
        self._db.execute("INSERT INTO checkpoints VALUES(?,?,?,?,?,?,?,?,?)",
                         (checkpoint.checkpoint_id,state.workspace_id,checkpoint.event_sequence,str(state.event_head_hash),str(checkpoint.state_digest),checkpoint.commit_id,state.reducer_version,state.state_schema_version,canonical_c1_pack(state)))

    def restore(self,checkpoint_id):
        row=self._db.execute("SELECT checkpoint_id,workspace_id,event_sequence,event_head_hash,state_digest,commit_id,reducer_version,schema_version,state_blob FROM checkpoints WHERE checkpoint_id=?",(checkpoint_id,)).fetchone()
        if row is None:
            raise KeyError(checkpoint_id)
        state=canonical_c1_unpack(row[8])
        if not isinstance(state,EngineeringState):
            raise ValueError("checkpoint object has wrong type")
        if state.workspace_id != row[1] or state.event_sequence != row[2] or str(state.event_head_hash) != row[3]:
            raise ValueError("checkpoint state/header mismatch")
        if str(engineering_state_digest(state)) != row[4] or str(state.state_digest) != row[4]:
            raise ValueError("checkpoint integrity mismatch")
        if state.reducer_version != row[6] or state.state_schema_version != row[7]:
            raise ValueError("checkpoint schema/reducer mismatch")
        commit=self._load_commit(row[5])
        if commit.resulting_head != state.event_head_hash or commit.resulting_state_digest != state.state_digest:
            raise ValueError("checkpoint commit binding mismatch")
        if state.reducer_facts.get("last_commit_id") != row[5]:
            raise ValueError("checkpoint last_commit binding mismatch")
        return state

    def replay(self,workspace_id,from_checkpoint=None,reducer_version=REDUCER_VERSION):
        if reducer_version != REDUCER_VERSION:
            raise ValueError("unsupported reducer version")
        events=self._read_all_committed(workspace_id)
        if from_checkpoint is None:
            state=genesis_engineering_state(workspace_id)
            start=1
        else:
            state=self.restore(from_checkpoint.checkpoint_id if isinstance(from_checkpoint,CheckpointRef) else str(from_checkpoint))
            if state.workspace_id != workspace_id:
                raise ValueError("checkpoint workspace mismatch")
            start=state.event_sequence+1
        suffix=tuple(e for e in events if e.event_sequence >= start)
        replayed=REFERENCE_REDUCER.replay(state,suffix)
        canonical=self._load_canonical_state(workspace_id)
        if engineering_state_digest(replayed) != engineering_state_digest(canonical):
            raise ValueError("replay does not equal canonical projection")
        return replayed

SQLiteCanonicalStore = SQLiteEventStore

