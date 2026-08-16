class SPIFFEMutualTLSRouterV2:
    def __init__(self, domain='spiffe://prod.net'): self.domain = domain
    def validate_spiffe_id(self, s: str) -> bool:
        return self.domain in s # Flawed: suffix spoofing allowed
