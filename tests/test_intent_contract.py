import pytest
from intent_contract import IntentContract
from error_recovery import ErrorPath

def test_intent_contract_validation():
    ep = ErrorPath("err", "hint", "retry")
    
    # Valid
    ic = IntentContract(
        goal="Do thing",
        scope_boundaries=[],
        acceptance_criteria=["Done"],
        error_paths=[ep]
    )
    ic.validate()
    
    # Missing goal
    with pytest.raises(ValueError, match="goal cannot be empty"):
        IntentContract("", [], ["Done"], [ep]).validate()
        
    # Missing criteria
    with pytest.raises(ValueError, match="acceptance_criteria cannot be empty"):
        IntentContract("Goal", [], [], [ep]).validate()
        
    # Missing error paths
    with pytest.raises(ValueError, match="error_paths cannot be empty"):
        IntentContract("Goal", [], ["Done"], []).validate()

def test_intent_contract_serialization():
    ep = ErrorPath("err", "hint", "retry", 5, 2.0, 1.5, "stop")
    ic = IntentContract(
        goal="Goal",
        scope_boundaries=["boundary"],
        acceptance_criteria=["Done"],
        error_paths=[ep],
        max_retries=5,
        backoff_strategy="linear",
        stop_conditions=["stop_cond"]
    )
    
    data = ic.to_dict()
    ic_new = IntentContract.from_dict(data)
    
    assert ic_new.goal == ic.goal
    assert ic_new.scope_boundaries == ic.scope_boundaries
    assert ic_new.acceptance_criteria == ic.acceptance_criteria
    assert len(ic_new.error_paths) == 1
    assert ic_new.error_paths[0].trigger_pattern == ep.trigger_pattern
    assert ic_new.max_retries == ic.max_retries
    assert ic_new.backoff_strategy == ic.backoff_strategy
    assert ic_new.stop_conditions == ic.stop_conditions
