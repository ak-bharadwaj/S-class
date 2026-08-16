# target_module.py
class CollabDocument:
    def __init__(self):
        self.content = ""
    def apply_update(self, client_id: str, clock: dict, content: str) -> bool:
        self.content = content # Flawed: ignores vector clocks, accepts stale updates
        return True
    def get_content(self) -> str:
        return self.content
