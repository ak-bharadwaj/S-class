#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.2 Experiment C Executable Runner
(benchmark/v0/experiments/run_experiment_c.py)

Responsibilities:
- Executes Stage 2 Grounded Domain Inference via real LLM API calls.
- Formulates engineering requirements with strict epistemic self-restraint (derives only justified rules with 3-step why-chains, surfaces unstated choices as UNKNOWN).
- Enforces strict provenance logging: git commit, model version, latency, prompt/completion tokens, cost.
- Writes immutable result to `benchmark/v0/experiments/task_XX/experiment_c_grounded_inference.json`.
- Fails loudly if credentials or API are unavailable; zero silent fallbacks or simulated mocks.
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

SYSTEM_PROMPT_STAGE_2 = """You are the S-Class Grounded Domain Inference Engine.
Your job is to synthesize software engineering requirements with STRICT EPISTEMIC SELF-RESTRAINT:

1. Requirement Categorization & Provenance:
   - EXPLICIT: Requirements directly and unambiguously stated in the prompt.
   - DERIVED_JUSTIFIED: Requirements that are strictly mathematically, architecturally, or operationally necessary to implement the stated goal without defect or system compromise. Every DERIVED_JUSTIFIED requirement MUST include a rigorous 3-step why-chain (Why 1: Problem/Context -> Why 2: Technical Mechanism -> Why 3: Mandatory Invariant).
   - SUPPORTED: Non-functional, architectural, or platform constraints directly supporting the scope.
   - UNKNOWN: Any operational parameter, storage choice, protocol standard, third-party provider, or policy that is unstated in the prompt. You MUST surface these as UNKNOWN rather than guessing or fabricating specific implementations.

2. Anti-Hallucination Barrier:
   - DO NOT fabricate full-stack UI pages (e.g. login screens, dashboards, admin portals) unless explicitly requested.
   - DO NOT fabricate arbitrary third-party providers (e.g. Stripe, Auth0, AWS) unless explicitly requested.

3. Output Schema:
Return strictly valid JSON adhering to this schema:
{
  "experiment": "EXPERIMENT C — Grounded Domain Inference",
  "task_id": "<TASK_ID>",
  "inferred_requirements": [
    {
      "requirement_id": "<REQ_ID_STRING>",
      "title": "<REQUIREMENT_TITLE>",
      "description": "<DETAILED_SPECIFICATION>",
      "type": "FUNCTIONAL" | "NON_FUNCTIONAL" | "SECURITY" | "BEHAVIORAL" | "INVARIANT",
      "epistemic_status": "EXPLICIT" | "DERIVED_JUSTIFIED" | "SUPPORTED" | "UNKNOWN",
      "provenance": "USER_PROMPT" | "<DOMAIN_PROVENANCE_STRING>" | "UNSUPPORTED",
      "confidence": <FLOAT_0_TO_1>,
      "justification": "<WHY_CHAIN_OR_RATIONALE>"
    }
  ]
}
"""

def run_task_experiment_c(task_dir: str, client: LLMProvenanceClient) -> Dict[str, Any]:
    gt_path = os.path.join(task_dir, "ground_truth_labels.json")
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Missing ground truth file at {gt_path}")

    with open(gt_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    task_id = gt["task_id"]
    domain = gt.get("domain", "engineering")
    raw_prompt = gt["raw_prompt"]
    forbidden = gt.get("forbidden_hallucinations", [])

    user_prompt = (
        f"Synthesize formal software engineering requirements for the following prompt in the domain of '{domain}':\n"
        f"Prompt: \"{raw_prompt}\"\n\n"
        f"Domain Guidance:\n"
        f"- Enforce core invariants and essential derived domain rules.\n"
        f"- Do not generate unrequested UI pages or hallucinate arbitrary features (specifically avoid: {', '.join(forbidden)}).\n"
        f"- If key operational choices, providers, or format standards are unstated, mark them explicitly as UNKNOWN.\n\n"
        f"Return strictly valid JSON as specified in the system instructions."
    )

    print(f"[{task_id}] Running Experiment C via {client.provider} ({client.model_name})...")

    provenance_record = client.call_model(
        system_prompt=SYSTEM_PROMPT_STAGE_2,
        user_prompt=user_prompt,
        task_id=task_id,
        experiment_id="EXPERIMENT_C_GROUNDED_INFERENCE",
        input_context={
            "raw_prompt": raw_prompt,
            "domain": domain,
            "forbidden_hallucinations": forbidden
        }
    )

    parsed = provenance_record["parsed_output"]
    # Embed top-level provenance in output file for immediate inspection
    parsed["provenance_metadata"] = provenance_record["provenance"]

    out_path = os.path.join(task_dir, "experiment_c_grounded_inference.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2)

    prov = provenance_record["provenance"]
    print(f"[{task_id}] Successfully wrote {len(parsed.get('inferred_requirements', []))} inferred requirements to {out_path}")
    print(f"[{task_id}] Provenance: latency={prov['latency_ms']}ms, tokens={prov['token_usage']['total_tokens']}, commit={prov['git_commit'][:7]}")

    return parsed

def main():
    parser = argparse.ArgumentParser(description="Run S-Class Experiment C (Grounded Inference) with provenance.")
    parser.add_argument("--task", type=str, default="all", help="Task ID or folder name (e.g. task_01, task_04, or all)")
    parser.add_argument("--provider", type=str, default=None, help="LLM provider (gemini, openai, anthropic, ollama)")
    parser.add_argument("--model", type=str, default=None, help="Model name (e.g. gemini-2.0-flash, gpt-4o-mini)")
    parser.add_argument("--api-key", type=str, default=None, help="API key for the selected provider")
    args = parser.parse_args()

    client = LLMProvenanceClient(
        provider=args.provider,
        model_name=args.model,
        api_key=args.api_key,
        temperature=0.0
    )

    exp_base = os.path.abspath(os.path.join(os.path.dirname(__file__)))
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
            run_task_experiment_c(td, client)

if __name__ == "__main__":
    main()
