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
) -> Dict[str, Any]:
    """Build a deterministic, integrity-hashed audit export bundle."""
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

    body: Dict[str, Any] = {
        "schema_version": "1.0",
        "truncated": truncated,
        "total_count": total_count,
        "exported_count": len(exported_gates),
        "sources": {
            "event_store_digest": event_store_digest,
            "decision_ids": list(decision_ids),
            "approval_ids": list(approval_ids),
            "work_graph_digest": work_graph_digest,
            "verification_plan_digest": verification_plan_digest,
            "receipt_digests": list(receipt_digests),
        },
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
    out_path.write_text(json.dumps(bundle, sort_keys=True, indent=2), encoding="utf-8")
    return out_path


def open_bundle_readonly(bundle_path: pathlib.Path) -> tuple[int, Dict[str, Any]]:
    """Open an audit bundle strictly with os.O_RDONLY, verify digest, and return (fd, bundle).

    Caller owns closing fd (or use view_bundle_readonly). Proves read-only fd cannot write.
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
