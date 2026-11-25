"""WI-101 Audit Export & Read-Only Viewer (B22).

Exports a tamper-evident bundle reconstructing every gate decision, inputs,
evaluator ref, and GateOutput from EventStore/Decision/Approval/WorkGraph/
VerificationPlan/receipts, with explicit truncation declaration and O_RDONLY viewer.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
from typing import Any, Dict, List, Mapping, Optional, Sequence

from sclass.product.gate import GateOutput
from sclass.product.registry import REGISTRY_AUTHORITY, evaluate, list_musts


class AuditBundleTamperError(ValueError):
    """Raised when an audit export bundle fails integrity digest verification."""


class AuditBundleReconstructionError(ValueError):
    """Raised when an audit export bundle is missing required gate inputs/outputs."""


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _compute_bundle_sha256(bundle_without_hash: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(bundle_without_hash).encode("utf-8")).hexdigest()


def _digest_producer_object(obj: Any) -> str:
    """Compute canonical sha256:<hex> digest for any producer dataclass/mapping."""
    raw = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def collect_audit_sources(
    *,
    event_store: Any = None,
    workspace_id: str = "default",
    decisions: Sequence[Any] = (),
    approval_sets: Sequence[Any] = (),
    work_graph: Any = None,
    verification_plans: Sequence[Any] = (),
    receipts: Sequence[Any] = (),
) -> Dict[str, Any]:
    """Extract canonical IDs, digests, and counts from real S-Class producer objects."""
    ev_digest = ""
    ev_count: Optional[int] = None
    if event_store is not None:
        head_obj = event_store.head(workspace_id)
        ev_digest = str(getattr(head_obj, "hash", "") or "")
        seq = getattr(head_obj, "sequence", None)
        ev_count = int(seq) if isinstance(seq, int) else 0

    dec_ids: List[str] = []
    for d in decisions:
        if isinstance(d, str):
            dec_ids.append(d)
        elif isinstance(d, Mapping) and "decision_id" in d:
            dec_ids.append(str(d["decision_id"]))
        elif hasattr(d, "decision_id"):
            dec_ids.append(str(getattr(d, "decision_id")))
        else:
            dec_ids.append(_digest_producer_object(d))

    apr_ids: List[str] = []
    for item in approval_sets:
        if isinstance(item, str):
            apr_ids.append(item)
        elif hasattr(item, "approvals"):
            records = list(getattr(item, "approvals") or ())
            if records:
                for rec in records:
                    apr_ids.append(str(getattr(rec, "approval_id", _digest_producer_object(rec))))
            else:
                apr_ids.append(str(getattr(item, "set_id", _digest_producer_object(item))))
        elif hasattr(item, "approval_id"):
            apr_ids.append(str(getattr(item, "approval_id")))
        elif isinstance(item, Mapping) and "approval_id" in item:
            apr_ids.append(str(item["approval_id"]))
        else:
            apr_ids.append(_digest_producer_object(item))

    wg_digest = ""
    if work_graph is not None:
        if isinstance(work_graph, str):
            wg_digest = work_graph
        else:
            wg_payload = {
                "revision_id": getattr(work_graph, "revision_id", ""),
                "objective_revision": getattr(work_graph, "objective_revision", ""),
                "obligation_graph_revision": getattr(work_graph, "obligation_graph_revision", ""),
                "policy_version": getattr(work_graph, "policy_version", ""),
                "world_model_revision": getattr(work_graph, "world_model_revision", ""),
                "nodes": sorted(list(getattr(work_graph, "_nodes", ()) or ())),
            }
            wg_digest = _digest_producer_object(wg_payload)

    vp_digest = ""
    vp_count = 0
    if verification_plans:
        plan_summaries = []
        for p in verification_plans:
            if isinstance(p, str):
                plan_summaries.append(p)
            else:
                plan_summaries.append(
                    {
                        "plan_id": getattr(p, "plan_id", ""),
                        "obligation_id": getattr(p, "obligation_id", ""),
                        "revision": getattr(p, "revision", ""),
                        "contract_revision": getattr(p, "contract_revision", ""),
                        "step_ids": [getattr(s, "step_id", str(s)) for s in (getattr(p, "steps", ()) or ())],
                    }
                )
        vp_count = len(plan_summaries)
        vp_digest = _digest_producer_object(plan_summaries)

    rec_digests: List[str] = []
    for r in receipts:
        if isinstance(r, str):
            rec_digests.append(r)
        else:
            rec_digests.append(_digest_producer_object(r))

    return {
        "event_store_digest": ev_digest,
        "event_store_count": ev_count,
        "decision_ids": tuple(dec_ids),
        "approval_ids": tuple(apr_ids),
        "work_graph_digest": wg_digest,
        "verification_plan_digest": vp_digest,
        "verification_plan_count": vp_count,
        "receipt_digests": tuple(rec_digests),
    }


def export_audit_bundle(
    gate_records: Sequence[Mapping[str, Any]],
    *,
    event_store_digest: str = "",
    decision_ids: Sequence[str] = (),
    approval_ids: Sequence[str] = (),
    work_graph_digest: str = "",
    verification_plan_digest: str = "",
    receipt_digests: Sequence[str] = (),
    max_entries: Optional[int] = None,
    event_store: Any = None,
    workspace_id: str = "default",
    decisions: Sequence[Any] = (),
    approval_sets: Sequence[Any] = (),
    work_graph: Any = None,
    verification_plans: Sequence[Any] = (),
    receipts: Sequence[Any] = (),
) -> Dict[str, Any]:
    """Build a deterministic, integrity-hashed audit export bundle.

    Reads and references all 6 authoritative sources:
    - EventStore (SQLiteEventStore / canonical events)
    - Decision
    - Approval
    - WorkGraph
    - VerificationPlan
    - receipts
    Sources with no records in current block runs are declared explicitly with record_count=0
    and note without fabrication.
    """
    by_id = {e.must_id: e for e in list_musts()}
    total_count = len(gate_records)
    if max_entries is not None and max_entries < total_count:
        selected = list(gate_records[:max_entries])
        truncated = True
    else:
        selected = list(gate_records)
        truncated = False

    exported_gates: List[Dict[str, Any]] = []
    for rec in selected:
        mid = str(rec["must_id"])
        entry = by_id.get(mid)
        eval_ref = (
            f"{entry.module}:{entry.function_name}:{entry.line}"
            if entry is not None
            else "UNKNOWN"
        )
        if "inputs" not in rec or not isinstance(rec["inputs"], Mapping):
            raise AuditBundleReconstructionError(f"Gate record for {mid} missing inputs mapping")
        if "output" not in rec:
            raise AuditBundleReconstructionError(f"Gate record for {mid} missing output")
        out_val = rec["output"]
        if isinstance(out_val, GateOutput):
            out_dict = {"state": out_val.state.value, "must_id": out_val.must_id, "str": str(out_val)}
        elif isinstance(out_val, Mapping):
            out_dict = dict(out_val)
        else:
            out_dict = {"str": str(out_val)}
        exported_gates.append(
            {
                "must_id": mid,
                "fixture_id": rec.get("fixture_id"),
                "inputs": dict(rec["inputs"]),
                "evaluator_ref": eval_ref,
                "output": out_dict,
            }
        )

    collected = collect_audit_sources(
        event_store=event_store,
        workspace_id=workspace_id,
        decisions=decisions,
        approval_sets=approval_sets,
        work_graph=work_graph,
        verification_plans=verification_plans,
        receipts=receipts,
    )
    eff_event_digest = event_store_digest or collected["event_store_digest"]
    eff_event_count = (
        collected["event_store_count"]
        if collected["event_store_count"] is not None
        else (total_count if eff_event_digest else 0)
    )
    eff_decision_ids = list(decision_ids) if decision_ids else list(collected["decision_ids"])
    eff_approval_ids = list(approval_ids) if approval_ids else list(collected["approval_ids"])
    eff_wg_digest = work_graph_digest or collected["work_graph_digest"]
    eff_vp_digest = verification_plan_digest or collected["verification_plan_digest"]
    eff_vp_count = (
        1
        if verification_plan_digest
        else (collected["verification_plan_count"] if eff_vp_digest else 0)
    )
    eff_receipt_digests = list(receipt_digests) if receipt_digests else list(collected["receipt_digests"])

    sources_map: Dict[str, Any] = {
        "EventStore": {
            "type": "SQLiteEventStore",
            "digest": eff_event_digest or "GENESIS",
            "record_count": eff_event_count,
            "note": (
                f"{eff_event_count} real producer record(s) exported"
                if eff_event_digest
                else "NO_RECORDS_PROVIDED_IN_RUN"
            ),
        },
        "Decision": {
            "type": "Decision",
            "ids": eff_decision_ids,
            "record_count": len(eff_decision_ids),
            "note": (
                f"{len(eff_decision_ids)} real producer record(s) exported"
                if eff_decision_ids
                else "NO_RECORDS_PROVIDED_IN_RUN"
            ),
        },
        "Approval": {
            "type": "Approval",
            "ids": eff_approval_ids,
            "record_count": len(eff_approval_ids),
            "note": (
                f"{len(eff_approval_ids)} real producer record(s) exported"
                if eff_approval_ids
                else "NO_RECORDS_PROVIDED_IN_RUN"
            ),
        },
        "WorkGraph": {
            "type": "WorkGraph",
            "digest": eff_wg_digest,
            "record_count": 1 if eff_wg_digest else 0,
            "note": (
                "1 real producer record(s) exported"
                if eff_wg_digest
                else "NO_RECORDS_PROVIDED_IN_RUN"
            ),
        },
        "VerificationPlan": {
            "type": "VerificationPlan",
            "digest": eff_vp_digest,
            "record_count": eff_vp_count,
            "note": (
                f"{eff_vp_count} real producer record(s) exported"
                if eff_vp_digest
                else "NO_RECORDS_PROVIDED_IN_RUN"
            ),
        },
        "receipts": {
            "type": "receipts",
            "digests": eff_receipt_digests,
            "record_count": len(eff_receipt_digests),
            "note": (
                f"{len(eff_receipt_digests)} real producer record(s) exported"
                if eff_receipt_digests
                else "NO_RECORDS_PROVIDED_IN_RUN"
            ),
        },
    }

    body: Dict[str, Any] = {
        "schema_version": "1.0",
        "truncated": truncated,
        "total_count": total_count,
        "exported_count": len(exported_gates),
        "sources": sources_map,
        "gates": exported_gates,
    }
    body["bundle_sha256"] = _compute_bundle_sha256(body)
    return body


def verify_and_load_bundle_dict(bundle: Mapping[str, Any]) -> Dict[str, Any]:
    """Verify bundle_sha256 integrity; raise AuditBundleTamperError on any mismatch."""
    expected_sha = bundle.get("bundle_sha256")
    if not isinstance(expected_sha, str) or not expected_sha:
        raise AuditBundleTamperError("Missing bundle_sha256")
    body = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    actual_sha = _compute_bundle_sha256(body)
    if actual_sha != expected_sha:
        raise AuditBundleTamperError(
            f"Audit bundle tampered: expected {expected_sha}, got {actual_sha}"
        )
    return dict(bundle)


def write_audit_bundle(bundle: Mapping[str, Any], out_path: pathlib.Path) -> pathlib.Path:
    verify_and_load_bundle_dict(bundle)
    out_path.write_text(json.dumps(bundle, sort_keys=True, indent=2, default=str), encoding="utf-8")
    return out_path


def open_bundle_readonly(bundle_path: pathlib.Path) -> tuple[int, Dict[str, Any]]:
    """Open an audit bundle strictly with os.O_RDONLY, verify digest, and return (fd, bundle).

    Caller owns closing fd. Proves read-only fd cannot write.
    """
    fd = os.open(str(bundle_path), os.O_RDONLY)
    try:
        chunks: List[bytes] = []
        while True:
            buf = os.read(fd, 65536)
            if not buf:
                break
            chunks.append(buf)
        raw = b"".join(chunks).decode("utf-8")
        data = json.loads(raw)
        verified = verify_and_load_bundle_dict(data)
        return fd, verified
    except Exception:
        os.close(fd)
        raise


def rerun_bundle_gates(bundle: Mapping[str, Any]) -> List[GateOutput]:
    """Verify bundle integrity and re-run every gate through sclass.product.registry.evaluate."""
    verified = verify_and_load_bundle_dict(bundle)
    outputs: List[GateOutput] = []
    for g in verified["gates"]:
        if "inputs" not in g or not isinstance(g["inputs"], Mapping):
            raise AuditBundleReconstructionError(f"Gate {g.get('must_id')} missing inputs")
        out = evaluate(g["must_id"], g["inputs"], authority=REGISTRY_AUTHORITY)
        outputs.append(out)
    return outputs
