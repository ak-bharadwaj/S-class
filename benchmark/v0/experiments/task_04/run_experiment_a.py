#!/usr/bin/env python3
import os
import sys
import json
import tempfile
import shutil
from dataclasses import asdict

plugin_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if plugin_root not in sys.path:
    sys.path.insert(0, plugin_root)

from spec_synthesis import SpecSynthesisEngine

def run_experiment_a():
    raw_prompt = "Implement real-time flight data recorder buffer synchronization that flushes ARINC 429 bus frames to solid-state crash-survivable memory on power loss."
    tmp_dir = tempfile.mkdtemp(prefix="exp_a_task04_")
    try:
        engine = SpecSynthesisEngine()
        spec = engine.run_synthesis(raw_prompt, workspace_dir=tmp_dir)
        
        spec_dict = asdict(spec)
        
        req_flat = []
        for cat, r_list in spec.requirements.items():
            for r in r_list:
                req_flat.append({
                    "category": cat,
                    "title": r.get("title", r.get("name", "Unknown")),
                    "type": r.get("type", "UNKNOWN"),
                    "action": r.get("action", "UNKNOWN"),
                    "why_chain": r.get("why_chain", []),
                    "provenance": r.get("provenance", "UNKNOWN")
                })

        out = {
            "experiment": "EXPERIMENT A — Current Baseline (Task 04)",
            "raw_prompt": raw_prompt,
            "gate_result": spec.gate_result,
            "total_assumption_weight": spec.total_assumption_weight,
            "scope_tier": spec.scope_tier,
            "archetypes": spec.archetypes,
            "total_requirements_count": len(req_flat),
            "requirements_by_category": {cat: len(r_list) for cat, r_list in spec.requirements.items()},
            "flattened_requirements": req_flat,
            "page_spreads_count": sum(len(v) for v in spec.page_spreads.values()),
            "low_level_designs_count": len(spec.low_level_designs),
            "scope_boundaries": spec.scope_boundaries,
            "questions_for_human": spec.questions_for_human,
            "acceptance_criteria": spec.acceptance_criteria,
            "raw_synthesized_spec": spec_dict
        }
        
        out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)))
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "experiment_a_baseline.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
            
        print(f"[Experiment A Task 04] Generated {len(req_flat)} requirements. Output saved to {out_path}")
        print(f"[Experiment A Task 04] Gate Result: {spec.gate_result}, Weight: {spec.total_assumption_weight}")
        print(f"[Experiment A Task 04] Page Spreads: {sum(len(v) for v in spec.page_spreads.values())}")
        return out
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_experiment_a()
