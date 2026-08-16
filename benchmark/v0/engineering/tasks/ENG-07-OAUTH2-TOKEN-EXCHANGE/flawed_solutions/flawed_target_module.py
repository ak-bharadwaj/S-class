# target_module.py
def exchange_token(subject_token: str, subject_token_type: str, requested_aud: str) -> dict:
    # Flawed: returns token for any audience without subject token validation
    return {"access_token": "exchanged_tok"}
