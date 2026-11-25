"""Shared F10 protocol validation, L992 resource limits, and ApprovalSet helpers."""
from __future__ import annotations

import hashlib
import json
import math
import pathlib
import sys
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Tuple

try:
    from sclass_semantics_v6_0_1 import (
        ApprovalKind,
        ApprovalRecord,
        ApprovalSet,
        ApprovalSetResult,
        Digest,
        SignatureBlock,
        UtcInstant,
        validate_approval_set,
    )
except ImportError:
    _conf_dir = pathlib.Path(__file__).resolve().parents[3] / "10-CONFORMANCE"
    if _conf_dir.is_dir() and str(_conf_dir) not in sys.path:
        sys.path.insert(0, str(_conf_dir))
    from sclass_semantics_v6_0_1 import (
        ApprovalKind,
        ApprovalRecord,
        ApprovalSet,
        ApprovalSetResult,
        Digest,
        SignatureBlock,
        UtcInstant,
        validate_approval_set,
    )

# Master F10 L992 default adapter resource limits
DEFAULT_RESOURCE_LIMITS: Mapping[str, Any] = MappingProxyType({
    "latency_soft_s": 60.0,
    "cpu_s": 60.0,
    "memory_bytes": 1073741824,  # 1 GiB
    "tokens": 200000,
    "max_executions": 4,
    "hard_stop_s": 120.0,
})


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_sha256_json(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def validate_resource_limits(
    limits: Any,
    *,
    policy_override_authorized: bool = False,
) -> Tuple[bool, Tuple[str, ...]]:
    """Validate L992 resource limits; absent/zero/negative/unbounded => unqualified PD-F10-004."""
    if not isinstance(limits, Mapping) or not limits:
        return False, ("MISSING_RESOURCE_LIMITS",)

    required = ("latency_soft_s", "cpu_s", "memory_bytes", "tokens", "max_executions", "hard_stop_s")
    int_only = {"memory_bytes", "tokens", "max_executions"}
    reasons: List[str] = []

    for k in required:
        if k not in limits or limits[k] is None:
            reasons.append(f"MISSING_LIMIT:{k}")
            continue
        val = limits[k]
        if type(val) is bool:
            reasons.append(f"INVALID_LIMIT_TYPE:{k}")
            continue
        if k in int_only:
            if type(val) is not int:
                reasons.append(f"INVALID_LIMIT_TYPE:{k}")
                continue
        elif type(val) not in (int, float):
            reasons.append(f"INVALID_LIMIT_TYPE:{k}")
            continue
        if math.isnan(float(val)) or math.isinf(float(val)) or val <= 0:
            reasons.append(f"NON_POSITIVE_OR_UNBOUNDED_LIMIT:{k}")
            continue
        if not policy_override_authorized and val > DEFAULT_RESOURCE_LIMITS[k]:
            reasons.append(f"LIMIT_EXCEEDS_DEFAULT_WITHOUT_OVERRIDE:{k}")

    return len(reasons) == 0, tuple(reasons)


def build_approval_context_payload(
    *,
    requester_principal_id: str,
    approver_principal_id: str,
    approver_role: str = "security-reviewer",
    adapter_digest: str,
    approval_id: str = "APR-S2-1",
    set_id: str = "ASET-S2-1",
    workspace_id: str = "ws-s2",
    policy_version: str = "1.0",
    target_digest: Optional[str] = None,
    scope_digest: Optional[str] = None,
    issued_epoch_ns: int = 1_700_000_000_000_000_000,
    expires_epoch_ns: int = 1_900_000_000_000_000_000,
    at_epoch_ns: int = 1_750_000_000_000_000_000,
) -> Dict[str, Any]:
    """Construct canonical ApprovalSet + verification context for non-agent adapter registration."""
    t_dig = target_digest or (adapter_digest if adapter_digest.startswith("sha256:") else f"sha256:{'a'*64}")
    s_dig = scope_digest or f"sha256:{hashlib.sha256(b'adapter-registration').hexdigest()}"
    approval_set = {
        "set_id": set_id,
        "kind": ApprovalKind.RELEASE.value,
        "workspace_id": workspace_id,
        "target_digest": t_dig,
        "policy_version": policy_version,
        "scope_digest": s_dig,
        "required_principals": 1,
        "requester_principal_id": requester_principal_id,
        "approvals": [
            {
                "approval_id": approval_id,
                "kind": ApprovalKind.RELEASE.value,
                "principal_id": approver_principal_id,
                "principal_role": approver_role,
                "workspace_id": workspace_id,
                "target_digest": t_dig,
                "policy_version": policy_version,
                "scope_digest": s_dig,
                "issued_at_ns": issued_epoch_ns,
                "expires_at_ns": expires_epoch_ns,
                "signature": {
                    "algorithm": "ed25519",
                    "key_id": f"key-{approver_principal_id}",
                    "trust_root": "sclass-root",
                    "canonicalization_version": "c1",
                    "signature_hex": "ab" * 64,
                },
            }
        ],
    }
    approval_context = {
        "valid_signature_ids": [approval_id],
        "principal_directory": {approver_principal_id: approver_role},
        "at_epoch_ns": at_epoch_ns,
        "required_principals": 1,
    }
    return {"approval_set": approval_set, "approval_context": approval_context}


def verify_non_agent_approval_set(
    approval_set_input: Any,
    approval_context: Any,
) -> Tuple[bool, str]:
    """Verify an ApprovalSet/ApprovalRecord using frozen kernel validate_approval_set."""
    if not isinstance(approval_context, Mapping):
        return False, "Missing or invalid approval_context"

    try:
        if isinstance(approval_set_input, ApprovalSet):
            aset = approval_set_input
        elif isinstance(approval_set_input, Mapping):
            req_id = approval_set_input.get("requester_principal_id")
            if type(req_id) is not str or not req_id.strip():
                return False, "Invalid requester_principal_id in approval_set"
            kind_enum = ApprovalKind(approval_set_input.get("kind"))
            recs: List[ApprovalRecord] = []
            raw_approvals = approval_set_input.get("approvals")
            if not isinstance(raw_approvals, (list, tuple)) or not raw_approvals:
                return False, "ApprovalSet has no ApprovalRecord entries"
            for r in raw_approvals:
                if not isinstance(r, Mapping):
                    return False, "Malformed ApprovalRecord"
                sig_raw = r.get("signature")
                if not isinstance(sig_raw, Mapping):
                    return False, "Missing signature block in ApprovalRecord"
                sig_blk = SignatureBlock(
                    algorithm=str(sig_raw.get("algorithm", "")),
                    key_id=str(sig_raw.get("key_id", "")),
                    trust_root=str(sig_raw.get("trust_root", "sclass-root")),
                    canonicalization_version=str(sig_raw.get("canonicalization_version", "c1")),
                    signature=bytes.fromhex(str(sig_raw.get("signature_hex", ""))),
                )
                recs.append(
                    ApprovalRecord(
                        approval_id=str(r.get("approval_id", "")),
                        kind=ApprovalKind(r.get("kind")),
                        principal_id=str(r.get("principal_id", "")),
                        principal_role=str(r.get("principal_role", "")),
                        workspace_id=str(r.get("workspace_id", "")),
                        target_digest=Digest(str(r.get("target_digest", ""))),
                        policy_version=str(r.get("policy_version", "")),
                        scope_digest=Digest(str(r.get("scope_digest", ""))),
                        issued_at=UtcInstant(int(r.get("issued_at_ns"))),
                        expires_at=UtcInstant(int(r.get("expires_at_ns"))),
                        signature=sig_blk,
                    )
                )
            aset = ApprovalSet(
                set_id=str(approval_set_input.get("set_id", "")),
                kind=kind_enum,
                workspace_id=str(approval_set_input.get("workspace_id", "")),
                target_digest=Digest(str(approval_set_input.get("target_digest", ""))),
                policy_version=str(approval_set_input.get("policy_version", "")),
                scope_digest=Digest(str(approval_set_input.get("scope_digest", ""))),
                required_principals=int(approval_set_input.get("required_principals", 0)),
                approvals=tuple(recs),
                requester_principal_id=req_id,
            )
        else:
            return False, "Missing or invalid approval_set"
    except Exception as exc:
        return False, f"Malformed ApprovalSet/ApprovalRecord: {type(exc).__name__}"

    if aset.requester_principal_id.strip().lower().startswith("agent"):
        return False, "Agent cannot act as adapter registration authority"
    for r in aset.approvals:
        if (
            r.principal_id.strip().lower().startswith("agent")
            or r.principal_role.strip().lower() == "agent"
        ):
            return False, "Agent approval record rejected for adapter registration"

    valid_sigs = approval_context.get("valid_signature_ids")
    principal_dir = approval_context.get("principal_directory")
    at_ns = approval_context.get("at_epoch_ns")
    req_p = approval_context.get("required_principals", aset.required_principals)
    if (
        not isinstance(valid_sigs, (list, tuple, set, frozenset))
        or not isinstance(principal_dir, Mapping)
        or type(at_ns) is not int
        or type(req_p) is not int
    ):
        return False, "Invalid approval_context fields"

    res = validate_approval_set(
        aset,
        frozenset(str(x) for x in valid_sigs),
        UtcInstant(at_ns),
        {str(k): str(v) for k, v in principal_dir.items()},
        req_p,
    )
    if res != ApprovalSetResult.VALID:
        return False, f"ApprovalSet validation failed: {res.value}"
    return True, "ApprovalSet VALID (non-agent authority)"


def detect_differential_disagreement(
    primary_output: Any,
    secondary_output: Any,
    primary_bindings: Any,
    secondary_bindings: Any,
) -> Tuple[bool, str]:
    """A2 differential comparison on canonicalized semantics and provenance bindings."""
    p_canon = canonical_json(primary_output)
    s_canon = canonical_json(secondary_output)
    if p_canon != s_canon:
        return False, "Canonicalized output semantics disagree"
    pb_canon = canonical_json(primary_bindings)
    sb_canon = canonical_json(secondary_bindings)
    if pb_canon != sb_canon:
        return False, "Evidence/provenance bindings disagree"
    return True, "Differential results agree"


def check_stale_evidence(
    evidence_adapter_digest: str,
    current_adapter_digest: str,
) -> Tuple[bool, str]:
    """A3 stale-evidence check: any adapter digest change invalidates dependent evidence."""
    if not evidence_adapter_digest or not current_adapter_digest:
        return False, "MISSING_ADAPTER_DIGEST"
    if evidence_adapter_digest != current_adapter_digest:
        return False, "STALE_EVIDENCE_AFTER_DIGEST_CHANGE"
    return True, "EVIDENCE_FRESH"
