class SPIFFEMutualTLSRouterV2:
    def __init__(self, domain='spiffe://prod.net'): self.domain = domain
    def validate_spiffe_id(self, s: str) -> bool:
        if not s or not s.startswith(self.domain):
            return False
        rest = s[len(self.domain):]
        return rest == '' or rest.startswith('/')
