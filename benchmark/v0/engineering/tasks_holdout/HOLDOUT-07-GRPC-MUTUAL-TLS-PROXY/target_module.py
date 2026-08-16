class MutualTLSProxy:
    def __init__(self, trusted_ca_pem: str):
        pass

    def authenticate_peer(self, cert_pem: str) -> dict:
        pass

    def proxy_request(self, payload: dict, cert_pem: str) -> dict:
        pass
