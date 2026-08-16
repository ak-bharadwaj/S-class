# target_module.py
class EventStore:
    def __init__(self):
        self.events = []

    def append(self, aggregate_id: str, event_type: str, data: dict, expected_version: int):
        current_events = [e for e in self.events if e['aggregate_id'] == aggregate_id]
        current_version = len(current_events)
        if expected_version != current_version:
            raise ValueError(f"Concurrency conflict: expected {expected_version}, got {current_version}")
        event = {
            'aggregate_id': aggregate_id,
            'event_type': event_type,
            'data': data,
            'version': current_version + 1
        }
        self.events.append(event)
        return event

    def get_projection(self, aggregate_id: str) -> dict:
        state = {'balance': 0, 'status': 'INITIAL'}
        for e in self.events:
            if e['aggregate_id'] == aggregate_id:
                if e['event_type'] == 'CREATED':
                    state['status'] = 'ACTIVE'
                elif e['event_type'] == 'DEPOSITED':
                    state['balance'] += e['data'].get('amount', 0)
        return state
