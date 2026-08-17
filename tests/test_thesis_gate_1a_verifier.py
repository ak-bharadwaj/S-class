"""
Tests for THESIS-GATE-1A Certificate Fail-Closed Verifier.
"""

import os
import json
import pytest
from verify_thesis_gate_1a_certificate import verify_thesis_gate_1a_certificate


@pytest.fixture
def valid_gate_1a_cert(tmp_path):
    cert_path = str(tmp_path / "valid_cert.json")
    payload = {
        "receipt_id": "SYNTHETIC-EFFICACY-PILOT-053B97DAD998",
        "milestone": "THESIS-GATE-1A: Synthetic Efficacy Pilot (Controlled Failure Injection)",
        "provenance": {
            "tested_source_sha": "053b97dad998dc759da0b0e33bfd07f7262b41ec",
            "total_scenarios_evaluated": 5
        },
        "observable_comparative_metrics": {
            "baseline_defects_escaped": 2,
            "treatment_defects_escaped": 0,
            "pre_gen_defects_caught_by_grounding": 1,
            "post_gen_defects_caught_by_evidence": 1,
            "rework_cycles_avoided": 3,
            "false_positive_rate": 0.0,
            "false_positive_gate_passed": True
        },
        "pilot_verdict": "PASS"
    }
    with open(cert_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return cert_path


def test_gate_1a_verifier_passes_on_valid_certificate(valid_gate_1a_cert):
    assert verify_thesis_gate_1a_certificate(valid_gate_1a_cert, expected_sha="053b97dad998dc759da0b0e33bfd07f7262b41ec") is True


def test_gate_1a_verifier_fails_on_sha_mismatch(valid_gate_1a_cert):
    assert verify_thesis_gate_1a_certificate(valid_gate_1a_cert, expected_sha="mismatched_sha") is False


def test_gate_1a_verifier_fails_on_unknown_sha(tmp_path):
    cert_path = str(tmp_path / "unknown_sha.json")
    payload = {
        "milestone": "THESIS-GATE-1A: Synthetic Efficacy Pilot",
        "provenance": {"tested_source_sha": "UNKNOWN", "total_scenarios_evaluated": 5},
        "observable_comparative_metrics": {"treatment_defects_escaped": 0, "pre_gen_defects_caught_by_grounding": 1, "post_gen_defects_caught_by_evidence": 1},
        "pilot_verdict": "PASS"
    }
    with open(cert_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    assert verify_thesis_gate_1a_certificate(cert_path) is False


def test_gate_1a_verifier_fails_on_treatment_escaped_defects(tmp_path):
    cert_path = str(tmp_path / "escaped_defects.json")
    payload = {
        "milestone": "THESIS-GATE-1A: Synthetic Efficacy Pilot",
        "provenance": {"tested_source_sha": "053b97dad998dc759da0b0e33bfd07f7262b41ec", "total_scenarios_evaluated": 5},
        "observable_comparative_metrics": {"treatment_defects_escaped": 1, "pre_gen_defects_caught_by_grounding": 1, "post_gen_defects_caught_by_evidence": 1},
        "pilot_verdict": "PASS"
    }
    with open(cert_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    assert verify_thesis_gate_1a_certificate(cert_path) is False
