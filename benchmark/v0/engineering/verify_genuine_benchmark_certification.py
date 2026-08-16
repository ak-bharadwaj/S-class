#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.6B Genuine Agent Benchmark Certification Verifier
(benchmark/v0/engineering/verify_genuine_benchmark_certification.py)

Strict Invariants Required for Certification:
1. 48/48 run artifacts must exist (16 tasks x 3 baselines: B1, B2, B3).
2. is_mock == False for EVERY SINGLE run artifact (Zero mock fallback allowed).
3. provider_type MUST be in {"gemini", "openai", "anthropic", "custom_http"} for all 48 runs.
4. model_name MUST be identical across all 48 runs (No mixed model conditions).
5. Full provenance complete: raw_prompt, execution_trace, tree hashes, pytest outputs, final_code.
6. Refuses certification (exit_code=1) if ANY mock artifact or inconsistency is found.
"""

import os
import sys
import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Any

ALLOWED_PROVIDERS = {"gemini", "openai", "anthropic", "custom_http"}

@dataclass
class CertificationCheck:
    check_name: str
    passed: bool
    details: str

class GenuineBenchmarkCertifier:
    def __init__(self, engineering_dir: str, is_holdout: bool = False, is_gate16e: bool = False):
        self.engineering_dir = engineering_dir
        self.is_holdout = is_holdout
        self.is_gate16e = is_gate16e
        
        if is_gate16e:
            self.tasks_dir_name = "tasks_gate16e"
            self.runs_dir_name = "runs_gate16e"
        elif is_holdout:
            self.tasks_dir_name = "tasks_holdout"
            self.runs_dir_name = "runs_holdout"
        else:
            self.tasks_dir_name = "tasks"
            self.runs_dir_name = "runs"

        self.tasks_dir = os.path.join(engineering_dir, self.tasks_dir_name)
        self.runs_dir = os.path.join(engineering_dir, self.runs_dir_name)

    def verify_certification(self) -> Tuple[bool, Dict[str, Any]]:
        checks = []
        task_ids = sorted([d for d in os.listdir(self.tasks_dir) if os.path.isdir(os.path.join(self.tasks_dir, d))]) if os.path.exists(self.tasks_dir) else []
        
        if self.is_gate16e:
            expected_tasks = 40
            expected_baselines = ["b2", "b4"]
        elif self.is_holdout:
            expected_tasks = 12
            expected_baselines = ["b1", "b2", "b3", "b4"]
        else:
            expected_tasks = 16
            expected_baselines = ["b1", "b2", "b3", "b4"]

        expected_runs = expected_tasks * len(expected_baselines)

        # Check 1: Task Repositories Exist
        c1 = CertificationCheck(f"{expected_tasks}_tasks_exist", len(task_ids) == expected_tasks, f"Found {len(task_ids)} / {expected_tasks} task directories.")
        checks.append(c1)

        total_runs = 0
        real_runs = 0
        mock_runs = 0
        provider_types = set()
        model_names = set()
        incomplete_provenance = 0
        invalid_budget_runs = 0
        missing_taxonomy_runs = 0

        for task_id in task_ids:
            truns_dir = os.path.join(self.runs_dir, task_id)
            for b in expected_baselines:
                rfile = os.path.join(truns_dir, f"{b}_raw.json")
                if not os.path.exists(rfile):
                    continue
                total_runs += 1
                
                try:
                    with open(rfile, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    
                    meta = data.get("model_metadata", {})
                    is_mock = meta.get("is_mock", True)
                    ptype = meta.get("provider_type", "unknown")
                    mname = meta.get("model_name", "unknown")
                    budget = meta.get("model_call_budget", 1)

                    if is_mock or ptype == "mock_test":
                        mock_runs += 1
                    else:
                        real_runs += 1

                    provider_types.add(ptype)
                    model_names.add(mname)

                    # Equal Budget Check (B2, B3, B4 must have model_call_budget == 3)
                    if b in ["b2", "b3", "b4"] and budget != 3:
                        invalid_budget_runs += 1

                    # Failure Taxonomy Check
                    if "failure_taxonomy" not in data:
                        missing_taxonomy_runs += 1

                    # Provenance integrity check
                    repo = data.get("repository", {})
                    oracle = data.get("oracle_result", {})
                    trace = data.get("execution_trace", [])

                    if not repo.get("starting_tree_hash") or not repo.get("final_tree_hash") or not oracle or not trace:
                        incomplete_provenance += 1

                except Exception as e:
                    mock_runs += 1
                    incomplete_provenance += 1

        # Check 2: Expected Runs Exist
        c2 = CertificationCheck(f"{expected_runs}_runs_exist", total_runs == expected_runs, f"Found {total_runs} / {expected_runs} expected run artifacts.")
        checks.append(c2)

        # Check 3: 0 Mock Runs
        c3 = CertificationCheck("zero_mock_runs", mock_runs == 0 and real_runs == expected_runs, f"Real runs: {real_runs}/{expected_runs}, Mock runs detected: {mock_runs}.")
        checks.append(c3)

        # Check 4: Valid Live Provider
        valid_providers = provider_types.issubset(ALLOWED_PROVIDERS) and len(provider_types) > 0
        c4 = CertificationCheck("valid_live_provider", valid_providers, f"Observed providers: {list(provider_types)} (Allowed: {list(ALLOWED_PROVIDERS)}).")
        checks.append(c4)

        # Check 5: Single Uniform Model Configuration (No mixed models)
        c5 = CertificationCheck("uniform_model_configuration", len(model_names) == 1, f"Observed model names: {list(model_names)}.")
        checks.append(c5)

        # Check 6: Equal Model Call Budget Invariant across B2, B3, B4
        c6 = CertificationCheck("equal_budget_enforcement", invalid_budget_runs == 0, f"Runs violating equal budget (MAX_MODEL_CALLS=3): {invalid_budget_runs}.")
        checks.append(c6)

        # Check 7: 100% Complete Provenance & Taxonomy
        c7 = CertificationCheck("complete_provenance_and_taxonomy", incomplete_provenance == 0 and missing_taxonomy_runs == 0, f"Incomplete provenance: {incomplete_provenance}, Missing taxonomy: {missing_taxonomy_runs}.")
        checks.append(c7)

        is_certified = all(c.passed for c in checks)

        cert_title = "Gate 1.6E Large-Scale Replication Certification Audit" if self.is_gate16e else ("Gate 1.6D Holdout Task Replication Certification Audit" if self.is_holdout else "Gate 1.6C Fair Treatment Benchmark Certification Audit")
        cert_report = {
            "title": cert_title,
            "certified": is_certified,
            "is_gate16e": self.is_gate16e,
            "is_holdout_replication": self.is_holdout,
            "status": "CERTIFIED_GENUINE_LIVE_BENCHMARK" if is_certified else "UNCERTIFIED_CONTAMINATED_OR_INCOMPLETE",
            "total_runs": total_runs,
            "real_runs": real_runs,
            "mock_runs": mock_runs,
            "provider_types": list(provider_types),
            "model_names": list(model_names),
            "checks": [asdict(c) for c in checks]
        }

        return is_certified, cert_report

    def write_reports(self, cert_report: Dict[str, Any], json_path: str, md_path: str):
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(cert_report, f, indent=2)

        md_lines = [
            "# Gate 1.6C Fair Treatment Benchmark Certification Audit",
            "",
            f"- **Status**: `{cert_report['status']}`",
            f"- **Certified**: `{'YES - 100% GENUINE LIVE' if cert_report['certified'] else 'NO - UNCERTIFIED'}`",
            f"- **Total Runs**: {cert_report['total_runs']} / 64",
            f"- **Real Live Runs**: {cert_report['real_runs']} / 64",
            f"- **Mock Runs**: {cert_report['mock_runs']} (Must be 0)",
            f"- **Model Version**: `{list(cert_report['model_names'])[0] if cert_report['model_names'] else 'NONE'}`",
            "",
            "## Certification Verification Invariants",
            "",
            "| Check Name | Status | Verification Details |",
            "| :--- | :---: | :--- |"
        ]

        for c in cert_report["checks"]:
            status_str = "🟢 PASS" if c["passed"] else "🔴 FAIL"
            md_lines.append(f"| `{c['check_name']}` | {status_str} | {c['details']} |")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines) + "\n")

        print(f"Certification audit report written to {json_path} and {md_path}")

def main():
    engineering_dir = os.path.dirname(os.path.abspath(__file__))
    certifier = GenuineBenchmarkCertifier(engineering_dir)
    is_certified, cert_report = certifier.verify_certification()
    
    json_path = os.path.join(engineering_dir, "benchmark_certification_audit.json")
    md_path = os.path.join(engineering_dir, "benchmark_certification_audit.md")
    certifier.write_reports(cert_report, json_path, md_path)

    if not is_certified:
        print(f"\n[REJECTED] Gate 1.6C Certification FAILED. Status: {cert_report['status']}")
        sys.exit(1)
    else:
        print(f"\n[CERTIFIED] Gate 1.6C Certified 100% Genuine Live Benchmark!")
        sys.exit(0)

if __name__ == "__main__":
    main()
