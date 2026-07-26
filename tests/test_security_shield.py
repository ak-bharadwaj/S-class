import pytest
import os
import tempfile
from security_shield import SecurityShield, SecurityFinding

@pytest.fixture
def test_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        # File with secrets
        secrets_file = os.path.join(tmpdir, "secrets.py")
        with open(secrets_file, "w") as f:
            f.write("api_key = 'abcdefghijklmnop'\n")
            f.write("normal_var = 'short'\n")
            f.write("password : \"1234567890\"\n")
            
        # File with dangerous patterns
        danger_file = os.path.join(tmpdir, "danger.py")
        with open(danger_file, "w") as f:
            f.write("user_input = 'code'\n")
            f.write("eval(user_input)\n")
            f.write("pickle.loads(data)\n")
            f.write("cursor.execute('SELECT * FROM users WHERE id = %s' % user_id)\n")
            f.write("yaml.load(stream)\n")
            
        yield {"secrets": secrets_file, "danger": danger_file}

def test_scan_secrets(test_files):
    shield = SecurityShield()
    findings = shield.scan_secrets(test_files["secrets"])
    
    assert len(findings) == 2
    assert findings[0].category == "hardcoded_secret"
    assert findings[0].line_number == 1
    assert "api_key" in findings[0].snippet
    
    assert findings[1].line_number == 3
    assert "password" in findings[1].snippet

def test_scan_dangerous_patterns(test_files):
    shield = SecurityShield()
    findings = shield.scan_dangerous_patterns(test_files["danger"])
    
    categories = [f.category for f in findings]
    assert "eval_usage" in categories
    assert "unsafe_deserialize" in categories
    assert "sql_injection" in categories
    
    assert len(findings) >= 4

def test_scan_file(test_files):
    shield = SecurityShield()
    findings = shield.scan_file(test_files["secrets"])
    assert len(findings) == 2

def test_generate_report():
    shield = SecurityShield()
    findings = [
        SecurityFinding("CRITICAL", "hardcoded_secret", "file1.py", 10, "test", "test"),
        SecurityFinding("HIGH", "sql_injection", "file2.py", 20, "test", "test"),
        SecurityFinding("CRITICAL", "eval_usage", "file3.py", 30, "test", "test"),
    ]
    
    report = shield.generate_report(findings)
    assert report["summary"]["CRITICAL"] == 2
    assert report["summary"]["HIGH"] == 1
    assert report["summary"]["MEDIUM"] == 0
    assert report["summary"]["LOW"] == 0
    
    assert len(report["findings"]) == 3
