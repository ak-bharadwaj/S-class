"""Test saga contracts."""
import pytest
from sclass.contracts.saga_contracts import CompensatingStep, SagaTransaction

def test_saga_transaction_structure():
    step = CompensatingStep(step_id="s1", target_resource="/tmp/file.txt", reversal_action="RESTORE", reversal_payload="prev-content")
    saga = SagaTransaction(transaction_id="tx-1", forward_action_id="act-write", compensating_steps=[step], status="PENDING")
    assert saga.transaction_id == "tx-1"
    assert len(saga.compensating_steps) == 1
