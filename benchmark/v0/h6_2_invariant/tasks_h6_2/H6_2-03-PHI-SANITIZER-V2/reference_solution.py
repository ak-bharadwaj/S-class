import re
class PHISanitizerV2:
    def sanitize(self, text: str) -> str:
        t1 = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED]', text)
        return re.sub(r'\b\d{3}\s*\.\s*\d{2}\s*\.\s*\d{4}\b', '[REDACTED]', t1)
