"""W15: Inspect 76 uncovered MUSTs and evaluate reachability through registry.evaluate."""
import os
import sys
import csv

sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('src'))
sys.path.insert(0, os.path.abspath('tools'))
sys.path.insert(0, os.path.abspath('tests/block2'))

from sclass.product.registry import evaluate, REGISTRY_AUTHORITY
from sclass.product.registry_table import REGISTRY_TABLE_ROWS
from sclass.product.gate import GateState
from sclass.qualification.adapter_registry import use_test_only_qualified_registry
from uncovered_76_payloads import UNCOVERED_HAPPY_PAYLOADS

v3_path = 'product/MUST-ALLOCATION-V3.csv'
with open(v3_path, 'r', encoding='utf-8') as f:
    v3_rows = {r['must_id']: r for r in csv.DictReader(f)}

reg_by_id = {r['must_id']: r for r in REGISTRY_TABLE_ROWS}

uncovered_ids = sorted(list(UNCOVERED_HAPPY_PAYLOADS.keys()))
print(f"Total uncovered MUSTs: {len(uncovered_ids)}")

table_rows = []
for mid in uncovered_ids:
    r = v3_rows.get(mid, {})
    chapter_sec = r.get('chapter_section', '')
    cls_kind = r.get('class', '')
    needs_eng = r.get('needs_engine', '')
    test_ids = r.get('evidence', '')
    
    if mid not in reg_by_id:
        can_reach = "NO-EVALUATOR"
        eval_loc = "NONE"
        reason = "Evaluator not registered in registry_table"
    else:
        reg_row = reg_by_id[mid]
        eval_loc = f"{reg_row['module']}:{reg_row['function_name']}:{reg_row['line']}"
        payload = UNCOVERED_HAPPY_PAYLOADS.get(mid, {})
        with use_test_only_qualified_registry():
            out = evaluate(mid, payload, authority=REGISTRY_AUTHORITY)
        if out.state == GateState.SATISFIED:
            can_reach = "YES"
            reason = "SATISFIED"
        else:
            can_reach = "NO"
            reason = f"{out.detail}"
            
    table_rows.append({
        "must_id": mid,
        "chapter_section": chapter_sec,
        "class": cls_kind,
        "needs_engine": needs_eng,
        "evaluator": eval_loc,
        "existing_test_ids": test_ids,
        "can_reach": can_reach,
        "reason": reason,
    })

# Print markdown table
print("\n| must_id | chapter_section | class | needs_engine | evaluator file:line | existing evidence test ids (from V3.csv) | can it reach SATISFIED through registry.evaluate | exact reason |")
print("|---|---|---|---|---|---|---|---|")
for row in table_rows:
    print(f"| {row['must_id']} | {row['chapter_section']} | {row['class']} | {row['needs_engine']} | `{row['evaluator']}` | `{row['existing_test_ids']}` | {row['can_reach']} | {row['reason']} |")

yes_count = sum(1 for r in table_rows if r['can_reach'] == 'YES')
no_count = sum(1 for r in table_rows if r['can_reach'] == 'NO')
no_eval_count = sum(1 for r in table_rows if r['can_reach'] == 'NO-EVALUATOR')

print(f"\nSummary: Total={len(table_rows)}, YES={yes_count}, NO={no_count}, NO-EVALUATOR={no_eval_count}")
