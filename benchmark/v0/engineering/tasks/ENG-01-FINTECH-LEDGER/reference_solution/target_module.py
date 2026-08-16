# target_module.py
balances = {'A': 1000, 'B': 500}
journal = []
seen_keys = {}

def execute_transaction(from_acc: str, to_acc: str, amount: float, idem_key: str) -> dict:
    if amount <= 0:
        raise ValueError("Amount must be positive non-zero")
    if idem_key in seen_keys:
        return seen_keys[idem_key]
    if balances.get(from_acc, 0) < amount:
        raise ValueError("Insufficient balance / Overdraft prevented")

    balances[from_acc] -= amount
    balances[to_acc] = balances.get(to_acc, 0) + amount
    journal.append({'from': from_acc, 'to': to_acc, 'amount': amount, 'key': idem_key})
    res = {'status': 'SUCCESS', 'id': idem_key, 'amount': amount}
    seen_keys[idem_key] = res
    return res

def get_balance(acc: str) -> float:
    return balances.get(acc, 0.0)
