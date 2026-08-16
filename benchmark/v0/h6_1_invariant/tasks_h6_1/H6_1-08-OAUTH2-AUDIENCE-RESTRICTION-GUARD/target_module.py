class InvalidAudienceError(Exception): pass

class OAuth2AudienceGuard:
    def __init__(self, expected_aud: str):
        self.expected_aud = expected_aud

    def validate_token_claims(self, claims: dict) -> bool:
        pass
