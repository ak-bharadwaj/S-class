import pytest
import target_module

def test_phi_anonymization():
    rec = {'name': 'John Doe', 'ssn': '000-12-3456', 'diag': 'ICD-10-J45'}
    res = target_module.anonymize_record(rec, salt='secret_salt')
    assert res['ssn'] == '[REDACTED_SSN]'
    assert res['name'].startswith('ANON_')
    assert res['diag'] == 'ICD-10-J45'
