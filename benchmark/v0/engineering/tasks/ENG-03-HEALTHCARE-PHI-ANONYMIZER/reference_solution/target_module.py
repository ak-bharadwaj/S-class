# target_module.py
import re, hmac, hashlib

def anonymize_record(record: dict, salt: str) -> dict:
    clean = record.copy()
    if 'ssn' in clean:
        clean['ssn'] = '[REDACTED_SSN]'
    if 'name' in clean:
        h = hmac.new(salt.encode(), clean['name'].encode(), hashlib.sha256).hexdigest()
        clean['name'] = f"ANON_{h[:16]}"
    return clean
