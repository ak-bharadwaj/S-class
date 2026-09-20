"""Test consensus contracts."""
import pytest
from sclass.contracts.consensus_contracts import ConsensusRule, ConsensusEvaluation

def test_consensus_rule_definition():
    rule = ConsensusRule(rule_id="rule-critical", minimum_independent_signals=2, required_trust_tiers=["V3", "V5"])
    assert rule.minimum_independent_signals == 2

def test_consensus_evaluation_result():
    ev = ConsensusEvaluation(claim_id="cl-1", consensus_reached=True, corroborating_signals=3, durable_promotion_allowed=True)
    assert ev.consensus_reached is True
