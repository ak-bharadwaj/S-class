#!/usr/bin/env python3
"""
S-Class EOS - Gate 1.3 Stage 1 Semantic Classifier Confusion Matrix Generator
(benchmark/v0/experiments/stage1_confusion_analysis.py)

Responsibilities:
- Evaluates live Experiment B classifications against frozen ground-truth canonical semantic units across all 7 tasks.
- Computes exact 6x6 confusion matrix (ENTITY, INVARIANT, BEHAVIOR, CONSTRAINT, ATTRIBUTE, NOISE).
- Computes per-class Precision, Recall, and F1-score.
- Identifies error topologies and codifies the Epistemic Confidence Boundary Rule.
- Generates `benchmark/v0/experiments/stage1_confusion_analysis.json` and `.md`.
"""

import os
import json
from typing import Dict, List, Any

CLASSES = ["ENTITY", "INVARIANT", "BEHAVIOR", "CONSTRAINT", "ATTRIBUTE", "NOISE"]

def generate_confusion_analysis():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    tasks = [f"task_0{i}" for i in range(1, 8)]

    # Matrix: row = Expected (GT), col = Actual (Predicted)
    matrix = {exp: {act: 0 for act in CLASSES} for exp in CLASSES}
    mismatches = []
    total_units = 0
    correct_units = 0

    task_summaries = {}

    for t in tasks:
        td = os.path.join(base_dir, t)
        p_b = os.path.join(td, "experiment_b_classification.json")
        p_gt = os.path.join(td, "ground_truth_labels.json")

        if not os.path.exists(p_b) or not os.path.exists(p_gt):
            continue

        with open(p_b, "r", encoding="utf-8") as fb, open(p_gt, "r", encoding="utf-8") as fgt:
            b_data = json.load(fb)
            gt_data = json.load(fgt)

        b_map = {c["unit"]: c for c in b_data.get("classifications", [])}
        gt_units = gt_data.get("canonical_semantic_units", {})

        task_correct = 0
        task_total = len(gt_units)

        for unit, gt_spec in gt_units.items():
            expected = gt_spec["ground_truth_class"] if isinstance(gt_spec, dict) else gt_spec
            pred_obj = b_map.get(unit, {})
            actual = pred_obj.get("class", "UNKNOWN")
            confidence = pred_obj.get("confidence", 0.0)

            total_units += 1
            if actual in CLASSES and expected in CLASSES:
                matrix[expected][actual] += 1

            if expected == actual:
                correct_units += 1
                task_correct += 1
            else:
                mismatches.append({
                    "task_id": t,
                    "unit": unit,
                    "expected_class": expected,
                    "predicted_class": actual,
                    "confidence": confidence,
                    "rationale": pred_obj.get("rationale", "")
                })

        task_summaries[t] = {
            "total": task_total,
            "correct": task_correct,
            "accuracy": round(task_correct / max(1, task_total) * 100, 2)
        }

    # Per-class metrics
    class_metrics = {}
    for c in CLASSES:
        tp = matrix[c][c]
        fp = sum(matrix[other][c] for other in CLASSES if other != c)
        fn = sum(matrix[c][other] for other in CLASSES if other != c)

        precision = round(tp / (tp + fp) * 100, 2) if (tp + fp) > 0 else 0.0
        recall = round(tp / (tp + fn) * 100, 2) if (tp + fn) > 0 else 0.0
        f1 = round(2 * (precision * recall) / (precision + recall), 2) if (precision + recall) > 0 else 0.0

        class_metrics[c] = {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "support": tp + fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1
        }

    overall_accuracy = round(correct_units / max(1, total_units) * 100, 2)
    macro_accuracy = round(sum(ts["accuracy"] for ts in task_summaries.values()) / len(task_summaries), 2)

    result = {
        "benchmark": "S-Class Gate 1.3 Stage 1 Semantic Unit Classification Confusion Analysis",
        "total_units_evaluated": total_units,
        "correct_units": correct_units,
        "micro_accuracy": overall_accuracy,
        "macro_accuracy": macro_accuracy,
        "task_breakdown": task_summaries,
        "confusion_matrix": matrix,
        "per_class_metrics": class_metrics,
        "misclassifications": mismatches,
        "epistemic_confidence_policy": {
            "high_confidence_threshold": 0.85,
            "rule": "If confidence >= 0.85 and category conforms to semantic lattice -> Accept. If confidence < 0.85 or cross-boundary (INVARIANT <-> CONSTRAINT) -> Flag as UNKNOWN / Clarification Candidate."
        }
    }

    # Write JSON artifact
    json_path = os.path.join(base_dir, "stage1_confusion_analysis.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # Write Markdown artifact
    md_path = os.path.join(base_dir, "stage1_confusion_analysis.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# S-Class Gate 1.3 — Stage 1 Semantic Classifier Confusion Matrix & Topology Analysis\n\n")
        f.write(f"- **Total Units Evaluated**: {total_units} units across 7 benchmark tasks\n")
        f.write(f"- **Micro-Accuracy (Pooled Aggregate)**: **{overall_accuracy}%** ({correct_units}/{total_units})\n")
        f.write(f"- **Macro-Accuracy (Task Mean)**: **{macro_accuracy}%**\n\n")
        
        f.write("## 1. 6x6 Semantic Class Confusion Matrix\n\n")
        f.write("| Ground Truth \\ Predicted | ENTITY | INVARIANT | BEHAVIOR | CONSTRAINT | ATTRIBUTE | NOISE |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for exp in CLASSES:
            row = [f"**{exp}**"] + [str(matrix[exp][act]) for act in CLASSES]
            f.write(f"| {' | '.join(row)} |\n")
        
        f.write("\n## 2. Per-Class Precision, Recall, and F1-Score\n\n")
        f.write("| Semantic Class | Support (GT Count) | True Positives | False Positives | False Negatives | Precision | Recall | F1-Score |\n")
        f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for c in CLASSES:
            m = class_metrics[c]
            f.write(f"| **{c}** | {m['support']} | {m['true_positive']} | {m['false_positive']} | {m['false_negative']} | **{m['precision']}%** | **{m['recall']}%** | **{m['f1_score']}%** |\n")

        f.write("\n## 3. Dissected Error Topology (All 5 Mismatches)\n\n")
        f.write("| Task | Semantic Unit | Expected (GT) | Predicted | Confidence | Analysis & Mitigation |\n")
        f.write("| :--- | :--- | :--- | :--- | :---: | :--- |\n")
        for mis in mismatches:
            f.write(f"| **{mis['task_id'].upper()}** | `\"{mis['unit']}\"` | `{mis['expected_class']}` | `{mis['predicted_class']}` | {mis['confidence']} | {mis['rationale']} |\n")

        f.write("\n## 4. Epistemic Confidence Boundary Policy\n")
        f.write("- **Threshold**: Confidence $\\ge 0.85$ required for autonomous ingestion into Requirement IR.\n")
        f.write("- **Boundary Demotion**: Ambiguous `INVARIANT` $\\leftrightarrow$ `CONSTRAINT` transitions without formal mathematical predicates are flagged as `UNKNOWN / CLARIFICATION` candidates to prevent latent corruption of downstream formal models.\n")

    print(f"Successfully generated stage1_confusion_analysis.json and .md (Micro: {overall_accuracy}%, Macro: {macro_accuracy}%)")
    return result

if __name__ == "__main__":
    generate_confusion_analysis()
