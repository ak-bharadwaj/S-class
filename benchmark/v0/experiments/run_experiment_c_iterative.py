#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.3 Iterative Grounded Specification Refinement Runner
(benchmark/v0/experiments/run_experiment_c_iterative.py)

Responsibilities:
- Executes 3-pass iterative grounded refinement across engineering tasks.
- Pass 1: Grounded Core Extraction (Explicit + direct domain derivations).
- Pass 2: Targeted Coverage Audit & Invariant Elaboration (Missing MUST invariants & edge-case guards).
- Pass 3: Epistemic Boundary & Completeness Verification (Statutory rules, crash recovery, UNKNOWN surfacing).
- Enforces strict provenance logging for every single pass (latency, tokens, cost, git commit, prompts).
- Writes `experiment_c_pass1.json`, `experiment_c_pass2.json`, `experiment_c_pass3.json`, and `experiment_c_iterative_summary.json` per task directory.
- Fails loudly on missing credentials; zero silent mocks.
"""

import os
import sys
import json
import time
import argparse
from typing import Dict, List, Any

plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

from benchmark.v0.experiments.llm_client import LLMProvenanceClient

SYSTEM_PROMPT_PASS_1 = """You are the S-Class Grounded Domain Inference Engine (Pass 1 - Core Extraction).
Your job is to synthesize software engineering requirements from the user prompt with STRICT EPISTEMIC SELF-RESTRAINT:

1. Requirement Categorization:
   - EXPLICIT: Requirements directly and unambiguously stated in the prompt.
   - DERIVED_JUSTIFIED: Requirements strictly mathematically, architecturally, or operationally necessary to implement the stated goal without defect. Every DERIVED_JUSTIFIED requirement MUST include a rigorous 3-step why-chain (Why 1: Context/Risk -> Why 2: Technical Mechanism -> Why 3: Mandatory Invariant).
   - SUPPORTED: Non-functional or platform constraints directly supporting the scope.
   - UNKNOWN: Any operational parameter, storage choice, or protocol unstated in the prompt.

2. Anti-Hallucination Barrier:
   - DO NOT fabricate full-stack UI pages (e.g. login screens, dashboards, admin portals) unless explicitly requested.
   - DO NOT fabricate arbitrary third-party providers (e.g. Stripe, Auth0, AWS) unless explicitly requested.

3. Output Schema:
{
  "experiment": "EXPERIMENT C — Pass 1 (Grounded Core Extraction)",
  "task_id": "<TASK_ID>",
  "inferred_requirements": [
    {
      "requirement_id": "<REQ_ID>",
      "title": "<TITLE>",
      "description": "<DESCRIPTION>",
      "type": "FUNCTIONAL" | "NON_FUNCTIONAL" | "SECURITY" | "BEHAVIORAL" | "INVARIANT",
      "epistemic_status": "EXPLICIT" | "DERIVED_JUSTIFIED" | "SUPPORTED" | "UNKNOWN",
      "provenance": "USER_PROMPT" | "<DOMAIN_PROVENANCE>" | "UNSUPPORTED",
      "confidence": <FLOAT_0_TO_1>,
      "justification": "<WHY_CHAIN_OR_RATIONALE>"
    }
  ]
}
"""

SYSTEM_PROMPT_PASS_2 = """You are the S-Class Grounded Domain Inference Engine (Pass 2 - Targeted Coverage Audit).
Your job is to analyze the requirements generated in Pass 1 and identify CRITICAL MISSING INVARIANTS AND GUARDS:

1. Targeted Gap Analysis:
   - What non-negotiable domain invariants, concurrency guards, failure recovery boundaries, data integrity rules, or edge-case behaviors are strictly required by the domain but MISSING from Pass 1?
   - Formulate ONLY the missing requirements. Do NOT repeat or duplicate Pass 1 requirements.
   - Every derived requirement must include a rigorous 3-step why-chain.

2. Anti-Hallucination Barrier:
   - Do NOT fabricate full-stack UI pages or arbitrary third-party providers.
   - If an operational choice or standard is unstated, mark it explicitly as UNKNOWN.

3. Output Schema:
{
  "experiment": "EXPERIMENT C — Pass 2 (Targeted Coverage Audit)",
  "task_id": "<TASK_ID>",
  "missing_requirements": [
    {
      "requirement_id": "<REQ_ID>",
      "title": "<TITLE>",
      "description": "<DESCRIPTION>",
      "type": "FUNCTIONAL" | "NON_FUNCTIONAL" | "SECURITY" | "BEHAVIORAL" | "INVARIANT",
      "epistemic_status": "DERIVED_JUSTIFIED" | "SUPPORTED" | "UNKNOWN",
      "provenance": "<DOMAIN_PROVENANCE>" | "UNSUPPORTED",
      "confidence": <FLOAT_0_TO_1>,
      "justification": "<WHY_CHAIN_OR_RATIONALE>"
    }
  ]
}
"""

SYSTEM_PROMPT_PASS_3 = """You are the S-Class Grounded Domain Inference Engine (Pass 3 - Boundary & Completeness Verification).
Your job is to perform a final completeness audit of the merged specification:

1. Final Boundary Verification:
   - Identify any remaining statutory regulatory invariants (e.g. HIPAA, DO-178C, PCI-DSS boundaries), operational lifecycle boundaries (graceful shutdown, power loss, crash recovery), or unstated operational decisions.
   - Surface all unstated technology choices (storage engines, identity providers, network transports) explicitly as UNKNOWN.
   - Do NOT repeat existing requirements from Pass 1 or Pass 2.

2. Output Schema:
{
  "experiment": "EXPERIMENT C — Pass 3 (Boundary & Completeness Verification)",
  "task_id": "<TASK_ID>",
  "final_boundary_requirements": [
    {
      "requirement_id": "<REQ_ID>",
      "title": "<TITLE>",
      "description": "<DESCRIPTION>",
      "type": "FUNCTIONAL" | "NON_FUNCTIONAL" | "SECURITY" | "BEHAVIORAL" | "INVARIANT",
      "epistemic_status": "DERIVED_JUSTIFIED" | "SUPPORTED" | "UNKNOWN",
      "provenance": "<DOMAIN_PROVENANCE>" | "UNSUPPORTED",
      "confidence": <FLOAT_0_TO_1>,
      "justification": "<WHY_CHAIN_OR_RATIONALE>"
    }
  ]
}
"""

def run_task_iterative_refinement(task_dir: str, client: LLMProvenanceClient) -> Dict[str, Any]:
    gt_path = os.path.join(task_dir, "ground_truth_labels.json")
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Missing ground truth file at {gt_path}")

    with open(gt_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    task_id = gt["task_id"]
    domain = gt.get("domain", "engineering")
    raw_prompt = gt["raw_prompt"]
    forbidden = gt.get("forbidden_hallucinations", [])

    print(f"\n=======================================================")
    print(f"[{task_id}] STARTING 3-PASS ITERATIVE REFINEMENT ({domain})")
    print(f"=======================================================")

    # --- PASS 1: Grounded Core Extraction ---
    user_prompt_1 = (
        f"Synthesize formal software engineering requirements for the following prompt in the domain of '{domain}':\n"
        f"Prompt: \"{raw_prompt}\"\n\n"
        f"Domain Guidance:\n"
        f"- Enforce core invariants and essential derived domain rules.\n"
        f"- Do not generate unrequested UI pages or hallucinate arbitrary features (specifically avoid: {', '.join(forbidden)}).\n"
        f"- If key operational choices, providers, or format standards are unstated, mark them explicitly as UNKNOWN.\n\n"
        f"Return strictly valid JSON as specified in the system instructions."
    )

    print(f"[{task_id}] Executing Pass 1 (Core Extraction)...")
    prov_1 = client.call_model(
        system_prompt=SYSTEM_PROMPT_PASS_1,
        user_prompt=user_prompt_1,
        task_id=task_id,
        experiment_id="EXPERIMENT_C_PASS_1_CORE_EXTRACTION",
        input_context={"pass": 1, "raw_prompt": raw_prompt, "domain": domain}
    )
    parsed_1 = prov_1["parsed_output"]
    parsed_1["provenance_metadata"] = prov_1["provenance"]
    pass1_reqs = parsed_1.get("inferred_requirements", [])

    with open(os.path.join(task_dir, "experiment_c_pass1.json"), "w", encoding="utf-8") as f:
        json.dump(parsed_1, f, indent=2)

    print(f"[{task_id}] Pass 1 Complete: {len(pass1_reqs)} requirements (latency: {prov_1['provenance']['latency_ms']}ms, tokens: {prov_1['provenance']['token_usage']['total_tokens']})")

    # Inter-pass pacing
    time.sleep(12)

    # --- PASS 2: Targeted Coverage Audit ---
    req_summary_pass1 = "\n".join(
        f"- [{r.get('requirement_id', f'REQ-P1-{i}')}] {r.get('title', '')} ({r.get('epistemic_status', '')}): {r.get('description', '')}"
        for i, r in enumerate(pass1_reqs)
    )

    user_prompt_2 = (
        f"Original Prompt: \"{raw_prompt}\"\n"
        f"Domain: '{domain}'\n\n"
        f"Pass 1 Requirements already synthesized:\n{req_summary_pass1}\n\n"
        f"Coverage Audit Directive:\n"
        f"- Analyze what critical domain invariants, edge cases, failure modes, data integrity rules, or concurrency controls are MISSING from the above list to fulfill the prompt completely.\n"
        f"- Synthesize ONLY the missing requirements with 3-step why-chains.\n"
        f"- Do NOT duplicate any requirement already in Pass 1.\n"
        f"- Avoid hallucinating unrequested fullstack UI features ({', '.join(forbidden)}).\n\n"
        f"Return strictly valid JSON as specified in the system instructions."
    )

    print(f"[{task_id}] Executing Pass 2 (Coverage Audit)...")
    prov_2 = client.call_model(
        system_prompt=SYSTEM_PROMPT_PASS_2,
        user_prompt=user_prompt_2,
        task_id=task_id,
        experiment_id="EXPERIMENT_C_PASS_2_COVERAGE_AUDIT",
        input_context={"pass": 2, "raw_prompt": raw_prompt, "pass1_count": len(pass1_reqs)}
    )
    parsed_2 = prov_2["parsed_output"]
    parsed_2["provenance_metadata"] = prov_2["provenance"]
    pass2_reqs = parsed_2.get("missing_requirements", [])

    with open(os.path.join(task_dir, "experiment_c_pass2.json"), "w", encoding="utf-8") as f:
        json.dump(parsed_2, f, indent=2)

    print(f"[{task_id}] Pass 2 Complete: {len(pass2_reqs)} missing requirements identified (latency: {prov_2['provenance']['latency_ms']}ms, tokens: {prov_2['provenance']['token_usage']['total_tokens']})")

    # Inter-pass pacing
    time.sleep(12)

    # --- PASS 3: Boundary & Epistemic Completeness Check ---
    merged_1_2 = pass1_reqs + pass2_reqs
    req_summary_merged = "\n".join(
        f"- [{r.get('requirement_id', f'REQ-M-{i}')}] {r.get('title', '')} ({r.get('epistemic_status', '')}): {r.get('description', '')}"
        for i, r in enumerate(merged_1_2)
    )

    user_prompt_3 = (
        f"Original Prompt: \"{raw_prompt}\"\n"
        f"Domain: '{domain}'\n\n"
        f"Current Merged Specification (Pass 1 + Pass 2):\n{req_summary_merged}\n\n"
        f"Final Completeness Audit Directive:\n"
        f"- Perform a final boundary and epistemic check for statutory safety rules, lifecycle boundaries (graceful shutdown / recovery), and unstated operational parameters.\n"
        f"- Surface any unstated architecture decisions (storage engines, token formats, identity providers, protocols) explicitly as UNKNOWN.\n"
        f"- Synthesize ONLY final missing boundary/unknown items. Do NOT duplicate existing items.\n\n"
        f"Return strictly valid JSON as specified in the system instructions."
    )

    print(f"[{task_id}] Executing Pass 3 (Boundary & Completeness Verification)...")
    prov_3 = client.call_model(
        system_prompt=SYSTEM_PROMPT_PASS_3,
        user_prompt=user_prompt_3,
        task_id=task_id,
        experiment_id="EXPERIMENT_C_PASS_3_BOUNDARY_VERIFICATION",
        input_context={"pass": 3, "raw_prompt": raw_prompt, "merged_count": len(merged_1_2)}
    )
    parsed_3 = prov_3["parsed_output"]
    parsed_3["provenance_metadata"] = prov_3["provenance"]
    pass3_reqs = parsed_3.get("final_boundary_requirements", [])

    with open(os.path.join(task_dir, "experiment_c_pass3.json"), "w", encoding="utf-8") as f:
        json.dump(parsed_3, f, indent=2)

    print(f"[{task_id}] Pass 3 Complete: {len(pass3_reqs)} final boundary items identified (latency: {prov_3['provenance']['latency_ms']}ms, tokens: {prov_3['provenance']['token_usage']['total_tokens']})")

    # --- Epistemic Deduplication & Cumulative Summary ---
    all_cumulative = []
    seen_titles = set()

    for idx, r in enumerate(pass1_reqs):
        r_copy = dict(r)
        r_copy["introduced_in_pass"] = 1
        all_cumulative.append(r_copy)
        seen_titles.add(r_copy.get("title", "").strip().lower())

    for idx, r in enumerate(pass2_reqs):
        t_clean = r.get("title", "").strip().lower()
        if t_clean not in seen_titles and t_clean:
            r_copy = dict(r)
            r_copy["introduced_in_pass"] = 2
            all_cumulative.append(r_copy)
            seen_titles.add(t_clean)

    for idx, r in enumerate(pass3_reqs):
        t_clean = r.get("title", "").strip().lower()
        if t_clean not in seen_titles and t_clean:
            r_copy = dict(r)
            r_copy["introduced_in_pass"] = 3
            all_cumulative.append(r_copy)
            seen_titles.add(t_clean)

    summary = {
        "task_id": task_id,
        "domain": domain,
        "raw_prompt": raw_prompt,
        "passes": {
            "pass_1": {
                "generated_count": len(pass1_reqs),
                "latency_ms": prov_1["provenance"]["latency_ms"],
                "total_tokens": prov_1["provenance"]["token_usage"]["total_tokens"],
                "estimated_cost_usd": prov_1["provenance"]["estimated_cost_usd"]
            },
            "pass_2": {
                "generated_count": len(pass2_reqs),
                "latency_ms": prov_2["provenance"]["latency_ms"],
                "total_tokens": prov_2["provenance"]["token_usage"]["total_tokens"],
                "estimated_cost_usd": prov_2["provenance"]["estimated_cost_usd"]
            },
            "pass_3": {
                "generated_count": len(pass3_reqs),
                "latency_ms": prov_3["provenance"]["latency_ms"],
                "total_tokens": prov_3["provenance"]["token_usage"]["total_tokens"],
                "estimated_cost_usd": prov_3["provenance"]["estimated_cost_usd"]
            }
        },
        "cumulative_progression": {
            "pass_1_count": len(pass1_reqs),
            "pass_1_plus_2_count": len([r for r in all_cumulative if r.get("introduced_in_pass") in [1, 2]]),
            "pass_1_plus_2_plus_3_count": len(all_cumulative)
        },
        "cumulative_requirements": all_cumulative
    }

    with open(os.path.join(task_dir, "experiment_c_iterative_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"[{task_id}] Cumulative Requirements: Pass 1={summary['cumulative_progression']['pass_1_count']} -> Pass 1+2={summary['cumulative_progression']['pass_1_plus_2_count']} -> Pass 1+2+3={summary['cumulative_progression']['pass_1_plus_2_plus_3_count']}")
    return summary

def main():
    parser = argparse.ArgumentParser(description="Run S-Class Experiment C 3-Pass Iterative Refinement.")
    parser.add_argument("--task", type=str, default="all", help="Task ID or folder name (task_01 to task_07 or all)")
    parser.add_argument("--provider", type=str, default=None, help="LLM provider (gemini, openai, anthropic, ollama)")
    parser.add_argument("--model", type=str, default=None, help="Model name (e.g. gemini-flash-lite-latest, gpt-4o-mini)")
    parser.add_argument("--api-key", type=str, default=None, help="API key for the selected provider")
    args = parser.parse_args()

    client = LLMProvenanceClient(
        provider=args.provider,
        model_name=args.model,
        api_key=args.api_key,
        temperature=0.0
    )

    exp_base = os.path.abspath(os.path.dirname(__file__))
    all_tasks = [f"task_0{i}" for i in range(1, 8)]

    if args.task == "all":
        target_tasks = all_tasks
    else:
        target_tasks = [args.task if args.task.startswith("task_") else f"task_{args.task}"]

    for idx, t in enumerate(target_tasks):
        td = os.path.join(exp_base, t)
        if os.path.isdir(td):
            if idx > 0:
                time.sleep(12)
            run_task_iterative_refinement(td, client)

if __name__ == "__main__":
    main()
