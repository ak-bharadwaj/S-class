# target_module.py
def anonymize_record(record: dict, salt: str) -> dict:
    clean = record.copy()
    if 'name' in clean:
        clean['name'] = 'ANON_USER' # Flawed: unsalted static string, leaks equality, misses SSN redaction
    return clean
