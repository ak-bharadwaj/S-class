import os
import sys

# Exact 20 sites / 24 parameters from the true B.1 table with exact file:line in src/sclass/product/
W16_ROWS = [
    ("src/sclass/product/enforcement_workspace_gate.py", 219, "authoritative_host_cost", "Budget ledger authoritative host cost"),
    ("src/sclass/product/adapter_diff_spec_anchors.py", 283, "invalidated_evidence", "Downstream evidence invalidation flag"),
    ("src/sclass/product/artifacts.py", 393, "check_digest", "Artifact verification digest validation"),
    ("src/sclass/product/execution_flow_testinput.py", 58, "rollback_inputs_bound", "Workflow baseline rollback binding"),
    ("src/sclass/product/execution_flow_testinput.py", 59, "verification_inputs_bound", "Workflow baseline verification binding"),
    ("src/sclass/product/execution_flow_testinput.py", 274, "is_before_red", "TestInputSet phase check"),
    ("src/sclass/product/f4_lane_selection.py", 228, "rollback_capability", "Rollback capability check"),
    ("src/sclass/product/f4_lane_selection.py", 357, "ddl_present", "DDL schema presence"),
    ("src/sclass/product/f8_step_pack.py", 147, "transcript_present", "Step-pack transcript presence flag"),
    ("src/sclass/product/f8_step_pack.py", 227, "bytes_equal", "Step-pack byte equality comparison"),
    ("src/sclass/product/isolation_claims.py", 36, "manifest_unchanged", "Write isolation manifest unchanged"),
    ("src/sclass/product/isolation_claims.py", 37, "environment_digest_match", "Write isolation environment digest match"),
    ("src/sclass/product/isolation_claims.py", 38, "test_is_green", "Write isolation test is green"),
    ("src/sclass/product/isolation_claims.py", 81, "green_test_run", "Delta scope authorization green test run"),
    ("src/sclass/product/isolation_claims.py", 198, "target_identity_match", "Target identity matching"),
    ("src/sclass/product/lifecycle_p0b.py", 41, "is_p8_repair", "P8 repair loop classification"),
    ("src/sclass/product/lifecycle_p3c_p8_p10.py", 196, "product_checks_pass", "Aggregate product checks pass"),
    ("src/sclass/product/lifecycle_p11.py", 337, "treated_as_complete", "P11 delivery completion flag"),
    ("src/sclass/product/lifecycle_p3b.py", 54, "supported", "Invariant support flag"),
    ("src/sclass/product/metrics.py", 476, "allow_replayed_digest", "Metric replayed digest computation flag"),
    ("src/sclass/product/registry_adapters.py", 857, "transcript_present", "F8 step-pack resume transcript flag"),
    ("src/sclass/product/threat_eval_regression_gate.py", 281, "recorded_action", "Data retention recorded action"),
    ("src/sclass/product/trust_model.py", 194, "user_presence_required", "Human presence waiver requirement"),
    ("src/sclass/product/wire_session_consequential_gate.py", 134, "version_conflict_typed_error", "Wire protocol conflict typed error"),
]

def main():
    print("=== W20: W16 / B.1 Table File:Line Verification ===")
    print("| Row | File:Line | Parameter | Purpose | Exact Line Content | MATCH |")
    print("|---|---|---|---|---|---|")

    all_matched = True
    for idx, (rel_path, line_no, param, purpose) in enumerate(W16_ROWS, 1):
        if not os.path.exists(rel_path):
            print(f"| {idx} | {rel_path}:{line_no} | {param} | {purpose} | FILE NOT FOUND | NO |")
            all_matched = False
            continue

        with open(rel_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if line_no > len(lines):
            print(f"| {idx} | {rel_path}:{line_no} | {param} | {purpose} | LINE EXCEEDS FILE LENGTH ({len(lines)}) | NO |")
            all_matched = False
            continue

        actual_line = lines[line_no - 1].strip()
        matched = param in actual_line
        if not matched:
            all_matched = False
        match_str = "YES" if matched else "NO"
        # Sanitize line content for markdown table
        sanitized_line = actual_line.replace("|", "\\|")
        print(f"| {idx} | `{rel_path}:{line_no}` | `{param}` | {purpose} | `{sanitized_line}` | {match_str} |")

    print(f"\nVerification outcome: {'ALL 24 ROWS MATCH EXACTLY' if all_matched else 'VERIFICATION FAILED'}")
    if not all_matched:
        sys.exit(1)

if __name__ == "__main__":
    main()
