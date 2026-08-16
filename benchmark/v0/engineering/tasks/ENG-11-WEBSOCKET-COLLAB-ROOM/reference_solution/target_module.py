# target_module.py
class CollabDocument:
    def __init__(self):
        self.vector_clock = {}
        self.content = ""

    def apply_update(self, client_id: str, clock: dict, content: str) -> bool:
        # Check causality: new clock must not be strictly dominated by local clock
        local_v = self.vector_clock.get(client_id, 0)
        remote_v = clock.get(client_id, 0)
        if remote_v <= local_v and self.content != "":
            return False # Ignore stale or duplicate update
        
        self.vector_clock[client_id] = remote_v
        self.content = content
        return True

    def get_content(self) -> str:
        return self.content
