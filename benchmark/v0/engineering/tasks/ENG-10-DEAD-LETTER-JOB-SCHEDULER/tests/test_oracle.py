import pytest
from target_module import JobScheduler

def test_dlq_escalation():
    scheduler = JobScheduler(max_retries=2, base_delay_sec=0.01)
    
    def failing_job():
        raise RuntimeError("DB connection timeout")
        
    status = scheduler.execute_job('job_99', failing_job)
    assert status == "MOVED_TO_DLQ"
    dlq = scheduler.get_dlq()
    assert len(dlq) == 1
    assert dlq[0]['job_id'] == 'job_99'
