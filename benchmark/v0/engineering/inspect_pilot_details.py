#!/usr/bin/env python3
import os
import sys
import json
import tempfile
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PILOT_TASK_DIR = os.path.join(CURRENT_DIR, "tasks_pilot", "INTERNAL_PILOT_CONFIG_GC")

sys.path.insert(0, os.path.dirname(os.path.dirname(CURRENT_DIR)))
sys.path.insert(0, CURRENT_DIR)

from run_genuine_benchmark import LLMProviderConfig, LLMProvider, run_baseline_b2, run_baseline_b4

with open(os.path.join(PILOT_TASK_DIR, "task_spec.json"), "r") as f:
    spec = json.load(f)

config = LLMProviderConfig(provider_type="auto", model_name="gemini-3.5-flash-lite")
provider = LLMProvider(config=config)

# Run B2 and inspect trace
b2_art = run_baseline_b2(PILOT_TASK_DIR, spec, provider)

# Run B4 and inspect trace
b4_art = run_baseline_b4(PILOT_TASK_DIR, spec, provider)

detail_report = {
    "b2_result": b2_art["oracle_result"],
    "b2_trace": b2_art["execution_trace"],
    "b2_final_code": b2_art.get("final_code", ""),
    "b4_result": b4_art["oracle_result"],
    "b4_trace": b4_art["execution_trace"],
    "b4_final_code": b4_art.get("final_code", "")
}

with open(os.path.join(CURRENT_DIR, "internal_pilot_details.json"), "w") as f:
    json.dump(detail_report, f, indent=2)

print("Saved internal_pilot_details.json")
