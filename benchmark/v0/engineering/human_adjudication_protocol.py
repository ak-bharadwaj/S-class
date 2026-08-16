#!/usr/bin/env python3
"""
Gate 1.6D — Independent Human Failure Adjudication Protocol
(benchmark/v0/engineering/human_adjudication_protocol.py)

1. Samples failing benchmark runs for human review.
2. Provides structured human adjudication schema.
3. Computes Cohen's Kappa (kappa) inter-annotator agreement score between
   automated taxonomy classifications and human expert audit annotations.
"""

import os
import json
from typing import Dict, List, Any, Optional

TAXONOMY_CATEGORIES = [
    "wrong_requirement",
    "missing_requirement",
    "implementation_bug",
    "test_api_mismatch",
    "environment_failure"
]

class HumanAdjudicationProtocol:
    @staticmethod
    def sample_failures_for_adjudication(runs: List[Dict[str, Any]], sample_size: int = 10) -> List[Dict[str, Any]]:
        """
        Samples up to sample_size failing runs across tasks for independent human audit.
        """
        failed_runs = [r for r in runs if not r["oracle_result"]["all_passed"]]
        sampled = failed_runs[:sample_size]

        adjudication_samples = []
        for r in sampled:
            tax = r.get("failure_taxonomy", {})
            adjudication_samples.append({
                "task_id": r["task_id"],
                "baseline": r["baseline"],
                "automated_category": tax.get("category", "wrong_requirement"),
                "automated_reason": tax.get("reason", ""),
                "human_adjudicated_category": None,  # Filled by human reviewer
                "human_adjudicator_notes": None,     # Filled by human reviewer
                "adjudicated": False
            })
        return adjudication_samples

    @staticmethod
    def compute_cohens_kappa(automated: List[str], human: List[str]) -> Dict[str, Any]:
        """
        Computes Cohen's Kappa (kappa) agreement metric between automated & human annotations.
        """
        if not automated or not human or len(automated) != len(human):
            return {"kappa": 0.0, "observed_agreement": 0.0, "expected_agreement": 0.0, "total_samples": 0}

        n = len(automated)
        agree_count = sum(1 for a, h in zip(automated, human) if a == h)
        po = agree_count / float(n)

        # Calculate category probabilities for expected agreement
        cat_auto_counts = {c: automated.count(c) for c in TAXONOMY_CATEGORIES}
        cat_human_counts = {c: human.count(c) for c in TAXONOMY_CATEGORIES}

        pe = sum((cat_auto_counts[c] / float(n)) * (cat_human_counts[c] / float(n)) for c in TAXONOMY_CATEGORIES)

        kappa = (po - pe) / (1.0 - pe) if (1.0 - pe) != 0 else 1.0

        return {
            "total_samples": n,
            "agreed_samples": agree_count,
            "observed_agreement": round(po, 4),
            "expected_agreement": round(pe, 4),
            "cohens_kappa": round(kappa, 4),
            "reliability_assessment": "EXCELLENT" if kappa >= 0.8 else ("SUBSTANTIAL" if kappa >= 0.6 else "MODERATE")
        }
