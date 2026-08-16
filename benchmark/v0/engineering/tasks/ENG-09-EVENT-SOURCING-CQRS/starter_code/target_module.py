# target_module.py
class EventStore:
    def append(self, aggregate_id: str, event_type: str, data: dict, expected_version: int):
        pass
    def get_projection(self, aggregate_id: str) -> dict:
        pass
