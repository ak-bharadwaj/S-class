# target_module.py
balances = {'A': 1000, 'B': 500}
journal = []
seen_keys = {}

def execute_transaction(from_acc: str, to_acc: str, amount: float, idem_key: str) -> dict:
    # Implement double-entry transaction
    pass

def get_balance(acc: str) -> float:
    return balances.get(acc, 0.0)
