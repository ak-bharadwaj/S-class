from target_module import WorkspaceGarbageCollector, ArtifactTamperError
import pytest
import os
import tempfile

def test_pilot_gc_basic():
    with tempfile.TemporaryDirectory() as tmp:
        gc = WorkspaceGarbageCollector(tmp)
        # Create a report file and compute initial state
        report = os.path.join(tmp, 'master_ledger.md')
        with open(report, 'w', encoding='utf-8') as f:
            f.write('# Master Ledger')
        assert gc.verify_artifact_integrity() is True

def test_pilot_gc_tamper():
    with tempfile.TemporaryDirectory() as tmp:
        gc = WorkspaceGarbageCollector(tmp)
        report = os.path.join(tmp, 'master_ledger.md')
        with open(report, 'w', encoding='utf-8') as f:
            f.write('# Master Ledger')
        gc.verify_artifact_integrity() # Record baseline hash
        # Modify report
        with open(report, 'a', encoding='utf-8') as f:
            f.write('\nTampered!')
        with pytest.raises(ArtifactTamperError):
            gc.verify_artifact_integrity()
