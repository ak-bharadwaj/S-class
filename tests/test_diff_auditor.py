import pytest
from diff_auditor import DiffAuditor, ScopeCreep, WeakenedTests, ExposedSecrets, UnauthorizedDependency

def test_diff_auditor_clean():
    auditor = DiffAuditor()
    intent = {"files": ["src/calculator.py"]}
    diff = """--- a/src/calculator.py
+++ b/src/calculator.py
@@ -1,3 +1,3 @@
-def add(a, b): return 0
+def add(a, b): return a + b
"""
    result = auditor.audit(intent, diff)
    assert result.passed is True
    assert len(result.issues) == 0

def test_diff_auditor_catches_scope_creep():
    auditor = DiffAuditor()
    intent = {"files": ["src/calculator.py"]}
    diff = """--- a/src/unauthorized.py
+++ b/src/unauthorized.py
@@ -1,3 +1,3 @@
+def malicious(): pass
"""
    result = auditor.audit(intent, diff)
    assert result.passed is False
    assert any(isinstance(issue, ScopeCreep) for issue in result.issues)

def test_diff_auditor_catches_weakened_tests():
    auditor = DiffAuditor()
    intent = {"files": ["tests/test_calculator.py"]}
    diff = """--- a/tests/test_calculator.py
+++ b/tests/test_calculator.py
@@ -5,4 +5,3 @@
-    assert calc.add(2, 2) == 4
+    pass
"""
    result = auditor.audit(intent, diff)
    assert result.passed is False
    assert any(isinstance(issue, WeakenedTests) for issue in result.issues)

def test_diff_auditor_catches_exposed_secrets():
    auditor = DiffAuditor()
    intent = {"files": ["src/config.py"]}
    diff = """--- a/src/config.py
+++ b/src/config.py
@@ -1,2 +1,3 @@
+OPENAI_KEY = "sk-proj-1234567890abcdef1234567890abcdef1234"
"""
    result = auditor.audit(intent, diff)
    assert result.passed is False
    assert any(isinstance(issue, ExposedSecrets) for issue in result.issues)
