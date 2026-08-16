class ArtifactTamperError(Exception): pass

class WorkspaceGarbageCollector:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def purge_expired_runs(self, max_age_days: int = 30) -> int:
        pass

    def verify_artifact_integrity(self) -> bool:
        pass

    def get_storage_breakdown(self) -> dict:
        pass
