# target_module.py
VALID_SUBJECT_TYPE = "urn:ietf:params:oauth:token-type:access_token"
ALLOWED_AUDIENCES = {"api.payment.service", "api.user.service"}

def exchange_token(subject_token: str, subject_token_type: str, requested_aud: str) -> dict:
    if subject_token_type != VALID_SUBJECT_TYPE:
        raise ValueError("Invalid subject token type")
    if not subject_token or not subject_token.startswith("valid_"):
        raise PermissionError("Invalid subject token")
    if requested_aud not in ALLOWED_AUDIENCES:
        raise PermissionError("Unauthorized audience requested")
        
    return {
        "access_token": f"exchanged_tok_{requested_aud}",
        "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "token_type": "Bearer",
        "expires_in": 3600
    }
