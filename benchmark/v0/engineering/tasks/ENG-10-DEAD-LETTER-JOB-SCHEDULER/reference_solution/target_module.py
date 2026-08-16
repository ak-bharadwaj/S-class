# target_module.py
class JobScheduler:
    def __init__(self, max_retries: int = 3, base_delay_sec: float = 1.0):
        self.max_retries = max_retries
        self.base_delay_sec = base_delay_sec
        self.dlq = []

    def execute_job(self, job_id: str, job_fn) -> str:
        attempts = 0
        while attempts <= self.max_retries:
            try:
                job_fn()
                return "COMPLETED"
            except Exception as e:
                attempts += 1
                if attempts > self.max_retries:
                    self.dlq.append({'job_id': job_id, 'error': str(e)})
                    return "MOVED_TO_DLQ"
                # Backoff delay = base * 2^(attempts - 1)
                delay = self.base_delay_sec * (2 ** (attempts - 1))

    def get_dlq(self) -> list:
        return list(self.dlq)
