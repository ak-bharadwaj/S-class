# target_module.py
class JobScheduler:
    def __init__(self, max_retries: int = 3, base_delay_sec: float = 1.0):
        pass
    def execute_job(self, job_id: str, job_fn) -> str:
        try:
            job_fn()
        except Exception:
            pass # Flawed: silent exception swallow, no retries, no DLQ
        return "COMPLETED"
    def get_dlq(self) -> list:
        return []
