class RateLimitedWebhookDispatcher:
    def __init__(self, max_rps: int = 5):
        pass

    def dispatch(self, url: str, payload: dict) -> str:
        pass

    def process_queue(self) -> int:
        pass

    def get_status(self, webhook_id: str) -> str:
        pass
