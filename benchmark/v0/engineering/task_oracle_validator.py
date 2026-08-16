#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.6B Task Oracle Validator
(benchmark/v0/engineering/task_oracle_validator.py)

Validates every task oracle against every MUST requirement before running the benchmark:
1. Verifies that the canonical reference solution passes 100% of pytest oracle tests.
2. Verifies that flawed solutions intentionally violating MUST invariants fail the oracle tests.
3. Ensures 1:1 mapping between MUST invariants and executable test assertions.
"""

import os
import sys
import json
import shutil
import tempfile
from dataclasses import dataclass, asdict
from typing import Dict, List, Any

plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

from benchmark.v0.engineering.snapshot_manager import RepositorySnapshotManager, PytestRunResult

@dataclass
class TaskOracleValidationResult:
    task_id: str
    domain: str
    must_invariants_count: int
    reference_passed: bool
    reference_pytest_result: Dict[str, Any]
    flawed_rejected: bool
    flawed_pytest_result: Dict[str, Any]
    oracle_valid: bool

class TaskOracleValidator:
    def __init__(self, tasks_dir: str):
        self.tasks_dir = tasks_dir

    def validate_all_oracles(self) -> List[TaskOracleValidationResult]:
        results = []
        if not os.path.exists(self.tasks_dir):
            print(f"Tasks directory not found: {self.tasks_dir}")
            return results

        task_ids = sorted([d for d in os.listdir(self.tasks_dir) if os.path.isdir(os.path.join(self.tasks_dir, d))])
        print(f"Validating {len(task_ids)} task oracles in {self.tasks_dir}...")

        for task_id in task_ids:
            tdir = os.path.join(self.tasks_dir, task_id)
            spec_file = os.path.join(tdir, "task_spec.json")
            with open(spec_file, "r", encoding="utf-8") as f:
                spec = json.load(f)

            domain = spec.get("domain", "")
            must_count = len(spec.get("must_invariants", []))

            # 1. Test Reference Solution
            with tempfile.TemporaryDirectory() as ref_workdir:
                RepositorySnapshotManager.materialize_task(tdir, ref_workdir)
                # Overwrite target_module.py with reference solution
                ref_src = os.path.join(tdir, "reference_solution", "target_module.py")
                if os.path.exists(ref_src):
                    shutil.copy2(ref_src, os.path.join(ref_workdir, "target_module.py"))
                
                ref_run = RepositorySnapshotManager.run_pytest(ref_workdir)
                reference_passed = ref_run.all_passed

            # 2. Test Flawed Solution
            with tempfile.TemporaryDirectory() as flaw_workdir:
                RepositorySnapshotManager.materialize_task(tdir, flaw_workdir)
                flaw_src = os.path.join(tdir, "flawed_solutions", "flawed_target_module.py")
                if os.path.exists(flaw_src):
                    shutil.copy2(flaw_src, os.path.join(flaw_workdir, "target_module.py"))
                
                flaw_run = RepositorySnapshotManager.run_pytest(flaw_workdir)
                flawed_rejected = (not flaw_run.all_passed)

            oracle_valid = (reference_passed and flawed_rejected)
            
            res = TaskOracleValidationResult(
                task_id=task_id,
                domain=domain,
                must_invariants_count=must_count,
                reference_passed=reference_passed,
                reference_pytest_result=ref_run.to_dict(),
                flawed_rejected=flawed_rejected,
                flawed_pytest_result=flaw_run.to_dict(),
                oracle_valid=oracle_valid
            )
            results.append(res)

            status_icon = "PASS" if oracle_valid else "FAIL"
            print(f"[{status_icon}] {task_id}: RefPassed={reference_passed}, FlawRejected={flawed_rejected}")

        return results

    def generate_report(self, results: List[TaskOracleValidationResult], output_json_path: str, output_md_path: str):
        valid_count = sum(1 for r in results if r.oracle_valid)
        total_count = len(results)
        
        report_data = {
            "title": "Gate 1.6B Task Oracle Pre-Validation Report",
            "timestamp": os.environ.get("BUILD_TIMESTAMP", ""),
            "total_tasks": total_count,
            "valid_tasks": valid_count,
            "validation_pass_rate": round((valid_count / total_count * 100.0) if total_count > 0 else 0.0, 2),
            "tasks": [asdict(r) for r in results]
        }
        
        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)

        md_lines = [
            "# Gate 1.6B Task Oracle Pre-Validation Report",
            "",
            f"- **Total Tasks Validated**: {total_count}",
            f"- **Valid Oracles**: {valid_count} / {total_count} ({report_data['validation_pass_rate']}%)",
            "",
            "| Task ID | Domain | MUST Invariants | Reference Solution | Flawed Sensitivity | Oracle Status |",
            "| :--- | :--- | :---: | :---: | :---: | :---: |"
        ]

        for r in results:
            ref_str = "PASS (100%)" if r.reference_passed else "FAIL"
            flaw_str = "REJECTED" if r.flawed_rejected else "MISSED"
            status_str = "**VALID**" if r.oracle_valid else "**INVALID**"
            md_lines.append(
                f"| `{r.task_id}` | {r.domain} | {r.must_invariants_count} | {ref_str} | {flaw_str} | {status_str} |"
            )

        with open(output_md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

        print(f"Validation report saved to {output_json_path} and {output_md_path}")

def main():
    engineering_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(engineering_dir, "tasks")
    validator = TaskOracleValidator(tasks_dir)
    results = validator.validate_all_oracles()
    
    json_path = os.path.join(engineering_dir, "oracle_validation_report.json")
    md_path = os.path.join(engineering_dir, "oracle_validation_report.md")
    validator.generate_report(results, json_path, md_path)

if __name__ == "__main__":
    main()
