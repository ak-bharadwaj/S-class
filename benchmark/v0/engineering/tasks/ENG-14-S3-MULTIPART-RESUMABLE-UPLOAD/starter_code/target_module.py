# target_module.py
class MultipartUploader:
    def __init__(self, total_parts: int):
        pass
    def upload_part(self, part_num: int, data: bytes, checksum: str) -> bool:
        pass
    def complete_upload(self) -> bytes:
        pass
