import sys, os
from diff_auditor import DiffAuditor

def test_diff_auditor_basic():
    auditor = DiffAuditor()
    intent = {'affected_files': ['package.json'], 'allow_new_dependencies': False}
    diff = '''diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -10,1 +10,2 @@
+    "build": "next build"
'''
    res = auditor.audit(intent, diff)
    assert res.passed is True

