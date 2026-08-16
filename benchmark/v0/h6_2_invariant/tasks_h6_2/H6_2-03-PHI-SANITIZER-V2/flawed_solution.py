class PHISanitizerV2:
    def sanitize(self, text: str) -> str:
        return text.replace('123-45-6789', '[REDACTED]') # Flawed naive replace
