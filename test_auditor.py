import sys, os
sys.path.insert(0, os.getcwd())
from diff_auditor import DiffAuditor
auditor = DiffAuditor()
intent = {'affected_files': ['package.json'], 'allow_new_dependencies': False}
diff = '''diff --git a/package.json b/package.json
--- a/package.json
+++ b/package.json
@@ -10,1 +10,2 @@
+    "build": "next build"
'''
res = auditor.audit(intent, diff)
print(res.passed, res.issues)
