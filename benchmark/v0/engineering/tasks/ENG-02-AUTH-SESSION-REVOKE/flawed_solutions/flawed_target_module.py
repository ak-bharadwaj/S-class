# target_module.py
active_tokens = {}
blacklist = set()

def issue_token(user_id: str) -> str:
    token = f"tok_{user_id}_{len(active_tokens)}"
    active_tokens[token] = user_id
    return token

def validate_token(token: str) -> bool:
    return token in active_tokens

def reset_password(user_id: str, new_pass: str) -> None:
    pass # Flawed: fails to revoke tokens
