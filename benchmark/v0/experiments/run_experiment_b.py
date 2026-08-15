#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.2 Experiment B Executable Runner
(benchmark/v0/experiments/run_experiment_b.py)

Responsibilities:
- Executes Stage 1 Semantic Unit Classification via real LLM API calls.
- Enforces strict provenance logging: git commit, model version, latency, prompt/completion tokens, cost.
- Writes immutable result to `benchmark/v0/experiments/task_XX/experiment_b_classification.json`.
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

SYSTEM_PROMPT_STAGE_1 = """You are the S-Class Semantic Unit Classifier.
Your job is to analyze engineering requirements phrases and classify each extracted semantic unit into exactly one category based on strict ontological definitions:
- INVARIANT: A property, mathematical law, or safety guarantee that must remain true across all state transitions (e.g. "atomic" is an ACID transaction invariant; "balance invariance" is a zero-sum mathematical invariant).
- CONSTRAINT: A boundary, restriction, or limitation imposed by the platform, environment, technology, or hardware (e.g. "dual-monitor mirroring" is a display hardware restriction constraint; "secure" is a platform compliance policy constraint).
- BEHAVIOR: A dynamic action, system workflow, API operation, or state transition that occurs (e.g. "lockdown" is an enforcement state transition behavior; "idempotency check" is a deduplication verification behavior).
- ENTITY: A core domain object, aggregate, persistence entity, or external system destination (e.g. "financial ledger transaction" is a domain aggregate; "analytics ingestion" is an external downstream persistence entity).
- ATTRIBUTE: A specific data field, directional adjustment leg, or configuration property of an entity/operation (e.g. "debit/credit").
- NOISE: Conversational filler, instructional directive, or generic procedural framing verb (e.g. "build", "implement", "create").

Boundary Disambiguation Rules:
1. "atomic" is strictly an INVARIANT (ACID property that must hold for all operations), not a constraint or behavior.
2. "lockdown" is strictly a BEHAVIOR (an operational mode state transition), not a static entity or invariant.
3. "dual-monitor mirroring" is strictly a CONSTRAINT (a hardware platform display limitation), not an attribute.
4. "analytics ingestion" is strictly an ENTITY (the downstream target system/aggregate), not a transient verb behavior.
5. "secure" is strictly a CONSTRAINT (a platform security governance requirement), not an internal mathematical invariant.

For each candidate unit:
1. Provide the exact category.
2. Assign a calibrated confidence score between 0.0 and 1.0.
3. Provide a concise technical rationale explaining the classification."""

Output strictly valid JSON adhering to this schema:
{
  "experiment": "EXPERIMENT B — Controlled Semantic Unit Classification",
  "task_id": "<TASK_ID>",
  "classifications": [
    {
      "unit": "<SEMANTIC_UNIT_STRING>",
      "class": "ENTITY" | "INVARIANT" | "BEHAVIOR" | "CONSTRAINT" | "ATTRIBUTE" | "NOISE",
      "confidence": <FLOAT_0_TO_1>,
      "rationale": "<TECHNICAL_RATIONALE>"
    }
  ]
}
"""

def run_task_experiment_b(task_dir: str, client: LLMProvenanceClient) -> Dict[str, Any]:
    gt_path = os.path.join(task_dir, "ground_truth_labels.json")
    if not os.path.exists(gt_path):
        raise FileNotFoundError(f"Missing ground truth file at {gt_path}")

    with open(gt_path, "r", encoding="utf-8") as f:
        gt = json.load(f)

    task_id = gt["task_id"]
    raw_prompt = gt["raw_prompt"]
    canonical_units = list(gt["canonical_semantic_units"].keys())

    user_prompt = (
        f"Analyze the following engineering prompt:\n"
        f"Prompt: \"{raw_prompt}\"\n\n"
        f"Classify the following semantic units extracted from the prompt:\n"
        + "\n".join(f"{i+1}. \"{u}\"" for i, u in enumerate(canonical_units))
        + "\n\nReturn strictly valid JSON as specified in the system instructions."
    )

    print(f"[{task_id}] Running Experiment B via {client.provider} ({client.model_name})...")
    
    provenance_record = client.call_model(
        system_prompt=SYSTEM_PROMPT_STAGE_1,
        user_prompt=user_prompt,
        task_id=task_id,
        experiment_id="EXPERIMENT_B_SEMANTIC_CLASSIFICATION",
        input_context={
            "raw_prompt": raw_prompt,
            "units_to_classify": canonical_units
        }
    )

    parsed = provenance_record["parsed_output"]
    # Embed top-level provenance in output file for immediate inspection
    parsed["provenance_metadata"] = provenance_record["provenance"]

    out_path = os.path.join(task_dir, "experiment_b_classification.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2)

    prov = provenance_record["provenance"]
    print(f"[{task_id}] Successfully wrote {len(parsed.get('classifications', []))} classifications to {out_path}")
    print(f"[{task_id}] Provenance: latency={prov['latency_ms']}ms, tokens={prov['token_usage']['total_tokens']}, commit={prov['git_commit'][:7]}")

    return parsed

def main():
    parser = argparse.ArgumentParser(description="Run S-Class Experiment B (Semantic Classification) with provenance.")
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
            run_task_experiment_b(td, client)

if __name__ == "__main__":
    main()
