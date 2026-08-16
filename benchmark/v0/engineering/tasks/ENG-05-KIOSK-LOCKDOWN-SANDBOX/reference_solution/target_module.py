# target_module.py
import os

ALLOWED_SYSCALLS = {'read', 'write', 'stat', 'exit'}
SANDBOX_PREFIX = "/tmp/sandbox"

def is_syscall_allowed(syscall_name: str, path_arg: str) -> bool:
    if syscall_name not in ALLOWED_SYSCALLS:
        return False
    clean_path = os.path.normpath(path_arg).replace("\\", "/")
    if not clean_path.startswith(SANDBOX_PREFIX):
        return False
    return True
