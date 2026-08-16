import pytest
import target_module

def test_negative_amount_rejected():
    with pytest.raises(ValueError):
        target_module.execute_transaction('A', 'B', -100, 'k_neg')

def test_idempotency_replay():
    target_module.balances = {'A': 1000, 'B': 500}
    target_module.seen_keys.clear()
    r1 = target_module.execute_transaction('A', 'B', 100, 'k_idem')
    r2 = target_module.execute_transaction('A', 'B', 100, 'k_idem')
    assert r1 == r2
    assert target_module.get_balance('A') == 900
    assert target_module.get_balance('B') == 600

def test_overdraft_prevention():
    target_module.balances = {'A': 100, 'B': 500}
    with pytest.raises(ValueError):
        target_module.execute_transaction('A', 'B', 200, 'k_over')

def test_zero_sum_invariance():
    target_module.balances = {'A': 1000, 'B': 500}
    init_total = sum(target_module.balances.values())
    target_module.execute_transaction('A', 'B', 300, 'k_sum')
    end_total = sum(target_module.balances.values())
    assert init_total == end_total
