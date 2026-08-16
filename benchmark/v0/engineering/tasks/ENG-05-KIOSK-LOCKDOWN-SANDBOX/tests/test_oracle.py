import pytest
import target_module

def test_sandbox_containment():
    assert target_module.is_syscall_allowed('read', '/tmp/sandbox/file.txt') is True
    assert target_module.is_syscall_allowed('execve', '/tmp/sandbox/file.txt') is False
    assert target_module.is_syscall_allowed('read', '/etc/passwd') is False
