"""Cross-artifact integrity gate for the active v6.0.1 semantic contract."""
from __future__ import annotations
import ast, json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=ROOT/"00-SPEC/S-CLASS-v6.0.1-FINAL-FIXED-DESIGN.md"
SEM=ROOT/"10-CONFORMANCE/sclass_semantics_v6_0_1.py"
SM=ROOT/"10-CONFORMANCE/state-machines.v6.0.1.json"
CM=ROOT/"10-CONFORMANCE/coverage-map.v6.0.1.json"


def code_blocks(text):
    return re.findall(r"```python\n(.*?)\n```", text, re.S)


def defined_classes(text):
    out=[]
    for block in code_blocks(text):
        tree=ast.parse(block)
        out.extend(n.name for n in tree.body if isinstance(n,ast.ClassDef))
    return out


def registry(text):
    marker="| # | Type | Category |"
    a=text.index(marker)
    b=text.index("## 2.2",a)
    return [(int(n), name, cat.strip()) for n,name,cat in re.findall(r"\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|",text[a:b])]


def source_registry():
    tree=ast.parse(SEM.read_text())
    out=[]
    for n in tree.body:
        if not isinstance(n,ast.ClassDef):
            continue
        decorators={getattr(d,'id',getattr(d,'attr','')) for d in n.decorator_list}
        bases={getattr(b,'id',getattr(b,'attr','')) for b in n.bases}
        if n.name=="FrozenMap" or "canonical_dataclass" in decorators or "Enum" in bases or "IntEnum" in bases or "Protocol" in bases:
            category=("Enum/Value" if ("Enum" in bases or "IntEnum" in bases)
                      else "Protocol" if "Protocol" in bases else "Canonical")
            out.append((n.name,category))
    return out


def class_field_names(text, class_name):
    for block in code_blocks(text):
        tree=ast.parse(block)
        for n in tree.body:
            if isinstance(n,ast.ClassDef) and n.name==class_name:
                return tuple(stmt.target.id for stmt in n.body if isinstance(stmt,ast.AnnAssign) and isinstance(stmt.target,ast.Name))
    raise AssertionError(f"{class_name} not found")

def source_class_field_names(class_name):
    tree=ast.parse(SEM.read_text())
    for n in tree.body:
        if isinstance(n,ast.ClassDef) and n.name==class_name:
            return tuple(stmt.target.id for stmt in n.body if isinstance(stmt,ast.AnnAssign) and isinstance(stmt.target,ast.Name))
    raise AssertionError(f"{class_name} not found in executable semantics")

def event_types_from_text(text):
    for block in code_blocks(text):
        tree=ast.parse(block)
        for n in tree.body:
            if isinstance(n,ast.ClassDef) and n.name=="EventType":
                return {x.targets[0].id for x in n.body
                        if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name)}
    raise AssertionError("EventType not found")


def event_types_from_source():
    tree=ast.parse(SEM.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="EventType")
    return {x.targets[0].id for x in cls.body if isinstance(x,ast.Assign) and isinstance(x.targets[0],ast.Name)}


def main():
    text=SPEC.read_text()
    assert "FINAL FIXED DESIGN" in text
    reg=registry(text)
    assert [n for n,_,_ in reg] == list(range(1,len(reg)+1)), "registry numbering is not contiguous"
    normalized=[(name,cat) for _,name,cat in reg]
    source=source_registry()
    assert normalized == source, "spec registry != executable semantic registry"
    source_names={name for name,_ in source}
    spec_names=set(defined_classes(text))
    transient_spec_types={"WorkProposal","PayloadFieldSpec"}
    assert source_names - spec_names <= set(), f"registry types missing spec definitions: {sorted(source_names-spec_names)}"
    assert spec_names - source_names <= transient_spec_types, f"unclassified spec-only types: {sorted(spec_names-source_names)}"
    assert event_types_from_text(text) == event_types_from_source(), "spec EventType != executable EventType"
    assert class_field_names(text,"Command") == source_class_field_names("Command"), "spec Command schema != executable Command schema"
    assert 'aggregate_id' in class_field_names(text,"Command"), "Command.aggregate_id missing from active spec"
    assert class_field_names(text,"AuthorizationDecision") == source_class_field_names("AuthorizationDecision"), "spec AuthorizationDecision schema != executable schema"
    for name,_category in source:
        if name in transient_spec_types:
            continue
        assert class_field_names(text,name) == source_class_field_names(name), f"spec {name} schema != executable schema"
    assert "request_id" in class_field_names(text,"BudgetReservation")
    assert "budget_reservation_id" in class_field_names(text,"ExecutionLease")
    assert "budget_reservation_id" in class_field_names(text,"AuthorizedWorkRequest")
    assert {"execution_lease_id","execution_generation","execution_attempt_id","worker_identity","process_id","process_start_time_ns","attestation_signature"} <= set(class_field_names(text,"QuiescenceProof"))
    assert "process_id" in class_field_names(text,"ProcessExecutionResult")
    assert 'EVENT_HASH_DOMAIN = "sclass/event/v2"' in text
    sem_text=SEM.read_text()
    assert 'EVENT_HASH_DOMAIN = "sclass/event/v2"' in sem_text
    assert 'class Command:' in sem_text and 'aggregate_id: str' in sem_text
    assert 'external_effect_receipts' in sem_text
    sm=json.loads(SM.read_text())
    assert sm["rules"]["every_event_type_has_reducer"] is True
    assert sm["reducer_handler_contract"]["current_handler_kind"] == "reference_reducer"
    assert sm["rules"]["reducer_consumes_this_machine_source"] is True
    assert set(sm["event_transitions"]) == event_types_from_source()
    cm=json.loads(CM.read_text())
    assert any(e.get("coverage_key")=="EXTERNAL-EFFECT-RECONCILIATION-CANONICAL-01" for e in cm["entries"])
    # All contract code blocks must remain syntactically valid, but are documentation snippets.
    for block in code_blocks(text):
        ast.parse(block)
    # Importing the kernel confirms reducer coverage is complete and machine source is loadable.
    import sys
    sys.path.insert(0, str(ROOT/"10-CONFORMANCE"))
    import sclass_semantics_v6_0_1 as runtime
    assert set(runtime.REFERENCE_REDUCER_HANDLERS)==set(runtime.EventType)
    assert all(callable(h) for h in runtime.REFERENCE_REDUCER_HANDLERS.values())
    assert "authorization_decisions" in runtime.EngineeringState.__dataclass_fields__
    assert "execution_outcomes" in runtime.EngineeringState.__dataclass_fields__
    assert "external_effect_receipts" in runtime.EngineeringState.__dataclass_fields__
    print(f"SPEC_INTEGRITY_OK registry={len(reg)} events={len(event_types_from_source())}")

if __name__=="__main__":
    main()
