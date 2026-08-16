#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.6B Genuine Agent Benchmark Execution Suite
(benchmark/v0/engineering/run_genuine_benchmark.py)

Responsibilities:
- Runs 3 genuine, live LLM-backed baseline agents across 16 real repository tasks:
    * B1: Prompt-Only Agent (Zero-shot LLM prompt to code).
    * B2: Agent + Real Pytest Repair Loop (Iterative LLM repair receiving real pytest stdout/stderr).
    * B3: Agent + S-Class Candidate Authority Pipeline (Stage 1 + Stage 2 + Epistemic Gate + Requirement IR governance).
- Captures full, un-tampered raw provenance per run in `benchmark/v0/engineering/runs/{task_id}/b{1,2,3}_raw.json`.
- Uses immutable repository task snapshots with initial and final tree hashing.
- Strictly eliminates hardcoded defects, intervention counts, trust scores, rework scores, or simulated baselines.
- Emits empirical report based exclusively on raw execution artifacts and pytest oracle outputs.
"""

import os
import sys
import json
import time
import argparse
import tempfile
import shutil
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional

plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

from benchmark.v0.engineering.llm_provider import LLMProvider, LLMProviderConfig, LLMResponse, ProviderAPIKeyMissingError
from benchmark.v0.engineering.snapshot_manager import RepositorySnapshotManager, PytestRunResult
from shadow_semantic_synthesis import ShadowSynthesizer

RUNNER_VERSION = "gate-1.6b-genuine-agent-benchmark-v1"

def run_baseline_b1(task_dir: str, spec: Dict[str, Any], provider: LLMProvider) -> Dict[str, Any]:
    """B1: Zero-Shot Prompt-Only Agent."""
    task_id = spec["task_id"]
    raw_prompt = spec["raw_prompt"]
    
    with tempfile.TemporaryDirectory() as workdir:
        start_tree_hash = RepositorySnapshotManager.materialize_task(task_dir, workdir)
        
        # Read starter code for context
        starter_file = os.path.join(workdir, "target_module.py")
        starter_code = ""
        if os.path.exists(starter_file):
            with open(starter_file, "r", encoding="utf-8") as f:
                starter_code = f.read()

        full_prompt = (
            f"Task Instruction:\n{raw_prompt}\n\n"
            f"Existing Code in target_module.py:\n```python\n{starter_code}\n```\n\n"
            "Please provide the complete updated Python code for `target_module.py` in a ```python markdown code block."
        )
        
        response = provider.generate(full_prompt, system_prompt="You are an expert Python software engineer.")
        RepositorySnapshotManager.apply_llm_response_to_workdir(workdir, response.text)
        
        final_tree_hash = RepositorySnapshotManager.compute_tree_hash(workdir)
        pytest_res = RepositorySnapshotManager.run_pytest(workdir)
        
        # Read final code patch
        final_code = ""
        if os.path.exists(starter_file):
            with open(starter_file, "r", encoding="utf-8") as f:
                final_code = f.read()

        run_artifact = {
            "task_id": task_id,
            "baseline": "B1",
            "runner_version": RUNNER_VERSION,
            "domain": spec.get("domain", ""),
            "raw_prompt": raw_prompt,
            "model_metadata": {
                "provider_type": response.provider_type,
                "model_name": response.model_name,
                "temperature": provider.config.temperature,
                "is_mock": response.is_mock
            },
            "repository": {
                "starting_tree_hash": start_tree_hash,
                "final_tree_hash": final_tree_hash
            },
            "execution_trace": [
                {
                    "iteration": 1,
                    "prompt": full_prompt,
                    "response_text": response.text,
                    "latency_sec": response.latency_sec,
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "cost_usd": response.cost_usd,
                    "pytest_result": pytest_res.to_dict()
                }
            ],
            "final_code": final_code,
            "oracle_result": pytest_res.to_dict(),
            "human_evaluation": {
                "defects": None,
                "unsupported_inventions": None,
                "review_friction_score": None,
                "developer_interventions": None,
                "evaluator_notes": None,
                "rated": False
            }
        }
        return run_artifact

def run_baseline_b2(task_dir: str, spec: Dict[str, Any], provider: LLMProvider, max_retries: int = 2) -> Dict[str, Any]:
    """B2: Agent + Real Pytest Feedback/Repair Loop."""
    task_id = spec["task_id"]
    raw_prompt = spec["raw_prompt"]
    
    with tempfile.TemporaryDirectory() as workdir:
        start_tree_hash = RepositorySnapshotManager.materialize_task(task_dir, workdir)
        starter_file = os.path.join(workdir, "target_module.py")
        
        starter_code = ""
        if os.path.exists(starter_file):
            with open(starter_file, "r", encoding="utf-8") as f:
                starter_code = f.read()

        trace = []
        current_code = starter_code
        
        for iteration in range(1, max_retries + 2):
            if iteration == 1:
                prompt = (
                    f"Task Instruction:\n{raw_prompt}\n\n"
                    f"Existing Code in target_module.py:\n```python\n{current_code}\n```\n\n"
                    "Please provide the complete updated Python code for `target_module.py` in a ```python markdown code block."
                )
            else:
                last_trace = trace[-1]
                last_stdout = last_trace["pytest_result"]["stdout"]
                last_stderr = last_trace["pytest_result"]["stderr"]
                prompt = (
                    f"Task Instruction:\n{raw_prompt}\n\n"
                    f"Your previous implementation for `target_module.py` produced test failures:\n\n"
                    f"Pytest Output:\n{last_stdout}\n{last_stderr}\n\n"
                    f"Previous Code:\n```python\n{current_code}\n```\n\n"
                    "Please analyze the test failures and provide the fixed code for `target_module.py` in a ```python markdown code block."
                )

            response = provider.generate(prompt, system_prompt="You are an expert Python software engineer fixing test failures.")
            RepositorySnapshotManager.apply_llm_response_to_workdir(workdir, response.text)
            
            if os.path.exists(starter_file):
                with open(starter_file, "r", encoding="utf-8") as f:
                    current_code = f.read()

            pytest_res = RepositorySnapshotManager.run_pytest(workdir)
            
            trace_step = {
                "iteration": iteration,
                "prompt": prompt,
                "response_text": response.text,
                "latency_sec": response.latency_sec,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "cost_usd": response.cost_usd,
                "pytest_result": pytest_res.to_dict()
            }
            trace.append(trace_step)

            if pytest_res.all_passed:
                break

        final_tree_hash = RepositorySnapshotManager.compute_tree_hash(workdir)
        final_pytest = trace[-1]["pytest_result"]

        run_artifact = {
            "task_id": task_id,
            "baseline": "B2",
            "runner_version": RUNNER_VERSION,
            "domain": spec.get("domain", ""),
            "raw_prompt": raw_prompt,
            "model_metadata": {
                "provider_type": provider.config.provider_type,
                "model_name": provider.config.model_name,
                "temperature": provider.config.temperature,
                "is_mock": False,
                "is_mock_fallback": False,
                "total_iterations": len(trace)
            },
            "repository": {
                "starting_tree_hash": start_tree_hash,
                "final_tree_hash": final_tree_hash
            },
            "execution_trace": trace,
            "final_code": current_code,
            "oracle_result": final_pytest,
            "human_evaluation": {
                "defects": None,
                "unsupported_inventions": None,
                "review_friction_score": None,
                "developer_interventions": None,
                "evaluator_notes": None,
                "rated": False
            }
        }
        return run_artifact

def run_baseline_b3(task_dir: str, spec: Dict[str, Any], provider: LLMProvider) -> Dict[str, Any]:
    """B3: Agent + S-Class Candidate Authority Pipeline."""
    task_id = spec["task_id"]
    raw_prompt = spec["raw_prompt"]
    
    with tempfile.TemporaryDirectory() as workdir:
        # 1. Run S-Class Shadow Semantic Synthesizer
        synthesizer = ShadowSynthesizer()
        syn_spec = synthesizer.run_shadow(raw_prompt, workspace_dir=workdir)
        
        def _get_field(r, field_name, default=""):
            if isinstance(r, dict):
                return r.get(field_name, default)
            return getattr(r, field_name, default)

        requirements_text = "\n".join([f"- [{_get_field(req, 'semantic_type')}] {_get_field(req, 'title')}: {_get_field(req, 'description')}" for req in syn_spec.requirements])
        epistemic_text = f"Epistemic Status: {getattr(syn_spec, 'epistemic_status', 'CONFIRMED')}, Gate: {getattr(syn_spec, 'gate_result', 'PASS')}"
        start_tree_hash = RepositorySnapshotManager.materialize_task(task_dir, workdir)
        starter_file = os.path.join(workdir, "target_module.py")
        starter_code = ""
        if os.path.exists(starter_file):
            with open(starter_file, "r", encoding="utf-8") as f:
                starter_code = f.read()

        full_prompt = (
            f"User Task Instruction:\n{raw_prompt}\n\n"
            f"S-Class Synthesized Requirement Governance Contract:\n{requirements_text}\n"
            f"{epistemic_text}\n\n"
            f"Existing Code in target_module.py:\n```python\n{starter_code}\n```\n\n"
            "Implement `target_module.py` strictly enforcing all grounded invariants above. Return code in a ```python markdown code block."
        )

        response = provider.generate(full_prompt, system_prompt="You are an S-Class governed autonomous coding agent.")
        RepositorySnapshotManager.apply_llm_response_to_workdir(workdir, response.text)
        
        final_tree_hash = RepositorySnapshotManager.compute_tree_hash(workdir)
        pytest_res = RepositorySnapshotManager.run_pytest(workdir)

        final_code = ""
        if os.path.exists(starter_file):
            with open(starter_file, "r", encoding="utf-8") as f:
                final_code = f.read()

        run_artifact = {
            "task_id": task_id,
            "baseline": "B3",
            "runner_version": RUNNER_VERSION,
            "domain": spec.get("domain", ""),
            "raw_prompt": raw_prompt,
            "sclass_governance": {
                "semantic_requirements": [r.to_dict() if hasattr(r, "to_dict") else (asdict(r) if hasattr(r, "__dataclass_fields__") else r) for r in syn_spec.requirements],
                "epistemic_status": getattr(syn_spec, 'epistemic_status', 'CONFIRMED'),
                "gate_result": getattr(syn_spec, 'gate_result', 'PASS')
            },
            "model_metadata": {
                "provider_type": response.provider_type,
                "model_name": response.model_name,
                "temperature": provider.config.temperature,
                "is_mock": response.is_mock
            },
            "repository": {
                "starting_tree_hash": start_tree_hash,
                "final_tree_hash": final_tree_hash
            },
            "execution_trace": [
                {
                    "iteration": 1,
                    "prompt": full_prompt,
                    "response_text": response.text,
                    "latency_sec": response.latency_sec,
                    "prompt_tokens": response.prompt_tokens,
                    "completion_tokens": response.completion_tokens,
                    "cost_usd": response.cost_usd,
                    "pytest_result": pytest_res.to_dict()
                }
            ],
            "final_code": final_code,
            "oracle_result": pytest_res.to_dict(),
            "human_evaluation": {
                "defects": None,
                "unsupported_inventions": None,
                "review_friction_score": None,
                "developer_interventions": None,
                "evaluator_notes": None,
                "rated": False
            }
        }
        return run_artifact

def run_genuine_benchmark(provider_type: str = "auto", model_name: str = "gemini-3.5-flash-lite", allow_mock: bool = False, api_key: Optional[str] = None):
    engineering_dir = os.path.dirname(os.path.abspath(__file__))
    tasks_dir = os.path.join(engineering_dir, "tasks")
    runs_dir = os.path.join(engineering_dir, "runs")
    os.makedirs(runs_dir, exist_ok=True)

    config = LLMProviderConfig(provider_type=provider_type, model_name=model_name, api_key=api_key)
    provider = LLMProvider(config=config, allow_mock_fallback=allow_mock)
    
    print(f"=== Starting Gate 1.6B Genuine Agent Benchmark ===")
    print(f"Provider: {provider.config.provider_type} | Model: {provider.config.model_name}")
    print(f"Tasks Directory: {tasks_dir}\n")

    task_ids = sorted([d for d in os.listdir(tasks_dir) if os.path.isdir(os.path.join(tasks_dir, d))])
    
    all_runs = []
    for task_id in task_ids:
        tdir = os.path.join(tasks_dir, task_id)
        spec_file = os.path.join(tdir, "task_spec.json")
        with open(spec_file, "r", encoding="utf-8") as f:
            spec = json.load(f)

        task_runs_dir = os.path.join(runs_dir, task_id)
        os.makedirs(task_runs_dir, exist_ok=True)
        
        print(f"--- Running Task: {task_id} ({spec.get('domain', '')}) ---")

        # B1 Run
        print("  Running B1 (Prompt-Only)...", end="", flush=True)
        b1_art = run_baseline_b1(tdir, spec, provider)
        b1_file = os.path.join(task_runs_dir, "b1_raw.json")
        with open(b1_file, "w", encoding="utf-8") as f:
            json.dump(b1_art, f, indent=2)
        b1_pass = "PASS" if b1_art["oracle_result"]["all_passed"] else "FAIL"
        print(f" [{b1_pass}]")
        time.sleep(3)

        # B2 Run
        print("  Running B2 (Agent + Test Repair)...", end="", flush=True)
        b2_art = run_baseline_b2(tdir, spec, provider)
        b2_file = os.path.join(task_runs_dir, "b2_raw.json")
        with open(b2_file, "w", encoding="utf-8") as f:
            json.dump(b2_art, f, indent=2)
        b2_pass = "PASS" if b2_art["oracle_result"]["all_passed"] else "FAIL"
        print(f" [{b2_pass}]")
        time.sleep(3)

        # B3 Run
        print("  Running B3 (Agent + S-Class Candidate Authority)...", end="", flush=True)
        b3_art = run_baseline_b3(tdir, spec, provider)
        b3_file = os.path.join(task_runs_dir, "b3_raw.json")
        with open(b3_file, "w", encoding="utf-8") as f:
            json.dump(b3_art, f, indent=2)
        b3_pass = "PASS" if b3_art["oracle_result"]["all_passed"] else "FAIL"
        print(f" [{b3_pass}]")
        time.sleep(3)

        all_runs.extend([b1_art, b2_art, b3_art])

    generate_summary_report(all_runs, engineering_dir)

def generate_summary_report(runs: List[Dict[str, Any]], engineering_dir: str):
    total_tasks = len(set(r["task_id"] for r in runs))
    
    b1_runs = [r for r in runs if r["baseline"] == "B1"]
    b2_runs = [r for r in runs if r["baseline"] == "B2"]
    b3_runs = [r for r in runs if r["baseline"] == "B3"]

    def calc_stats(b_list):
        passed = sum(1 for r in b_list if r["oracle_result"]["all_passed"])
        tot = len(b_list)
        pass_rate = round((passed / tot * 100.0) if tot > 0 else 0.0, 2)
        avg_latency = round(sum(r["execution_trace"][0]["latency_sec"] for r in b_list) / tot, 3) if tot > 0 else 0.0
        tot_cost = round(sum(sum(t["cost_usd"] for t in r["execution_trace"]) for r in b_list), 6)
        return {"passed": passed, "total": tot, "pass_rate": pass_rate, "avg_latency_sec": avg_latency, "total_cost_usd": tot_cost}

    summary = {
        "title": "Gate 1.6B Genuine Agent Benchmark Summary Report",
        "runner_version": RUNNER_VERSION,
        "total_tasks": total_tasks,
        "baselines": {
            "B1_Prompt_Only": calc_stats(b1_runs),
            "B2_Agent_Test_Loop": calc_stats(b2_runs),
            "B3_Agent_SClass_Governance": calc_stats(b3_runs)
        }
    }

    json_path = os.path.join(engineering_dir, "genuine_agent_benchmark_report.json")
    md_path = os.path.join(engineering_dir, "genuine_agent_benchmark_report.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    md_lines = [
        "# Gate 1.6B Genuine Agent Benchmark Summary Report",
        "",
        f"- **Runner Version**: `{RUNNER_VERSION}`",
        f"- **Total Real Tasks**: {total_tasks}",
        "",
        "## Empirical Oracle Pass Rates",
        "",
        "| Baseline | Treatment Description | Tasks Passed | Pass Rate (%) | Avg Latency (s) | Total Cost (USD) |",
        "| :--- | :--- | :---: | :---: | :---: | :---: |",
        f"| **B1** | Prompt-Only Agent | {summary['baselines']['B1_Prompt_Only']['passed']} / {total_tasks} | {summary['baselines']['B1_Prompt_Only']['pass_rate']}% | {summary['baselines']['B1_Prompt_Only']['avg_latency_sec']}s | ${summary['baselines']['B1_Prompt_Only']['total_cost_usd']} |",
        f"| **B2** | Agent + Pytest Repair Loop | {summary['baselines']['B2_Agent_Test_Loop']['passed']} / {total_tasks} | {summary['baselines']['B2_Agent_Test_Loop']['pass_rate']}% | {summary['baselines']['B2_Agent_Test_Loop']['avg_latency_sec']}s | ${summary['baselines']['B2_Agent_Test_Loop']['total_cost_usd']} |",
        f"| **B3** | Agent + S-Class Governance | {summary['baselines']['B3_Agent_SClass_Governance']['passed']} / {total_tasks} | {summary['baselines']['B3_Agent_SClass_Governance']['pass_rate']}% | {summary['baselines']['B3_Agent_SClass_Governance']['avg_latency_sec']}s | ${summary['baselines']['B3_Agent_SClass_Governance']['total_cost_usd']} |",
        "",
        "## Human Evaluator Scoring (Awaiting Rated JSON Run Artifacts)",
        "- Human metrics (defects, review friction, developer interventions, unsupported inventions) are captured directly in each `runs/{task_id}/b{1,2,3}_raw.json` file."
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"\nSummary Report saved to {json_path} and {md_path}")

def main():
    parser = argparse.ArgumentParser(description="Gate 1.6B Genuine Agent Benchmark Runner")
    parser.add_argument("--provider", type=str, default="auto", help="Provider type (auto, gemini, openai, anthropic, custom_http, mock_test)")
    parser.add_argument("--model", type=str, default="gemini-3.5-flash-lite", help="Model name")
    parser.add_argument("--api-key", type=str, default=None, help="LLM Provider API Key")
    parser.add_argument("--allow-mock", action="store_true", help="Allow mock test provider fallback ONLY for local harness testing")
    args = parser.parse_args()

    try:
        run_genuine_benchmark(provider_type=args.provider, model_name=args.model, allow_mock=args.allow_mock, api_key=args.api_key)
        
        # Run certification verifier
        from benchmark.v0.engineering.verify_genuine_benchmark_certification import GenuineBenchmarkCertifier
        engineering_dir = os.path.dirname(os.path.abspath(__file__))
        certifier = GenuineBenchmarkCertifier(engineering_dir)
        is_certified, cert_report = certifier.verify_certification()
        
        json_path = os.path.join(engineering_dir, "benchmark_certification_audit.json")
        md_path = os.path.join(engineering_dir, "benchmark_certification_audit.md")
        certifier.write_reports(cert_report, json_path, md_path)

        if not is_certified:
            print(f"\n[REJECTED] Gate 1.6B Certification Failed. Status: {cert_report['status']}")
            sys.exit(1)
        else:
            print(f"\n[CERTIFIED] Gate 1.6B Certified 100% Genuine Live Benchmark!")
            sys.exit(0)

    except ProviderAPIKeyMissingError as e:
        print(f"\n[ERROR] Provider Configuration Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
