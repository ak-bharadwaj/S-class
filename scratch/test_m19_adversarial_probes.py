"""
Adversarial Probe & Stress Harness for Milestone 19 (RC.3 Independent Observation Plane).
Empirical challenger suite executing hostile attacks against:
1. Tampered observation records & receipt hash verification
2. Forged receipts & ledger provenance boundaries
3. Failing process claims (exit code 1, segfault, deceptive stdout)
4. Non-git, empty, and corrupted git repositories
5. Deep secret and credential redaction
"""

import os
import sys
import json
import shutil
import tempfile
import hashlib
import subprocess
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath('src'))

from sclass.observation.record import (
    ObservationRecord,
    ProcessTelemetry,
    GitRevisionState,
    WorkspaceDelta,
    FileMutation,
    redact_observation_secrets,
)
from sclass.observation.git_observer import GitObserver
from sclass.observation.delta import DeltaCalculator
from sclass.observation.factory import ObservationFactory
from sclass.observation.convergence import ObservationConvergence
from sclass.domain.action import ActionRequest
from sclass.domain.capability import CAP_TERMINAL_EXECUTE
from sclass.trust.ledger import LocalLedger
from sclass.domain.claim import Claim, ClaimType
from sclass.domain.evidence import ObservedReceipt, EvidenceReceipt, ProposedEvidence
from sclass.verification.engine import verify_claim


def test_suite_1_tampered_observation_records():
    print("\n--- Running Suite 1: Tampered Observation Records ---")
    proc = ProcessTelemetry(
        pid=4242,
        executable_path="/usr/bin/python3",
        executable_hash="a" * 64,
        requested_argv=("python", "test.py"),
        actual_argv=("/usr/bin/python3", "test.py"),
        process_start_time="2026-09-14T10:00:00Z",
        process_end_time="2026-09-14T10:00:02Z",
        duration_ms=2000.0,
    )
    ws = WorkspaceDelta(
        tree_fingerprint_before="b" * 64,
        tree_fingerprint_after="c" * 64,
        files_added=("src/new.py",),
        files_modified=("src/old.py",),
        files_deleted=("src/del.py",),
        mutations=(),
        total_bytes_changed=150,
    )
    git = GitRevisionState(
        is_git_repository=True,
        revision_before="d" * 40,
        revision_after="e" * 40,
        branch="main",
    )
    rec = ObservationRecord(
        record_id="rec_baseline",
        task_id="task_001",
        claim_id="claim_001",
        command="python test.py",
        exit_code=0,
        stdout_hash="1" * 64,
        stderr_hash="2" * 64,
        stdout_bytes=100,
        stderr_bytes=0,
        process=proc,
        workspace=ws,
        git=git,
        created_at="2026-09-14T10:00:02Z",
    )
    base_hash = rec.compute_hash()
    assert len(base_hash) == 64

    # 1.1 Exit code modification
    for bad_exit in (1, 255, -1, 139):
        rec_tampered = ObservationRecord(
            record_id=rec.record_id, task_id=rec.task_id, claim_id=rec.claim_id,
            command=rec.command, exit_code=bad_exit,
            stdout_hash=rec.stdout_hash, stderr_hash=rec.stderr_hash,
            stdout_bytes=rec.stdout_bytes, stderr_bytes=rec.stderr_bytes,
            process=rec.process, workspace=rec.workspace, git=rec.git,
            created_at=rec.created_at,
        )
        assert rec_tampered.compute_hash() != base_hash, f"Exit code {bad_exit} failed to alter compute_hash"
    print("  [PASS] 1.1: Exit code tamper alters ObservationRecord.compute_hash()")

    # 1.2 Stdout/Stderr hash modification
    rec_tampered_stdout = ObservationRecord(
        record_id=rec.record_id, task_id=rec.task_id, claim_id=rec.claim_id,
        command=rec.command, exit_code=rec.exit_code,
        stdout_hash="1" * 63 + "2", stderr_hash=rec.stderr_hash,
        stdout_bytes=rec.stdout_bytes, stderr_bytes=rec.stderr_bytes,
        process=rec.process, workspace=rec.workspace, git=rec.git,
        created_at=rec.created_at,
    )
    assert rec_tampered_stdout.compute_hash() != base_hash
    print("  [PASS] 1.2: Stdout hash tamper alters ObservationRecord.compute_hash()")

    # 1.3 Executable hash / actual_argv modification
    proc_tampered = ProcessTelemetry(
        pid=proc.pid,
        executable_path=proc.executable_path,
        executable_hash="f" * 64,
        requested_argv=proc.requested_argv,
        actual_argv=("/usr/bin/python3", "injected.py"),
    )
    rec_tampered_proc = ObservationRecord(
        record_id=rec.record_id, task_id=rec.task_id, claim_id=rec.claim_id,
        command=rec.command, exit_code=rec.exit_code,
        stdout_hash=rec.stdout_hash, stderr_hash=rec.stderr_hash,
        stdout_bytes=rec.stdout_bytes, stderr_bytes=rec.stderr_bytes,
        process=proc_tampered, workspace=rec.workspace, git=rec.git,
        created_at=rec.created_at,
    )
    assert rec_tampered_proc.compute_hash() != base_hash
    print("  [PASS] 1.3: Executable hash / actual_argv tamper alters compute_hash()")

    # 1.4 Tree fingerprint & files modification
    ws_tampered = WorkspaceDelta(
        tree_fingerprint_before="b" * 64,
        tree_fingerprint_after="9" * 64,
        files_added=("src/hacked.py",),
        files_modified=(),
        files_deleted=(),
    )
    rec_tampered_ws = ObservationRecord(
        record_id=rec.record_id, task_id=rec.task_id, claim_id=rec.claim_id,
        command=rec.command, exit_code=rec.exit_code,
        stdout_hash=rec.stdout_hash, stderr_hash=rec.stderr_hash,
        stdout_bytes=rec.stdout_bytes, stderr_bytes=rec.stderr_bytes,
        process=rec.process, workspace=ws_tampered, git=rec.git,
        created_at=rec.created_at,
    )
    assert rec_tampered_ws.compute_hash() != base_hash
    print("  [PASS] 1.4: Workspace delta tamper alters compute_hash()")

    # 1.5 Git revision modification
    git_tampered = GitRevisionState(
        is_git_repository=True,
        revision_before=rec.git.revision_before,
        revision_after="0" * 40,
        branch="main",
    )
    rec_tampered_git = ObservationRecord(
        record_id=rec.record_id, task_id=rec.task_id, claim_id=rec.claim_id,
        command=rec.command, exit_code=rec.exit_code,
        stdout_hash=rec.stdout_hash, stderr_hash=rec.stderr_hash,
        stdout_bytes=rec.stdout_bytes, stderr_bytes=rec.stderr_bytes,
        process=rec.process, workspace=rec.workspace, git=git_tampered,
        created_at=rec.created_at,
    )
    assert rec_tampered_git.compute_hash() != base_hash
    print("  [PASS] 1.5: Git revision tamper alters compute_hash()")

    # 1.6 ObservationRecord.created_at observation
    rec_time_mod = ObservationRecord(
        record_id=rec.record_id, task_id=rec.task_id, claim_id=rec.claim_id,
        command=rec.command, exit_code=rec.exit_code,
        stdout_hash=rec.stdout_hash, stderr_hash=rec.stderr_hash,
        stdout_bytes=rec.stdout_bytes, stderr_bytes=rec.stderr_bytes,
        process=rec.process, workspace=rec.workspace, git=rec.git,
        created_at="2026-09-14T12:34:56Z",
    )
    obs_rec_time_invariant = (rec_time_mod.compute_hash() == base_hash)
    print(f"  [OBSERVATION] 1.6: ObservationRecord.created_at outside compute_hash() payload: {obs_rec_time_invariant}")

    # 1.7 End-to-end receipt verification with tampered exit_code, stdout_hash, and timestamps
    ws_temp = tempfile.mkdtemp(prefix="sclass_adv_s1_")
    try:
        ledger = LocalLedger(ws_temp)
        req = ActionRequest(
            actor="agent:tester",
            session="sess_s1",
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target="echo test",
            parameters={"command": "python -c \"print('suite1_payload')\""},
            workspace=ws_temp,
        )
        cmd = [sys.executable, "-c", "print('suite1_payload')"]
        exec_res, receipt = ObservationConvergence.execute_and_observe(
            request=req,
            command=cmd,
            timeout=10.0,
            ledger=ledger,
        )
        assert receipt is not None
        claim = Claim(
            claim_id=receipt.claim_id,
            task_id=receipt.task_id,
            statement="Suite 1 legitimate execution",
            claim_type=ClaimType.EXECUTION.value,
        )
        v_legit = verify_claim(claim, receipt, workspace_dir=ws_temp, ledger=ledger)
        assert v_legit.is_accepted, f"Legitimate receipt failed verification: {v_legit.reason}"

        # Tamper exit_code on receipt
        tampered_exit = ObservedReceipt.from_dict(receipt.to_dict())
        object.__setattr__(tampered_exit, "exit_code", 42)
        v_tampered_exit = verify_claim(claim, tampered_exit, workspace_dir=ws_temp, ledger=ledger)
        assert v_tampered_exit.is_rejected, "Tampered exit code was not rejected!"

        # Tamper stdout_hash on receipt
        tampered_stdout = ObservedReceipt.from_dict(receipt.to_dict())
        object.__setattr__(tampered_stdout, "stdout_hash", "0" * 64)
        v_tampered_stdout = verify_claim(claim, tampered_stdout, workspace_dir=ws_temp, ledger=ledger)
        assert v_tampered_stdout.is_rejected, "Tampered stdout_hash was not rejected!"

        # Tamper started_at timestamp on receipt
        tampered_time = ObservedReceipt.from_dict(receipt.to_dict())
        object.__setattr__(tampered_time, "started_at", "2020-01-01T00:00:00Z")
        v_tampered_time = verify_claim(claim, tampered_time, workspace_dir=ws_temp, ledger=ledger)
        assert v_tampered_time.is_rejected, "Tampered timestamp was not rejected!"

        # Tamper finished_at timestamp on receipt
        tampered_time2 = ObservedReceipt.from_dict(receipt.to_dict())
        object.__setattr__(tampered_time2, "finished_at", "2020-01-01T00:00:05Z")
        v_tampered_time2 = verify_claim(claim, tampered_time2, workspace_dir=ws_temp, ledger=ledger)
        assert v_tampered_time2.is_rejected, "Tampered finished_at timestamp was not rejected!"

        # Tamper process_start_time inside execution_identity metadata
        tampered_proc_time = ObservedReceipt.from_dict(receipt.to_dict())
        tampered_proc_time.metadata["execution_identity"]["process_start_time"] = "1999-12-31T23:59:59Z"
        v_tampered_proc_time = verify_claim(claim, tampered_proc_time, workspace_dir=ws_temp, ledger=ledger)
        assert v_tampered_proc_time.is_rejected, "Tampered process_start_time metadata was not rejected!"

        print("  [PASS] 1.7: All receipt tampers (exit_code, stdout_hash, timestamps) strictly rejected by verification engine")
    finally:
        shutil.rmtree(ws_temp, ignore_errors=True)


def test_suite_2_forged_receipts():
    print("\n--- Running Suite 2: Forged Receipts & Ledger Checks ---")
    ws_temp = tempfile.mkdtemp(prefix="sclass_adv_s2_")
    try:
        ledger = LocalLedger(ws_temp)

        # 2.1 Pure unanchored fabricated receipt
        fake_receipt = ObservedReceipt(
            receipt_id="rcpt_fake_001",
            task_id="task_fake",
            claim_id="claim_fake",
            agent="agent:malicious",
            action="run_command",
            workspace=ws_temp,
            command="pytest",
            exit_code=0,
            stdout_hash=hashlib.sha256(b"10 passed").hexdigest(),
            stderr_hash=hashlib.sha256(b"").hexdigest(),
            workspace_fingerprint="0" * 64,
            verifier="pytest_runner",
            execution_kind="test_runner",
            evidence=[{"passed_tests": 10, "failed_tests": 0}],
            metadata={"execution_identity": {"actual_argv": ["pytest"], "requested_argv": ["pytest"]}},
        )
        fake_receipt.receipt_hash = fake_receipt.compute_hash()

        claim = Claim(
            claim_id="claim_fake",
            task_id="task_fake",
            statement="All 10 tests passed",
            claim_type=ClaimType.TEST_PASS.value,
        )

        v_fake = verify_claim(claim, fake_receipt, workspace_dir=ws_temp, ledger=ledger)
        assert v_fake.is_rejected, "Unanchored fabricated receipt was NOT rejected!"
        print("  [PASS] 2.1: Unanchored fabricated receipt caught and rejected by ledger provenance check")

        # 2.2 Forged receipt with injected non-canonical ledger entry (corrupted hash chain)
        with open(ledger.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"event": "OBSERVATION", "payload": {"receipt_id": "rcpt_fake_001"}, "hash": "badhash"}) + "\n")

        v_corrupted_ledger = verify_claim(claim, fake_receipt, workspace_dir=ws_temp, ledger=ledger)
        assert v_corrupted_ledger.is_rejected, "Corrupted ledger hash chain was NOT rejected!"
        print(f"  [PASS] 2.2: Tampered ledger hash chain caught and rejected ({v_corrupted_ledger.reason})")

        # 2.3 ProposedEvidence disguised as ObservedReceipt
        prop = ProposedEvidence(
            task_id="task_fake",
            action="run_command",
            agent="agent:malicious",
            proposed_command="pytest",
        )
        v_prop = verify_claim(claim, prop, workspace_dir=ws_temp, ledger=ledger)
        assert v_prop.is_rejected
        print(f"  [PASS] 2.3: ProposedEvidence strictly rejected as non-authoritative ({v_prop.reason})")
    finally:
        shutil.rmtree(ws_temp, ignore_errors=True)


def test_suite_3_failing_process_claims():
    print("\n--- Running Suite 3: Failing Process Claims (Exit Code 1, Segfault) ---")
    ws_temp = tempfile.mkdtemp(prefix="sclass_adv_s3_")
    try:
        ledger = LocalLedger(ws_temp)

        # 3.1 Exit code 1 on test runner
        req_fail = ActionRequest(
            actor="agent:tester",
            session="sess_s3",
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target="exit 1",
            parameters={"command": "python -c \"raise SystemExit(1)\""},
            workspace=ws_temp,
        )
        cmd_fail = [sys.executable, "-c", "raise SystemExit(1)"]
        exec_fail, receipt_fail = ObservationConvergence.execute_and_observe(
            request=req_fail,
            command=cmd_fail,
            timeout=10.0,
            ledger=ledger,
        )
        assert receipt_fail.exit_code == 1

        claim_test = Claim(
            claim_id=receipt_fail.claim_id,
            task_id=receipt_fail.task_id,
            statement="Tests succeeded",
            claim_type=ClaimType.TEST_PASS.value,
        )
        v_test = verify_claim(claim_test, receipt_fail, workspace_dir=ws_temp, ledger=ledger)
        assert v_test.is_rejected, "Failing exit code 1 on test claim was NOT rejected!"
        print(f"  [PASS] 3.1: Exit code 1 test claim rejected ({v_test.reason})")

        # 3.2 Exit code 1 on execution claim
        claim_exec = Claim(
            claim_id=receipt_fail.claim_id,
            task_id=receipt_fail.task_id,
            statement="Execution completed successfully",
            claim_type=ClaimType.EXECUTION.value,
        )
        v_exec = verify_claim(claim_exec, receipt_fail, workspace_dir=ws_temp, ledger=ledger)
        assert v_exec.is_rejected, "Failing exit code 1 on execution claim was NOT rejected!"
        print(f"  [PASS] 3.2: Exit code 1 execution claim rejected ({v_exec.reason})")

        # 3.3 Segfault / Crash exit code (e.g. 139 / 255)
        req_crash = ActionRequest(
            actor="agent:tester",
            session="sess_crash",
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target="exit 139",
            parameters={"command": "python -c \"raise SystemExit(139)\""},
            workspace=ws_temp,
        )
        cmd_crash = [sys.executable, "-c", "raise SystemExit(139)"]
        _, receipt_crash = ObservationConvergence.execute_and_observe(
            request=req_crash,
            command=cmd_crash,
            timeout=10.0,
            ledger=ledger,
        )
        assert receipt_crash.exit_code == 139
        v_crash = verify_claim(
            Claim(claim_id=receipt_crash.claim_id, task_id="t_crash", statement="Crash claim", claim_type=ClaimType.EXECUTION.value),
            receipt_crash,
            workspace_dir=ws_temp,
            ledger=ledger,
        )
        assert v_crash.is_rejected, "Segfault exit code 139 was NOT rejected!"
        print(f"  [PASS] 3.3: Crash exit code 139 strictly rejected ({v_crash.reason})")

        # 3.4 Deceptive stdout: prints 'SUCCESS' but exits with 1
        script_file = os.path.join(ws_temp, "deceptive.py")
        with open(script_file, "w", encoding="utf-8") as f:
            f.write("print('SUCCESS: 100% tests passed')\nraise SystemExit(1)\n")

        req_dec = ActionRequest(
            actor="agent:tester",
            session="sess_dec",
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target="deceptive",
            parameters={"command": f"python \"{script_file}\""},
            workspace=ws_temp,
        )
        cmd_dec = [sys.executable, script_file]
        _, receipt_dec = ObservationConvergence.execute_and_observe(
            request=req_dec,
            command=cmd_dec,
            timeout=10.0,
            ledger=ledger,
        )
        assert receipt_dec.exit_code == 1
        assert "SUCCESS" in receipt_dec.metadata.get("stdout", "")
        v_deceptive = verify_claim(
            Claim(claim_id=receipt_dec.claim_id, task_id="t_dec", statement="Deceptive claim", claim_type=ClaimType.EXECUTION.value),
            receipt_dec,
            workspace_dir=ws_temp,
            ledger=ledger,
        )
        assert v_deceptive.is_rejected
        print(f"  [PASS] 3.4: Deceptive stdout with exit code 1 strictly rejected ({v_deceptive.reason})")
    finally:
        shutil.rmtree(ws_temp, ignore_errors=True)


def test_suite_4_non_git_and_corrupted_git_directories():
    print("\n--- Running Suite 4: Non-Git & Corrupted Git Directories ---")
    
    # 4.1 Completely non-git directory
    ws_empty = tempfile.mkdtemp(prefix="sclass_nongit_")
    try:
        assert not GitObserver.is_git_repository(ws_empty)
        state_empty = GitObserver.capture_state(ws_empty)
        assert state_empty.is_git_repository is False
        assert state_empty.revision_before is None
        assert state_empty.revision_after is None
        assert state_empty.dirty_files == ()
        assert state_empty.untracked_files == ()
        print("  [PASS] 4.1: Plain non-git directory safely returns is_git_repository=False")
    finally:
        shutil.rmtree(ws_empty, ignore_errors=True)

    # 4.2 Non-existent directory
    state_nonexist = GitObserver.capture_state(os.path.join(tempfile.gettempdir(), "non_existent_folder_xyz123"))
    assert state_nonexist.is_git_repository is False
    print("  [PASS] 4.2: Non-existent directory safely returns is_git_repository=False")

    # 4.3 Corrupted .git file (e.g. submodule pointer or corrupted file instead of directory)
    ws_corrupt_file = tempfile.mkdtemp(prefix="sclass_corrupt_gitfile_")
    try:
        git_file = os.path.join(ws_corrupt_file, ".git")
        with open(git_file, "w", encoding="utf-8") as f:
            f.write("gitdir: /invalid/path/that/does/not/exist/at/all")
        state_corrupt = GitObserver.capture_state(ws_corrupt_file)
        assert state_corrupt.is_git_repository is False
        print("  [PASS] 4.3: Corrupted .git file reference safely returns is_git_repository=False")
    finally:
        shutil.rmtree(ws_corrupt_file, ignore_errors=True)

    # 4.4 Corrupted .git directory with missing or corrupted HEAD
    ws_corrupt_dir = tempfile.mkdtemp(prefix="sclass_corrupt_gitdir_")
    try:
        git_dir = os.path.join(ws_corrupt_dir, ".git")
        os.makedirs(git_dir, exist_ok=True)
        with open(os.path.join(git_dir, "HEAD"), "wb") as f:
            f.write(b"\x00\xff\xfe\x01\x02CORRUPTED_HEAD_DATA")
        with open(os.path.join(git_dir, "config"), "w", encoding="utf-8") as f:
            f.write("[core]\nrepositoryformatversion = 9999\n")
        state_corrupt_head = GitObserver.capture_state(ws_corrupt_dir)
        assert isinstance(state_corrupt_head, GitRevisionState)
        print(f"  [PASS] 4.4: Corrupted .git/HEAD and config safely handled (is_repo={state_corrupt_head.is_git_repository})")
    finally:
        shutil.rmtree(ws_corrupt_dir, ignore_errors=True)

    # 4.5 Empty git repository with 0 commits (git init without commits)
    ws_init_only = tempfile.mkdtemp(prefix="sclass_init_only_")
    try:
        subprocess.run(["git", "init"], cwd=ws_init_only, capture_output=True, check=True)
        state_init = GitObserver.capture_state(ws_init_only)
        assert state_init.is_git_repository is True
        assert state_init.revision_after is None
        assert isinstance(state_init.dirty_files, tuple)
        print("  [PASS] 4.5: Zero-commit git init safely handled (revision_after=None, no crash)")
    finally:
        shutil.rmtree(ws_init_only, ignore_errors=True)


def test_suite_5_secret_redaction():
    print("\n--- Running Suite 5: Secret Redaction Probes ---")
    
    # 5.1 GitHub personal access token (classic)
    token_ghp = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    redacted_ghp = redact_observation_secrets(token_ghp)
    assert redacted_ghp == "[REDACTED_SECRET]", f"ghp token failed to redact: {redacted_ghp}"
    print("  [PASS] 5.1: ghp_... classic token cleanly masked to [REDACTED_SECRET]")

    # 5.2 GitHub fine-grained PAT
    token_pat = "github_pat_11ABCDEFG0123456789_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    redacted_pat = redact_observation_secrets(token_pat)
    assert redacted_pat == "[REDACTED_SECRET]", f"github_pat failed to redact: {redacted_pat}"
    print("  [PASS] 5.2: github_pat_... fine-grained token cleanly masked")

    # 5.3 OpenAI API key
    token_sk = "sk-1234567890abcdefghijklmnopqrstuvwxyz123456"
    redacted_sk = redact_observation_secrets(token_sk)
    assert redacted_sk == "[REDACTED_SECRET]", f"sk- key failed to redact: {redacted_sk}"
    print("  [PASS] 5.3: sk-... API key cleanly masked")

    # 5.4 Key-value pair patterns (api_key, bearer, password)
    kv_examples = [
        ("api_key: 'supersecrettoken123'", "[REDACTED_SECRET]"),
        ("bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "[REDACTED_SECRET]"),
        ("token=secretvalue1234", "[REDACTED_SECRET]"),
        ("password : \"admin_pass_999\"", "[REDACTED_SECRET]"),
    ]
    for inp, expected in kv_examples:
        res = redact_observation_secrets(inp)
        assert "[REDACTED_SECRET]" in res, f"Failed to redact: {inp} -> {res}"
    print("  [PASS] 5.4: Key-value patterns (api_key, bearer, token, password) masked")

    # 5.5 Deep nested metadata structures
    nested = {
        "level1": {
            "tokens": [
                "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
                "normal_string",
            ],
            "tuple_data": (
                {"sk_key": "sk-abcdefghijklmnopqrstuvwxyz12345678"},
            ),
        },
        "public_info": "safe_to_keep",
    }
    redacted_nested = redact_observation_secrets(nested)
    assert redacted_nested["level1"]["tokens"][0] == "[REDACTED_SECRET]"
    assert redacted_nested["level1"]["tokens"][1] == "normal_string"
    assert redacted_nested["level1"]["tuple_data"][0]["sk_key"] == "[REDACTED_SECRET]"
    assert redacted_nested["public_info"] == "safe_to_keep"
    print("  [PASS] 5.5: Deep nested dicts/tuples/lists recursively masked")

    # 5.6 ObservationConvergence & ObservationFactory span attribute redaction
    ws_temp = tempfile.mkdtemp(prefix="sclass_adv_s5_")
    try:
        ledger = LocalLedger(ws_temp)
        secret_token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
        script_file = os.path.join(ws_temp, "test_sec.py")
        with open(script_file, "w", encoding="utf-8") as f:
            f.write("import sys\nprint('executed')\n")

        req = ActionRequest(
            actor="agent:tester",
            session="sess_s5",
            capability=CAP_TERMINAL_EXECUTE,
            action="run_command",
            target="secret",
            parameters={"command": f"python \"{script_file}\" {secret_token}"},
            workspace=ws_temp,
        )
        cmd = [sys.executable, script_file, secret_token]
        _, receipt_sec = ObservationConvergence.execute_and_observe(
            request=req,
            command=cmd,
            timeout=10.0,
            ledger=ledger,
        )
        obs_rec = receipt_sec.observation_record
        assert obs_rec is not None
        assert secret_token not in obs_rec.command, f"Secret leaked into obs_rec.command: {obs_rec.command}"
        assert "[REDACTED_SECRET]" in obs_rec.command
        for span in obs_rec.semantic_spans:
            attrs = span.get("attributes", {})
            for k, v in attrs.items():
                if isinstance(v, str):
                    assert secret_token not in v, f"Secret leaked into span attr {k}: {v}"
        print("  [PASS] 5.6: ObservationRecord.command and semantic spans redact secrets")
    finally:
        shutil.rmtree(ws_temp, ignore_errors=True)


if __name__ == '__main__':
    print("===========================================================")
    print("Milestone 19 Adversarial Probe & Challenge Suite")
    print("===========================================================")
    test_suite_1_tampered_observation_records()
    test_suite_2_forged_receipts()
    test_suite_3_failing_process_claims()
    test_suite_4_non_git_and_corrupted_git_directories()
    test_suite_5_secret_redaction()
    print("\n===========================================================")
    print("ALL ADVERSARIAL PROBES COMPLETED SUCCESSFULLY!")
    print("===========================================================")

