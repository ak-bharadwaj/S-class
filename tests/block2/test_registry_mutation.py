"""T8 / F3 tests: in-memory registry mutation check asserting exact survivor sets."""
from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import mutate_registry  # type: ignore

EXPECTED_ALWAYS_MISSING_SURVIVORS = {
    "PD-CH10-007 (sclass.product.erratum_issue_registry:evaluate_pd_ch10_007_master_cross_links)",
    "PD-CH5-003 (sclass.product.registry_adapters:evaluate_pd_ch5_003)",
    "PD-CH5-004 (sclass.product.registry_adapters:evaluate_pd_ch5_004)",
    "PD-CH5-005 (sclass.product.registry_adapters:evaluate_pd_ch5_005)",
    "PD-CH5-006 (sclass.product.registry_adapters:evaluate_pd_ch5_006)",
    "PD-CH6-003 (sclass.product.oss_qualification_playbook:evaluate_pd_ch6_003_pack_activation)",
    "PD-CH6-006 (sclass.product.oss_qualification_playbook:evaluate_pd_ch6_006_playbook_content)",
    "PD-F1-001 (sclass.product.registry_adapters:evaluate_pd_f1_001)",
    "PD-F1-002 (sclass.product.registry_adapters:evaluate_pd_f1_002)",
    "PD-F1-003 (sclass.product.registry_adapters:evaluate_pd_f1_003)",
    "PD-F1-004 (sclass.product.registry_adapters:evaluate_pd_f1_004)",
    "PD-F1-005 (sclass.product.registry_adapters:evaluate_pd_f1_005)",
    "PD-F2-001 (sclass.product.registry_adapters:evaluate_pd_f2_001)",
    "PD-F2-002 (sclass.product.registry_adapters:evaluate_pd_f2_002)",
    "PD-F2-005 (sclass.product.registry_adapters:evaluate_pd_f2_005)",
    "PD-F2-007 (sclass.product.registry_adapters:evaluate_pd_f2_007)",
    "PD-F3-001 (sclass.product.registry_adapters:evaluate_pd_f3_001)",
    "PD-F3-002 (sclass.product.registry_adapters:evaluate_pd_f3_002)",
    "PD-F3-003 (sclass.product.registry_adapters:evaluate_pd_f3_003)",
    "PD-F3-004 (sclass.product.registry_adapters:evaluate_pd_f3_004)",
    "PD-F3-005 (sclass.product.registry_adapters:evaluate_pd_f3_005)",
    "PD-F3-006 (sclass.product.registry_adapters:evaluate_pd_f3_006)",
    "PD-F4-001 (sclass.product.registry_adapters:evaluate_pd_f4_001)",
    "PD-F4-002 (sclass.product.registry_adapters:evaluate_pd_f4_002)",
    "PD-F4-003 (sclass.product.registry_adapters:evaluate_pd_f4_003)",
    "PD-F4-004 (sclass.product.registry_adapters:evaluate_pd_f4_004)",
    "PD-F4-005 (sclass.product.registry_adapters:evaluate_pd_f4_005)",
    "PD-F4-006 (sclass.product.registry_adapters:evaluate_pd_f4_006)",
    "PD-F5-001 (sclass.product.registry_adapters:evaluate_pd_f5_001)",
    "PD-F5-002 (sclass.product.registry_adapters:evaluate_pd_f5_002)",
    "PD-F5-003 (sclass.product.registry_adapters:evaluate_pd_f5_003)",
    "PD-F5-004 (sclass.product.registry_adapters:evaluate_pd_f5_004)",
    "PD-F5-005 (sclass.product.registry_adapters:evaluate_pd_f5_005)",
    "PD-F6-001 (sclass.product.registry_adapters:evaluate_pd_f6_001)",
    "PD-F6-002 (sclass.product.registry_adapters:evaluate_pd_f6_002)",
    "PD-F6-003 (sclass.product.registry_adapters:evaluate_pd_f6_003)",
    "PD-F6-004 (sclass.product.registry_adapters:evaluate_pd_f6_004)",
    "PD-F6-005 (sclass.product.registry_adapters:evaluate_pd_f6_005)",
    "PD-F6-006 (sclass.product.registry_adapters:evaluate_pd_f6_006)",
    "PD-F7-001 (sclass.product.registry_adapters:evaluate_pd_f7_001)",
    "PD-F7-002 (sclass.product.registry_adapters:evaluate_pd_f7_002)",
    "PD-F7-003 (sclass.product.registry_adapters:evaluate_pd_f7_003)",
    "PD-F7-004 (sclass.product.registry_adapters:evaluate_pd_f7_004)",
    "PD-F7-005 (sclass.product.registry_adapters:evaluate_pd_f7_005)",
    "PD-F7-006 (sclass.product.registry_adapters:evaluate_pd_f7_006)",
    "PD-F8-001 (sclass.product.registry_adapters:evaluate_pd_f8_001)",
    "PD-F8-002 (sclass.product.registry_adapters:evaluate_pd_f8_002)",
    "PD-F8-003 (sclass.product.registry_adapters:evaluate_pd_f8_003)",
    "PD-F8-004 (sclass.product.registry_adapters:evaluate_pd_f8_004)",
    "PD-F9-001 (sclass.product.registry_adapters:evaluate_pd_f9_001)",
    "PD-F9-002 (sclass.product.registry_adapters:evaluate_pd_f9_002)",
    "PD-F9-003 (sclass.product.registry_adapters:evaluate_pd_f9_003)",
    "PD-F9-004 (sclass.product.registry_adapters:evaluate_pd_f9_004)",
}


def test_registry_mutations_exact_survivor_sets() -> None:
    stats = mutate_registry.run_mutation_check()
    assert stats["always_satisfied"]["generated"] == 195
    assert set(stats["always_satisfied"]["survived"]) == set()
    assert set(stats["swallow_exception_satisfied"]["survived"]) == set()
    assert set(stats["always_missing"]["survived"]) == EXPECTED_ALWAYS_MISSING_SURVIVORS
    assert stats["always_missing"]["killed"] == 142
