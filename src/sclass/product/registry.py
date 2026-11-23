"""Unified WI-100 product MUST registry for all 195 active S-Class MUSTs.

Gate vocabulary reconciliation (T2):
- Product GateState (src/sclass/product/gate.py) defines 3 states:
  SATISFIED, MISSING, BLOCKED_ON_HUMAN.
- Master F5 (PD-F5-005, master:L672, L684) defines DENIED as a kernel
  ExecutionGate / ReleaseEvaluation authority state:
  "F5-T5a | F5-FT5a kernel ExecutionGate=DENIED, product check SATISFIED |
  combined DENIED; kernel authority wins". Product gates never emit DENIED;
  kernel authority overrides product SATISFIED.
- Master Ch.5 (PD-CH5-005, master:L3641) defines NOT_APPLICABLE for metric
  derivation with zero denominators ("mark zero denominators NOT_APPLICABLE"),
  not as a product GateState.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Tuple

from sclass.product.gate import GateOutput, GateState
from sclass.product.registry_table import REGISTRY_TABLE_ROWS

REGISTRY_AUTHORITY = "sclass.product.registry"
MAX_EVIDENCE_KEYS = 10000


@dataclass(frozen=True)
class MustEntry:
    must_id: str
    block: str
    plane: str
    wi: str
    module: str
    function_name: str
    line: int
    param_names: Tuple[str, ...]
    status_in_registry: str
    needs_engine: bool = False
    class_kind: str = "M"


@dataclass(frozen=True)
class ReleaseVerdictResult:
    verdict: str  # "READY" | "PARTIAL" | "BLOCKED" | "BLOCKED_ON_HUMAN"
    complete: bool = False
    missing_musts: Tuple[str, ...] = ()
    blocked_musts: Tuple[str, ...] = ()
    satisfied_musts: Tuple[str, ...] = ()


def _build_index() -> Tuple[Tuple[MustEntry, ...], Mapping[str, Dict[str, Any]]]:
    entries = []
    by_id: Dict[str, Dict[str, Any]] = {}
    for row in REGISTRY_TABLE_ROWS:
        entry = MustEntry(
            must_id=row["must_id"],
            block=row["block"],
            plane=row["plane"],
            wi=row["wi"],
            module=row["module"],
            function_name=row["function_name"],
            line=int(row["line"]),
            param_names=tuple(row["param_names"]),
            status_in_registry=row["status_in_registry"],
            needs_engine=bool(row["needs_engine"]),
            class_kind=row["class_kind"],
        )
        entries.append(entry)
        by_id[row["must_id"]] = row
    return tuple(entries), MappingProxyType(by_id)


_MUST_ENTRIES, _INDEX_BY_ID = _build_index()


def list_musts() -> Tuple[MustEntry, ...]:
    """Return frozen, sorted tuple of all 195 active MUST entries."""
    return _MUST_ENTRIES


def _missing(must_id: Optional[str], detail: str) -> GateOutput:
    return GateOutput(
        state=GateState.MISSING,
        must_id=must_id,
        detail=detail,
        failures=[f"MISSING[{must_id}]"] if must_id else ["MISSING"],
    )


def evaluate(
    must_id: str,
    evidence: Mapping[str, object] | None,
    *,
    authority: object | None = None,
) -> GateOutput:
    """Single entry point evaluating any of the 195 active MUSTs fail-closed."""
    if not isinstance(must_id, str) or not must_id or must_id != must_id.strip():
        return _missing(None, "invalid_must_id")
    row = _INDEX_BY_ID.get(must_id)
    if row is None:
        return _missing(must_id, "unknown_must_id")
    if row["status_in_registry"] != "IMPLEMENTED":
        return _missing(must_id, "not_implemented")
    if not isinstance(authority, str) or not authority:
        return _missing(must_id, "missing_or_invalid_authority")
    if not isinstance(evidence, Mapping):
        return _missing(must_id, "evidence_not_mapping")
    if len(evidence) > MAX_EVIDENCE_KEYS:
        return _missing(must_id, "evidence_key_limit_exceeded")
    for k in evidence.keys():
        if not isinstance(k, str):
            return _missing(must_id, "non_string_evidence_key")

    if row["needs_engine"]:
        if evidence.get("adapter_qualified") is not True:
            return _missing(must_id, "ENGINE_NOT_QUALIFIED")

    try:
        mod = importlib.import_module(row["module"])
        fn: Callable[..., Any] = getattr(mod, row["function_name"])
        mod_auth = getattr(mod, "QUALIFIED_EVALUATOR_BOUNDARY", None)
        if authority == REGISTRY_AUTHORITY:
            call_auth = mod_auth
        elif mod_auth is not None and authority == mod_auth:
            call_auth = mod_auth
        else:
            return _missing(must_id, "unauthorized_caller_authority")

        strip_qualified = row["needs_engine"] and "adapter_qualified" not in row["param_names"]
        eval_evidence: Dict[str, Any] = {
            k: v for k, v in evidence.items() if not (strip_qualified and k == "adapter_qualified")
        }

        if row["single_dict_param"]:
            param_name = row["pos_names"][0]
            ro_ev = MappingProxyType(eval_evidence)
            if "authority" in row["kw_names"] or "authority" in row["pos_names"]:
                res = fn(**{param_name: ro_ev, "authority": call_auth})
            elif "caller_authority" in row["kw_names"] or "caller_authority" in row["pos_names"]:
                res = fn(**{param_name: ro_ev, "caller_authority": call_auth})
            else:
                res = fn(**{param_name: ro_ev})
        else:
            allowed_keys = set(row["param_names"]) - {"authority", "caller_authority"}
            extra_keys = set(eval_evidence.keys()) - allowed_keys
            if extra_keys:
                return _missing(must_id, f"unexpected evidence key: {sorted(extra_keys)}")
            kwargs: Dict[str, Any] = {}
            for p in row["pos_names"]:
                if p == "authority":
                    kwargs["authority"] = call_auth
                elif p == "caller_authority":
                    kwargs["caller_authority"] = call_auth
                else:
                    kwargs[p] = eval_evidence.get(p, None)
            for k in row["kw_names"]:
                if k == "authority":
                    kwargs["authority"] = call_auth
                elif k == "caller_authority":
                    kwargs["caller_authority"] = call_auth
                elif k in eval_evidence:
                    kwargs[k] = eval_evidence[k]
            res = fn(**kwargs)
    except Exception as exc:
        return _missing(must_id, f"evaluator_exception:{type(exc).__name__}")

    if not isinstance(res, GateOutput) or not isinstance(res.state, GateState):
        return _missing(must_id, "invalid_evaluator_output")
    return res


def release_verdict(
    evidence_by_must: Mapping[str, Mapping[str, object]] | None,
    *,
    authority: object | None = None,
    required: Iterable[str] | None = None,
) -> ReleaseVerdictResult:
    """Compute release verdict across required MUSTs (default: all 195)."""
    req_ids = (
        tuple(dict.fromkeys(required))
        if required is not None
        else tuple(e.must_id for e in _MUST_ENTRIES)
    )
    all_ids = {e.must_id for e in _MUST_ENTRIES}
    complete = set(req_ids) == all_ids
    if not isinstance(evidence_by_must, Mapping):
        return ReleaseVerdictResult(verdict="BLOCKED", complete=complete, missing_musts=req_ids)

    missing: list[str] = []
    blocked: list[str] = []
    satisfied: list[str] = []

    for mid in req_ids:
        ev = evidence_by_must.get(mid) if isinstance(mid, str) else None
        out = evaluate(mid, ev, authority=authority)
        if out.state == GateState.SATISFIED:
            satisfied.append(mid)
        elif out.state == GateState.BLOCKED_ON_HUMAN:
            blocked.append(mid)
        else:
            missing.append(mid)

    if missing:
        verdict = "BLOCKED"
    elif blocked:
        verdict = "BLOCKED_ON_HUMAN"
    elif complete:
        verdict = "READY"
    else:
        verdict = "PARTIAL"
    return ReleaseVerdictResult(
        verdict=verdict,
        complete=complete,
        missing_musts=tuple(missing),
        blocked_musts=tuple(blocked),
        satisfied_musts=tuple(satisfied),
    )
