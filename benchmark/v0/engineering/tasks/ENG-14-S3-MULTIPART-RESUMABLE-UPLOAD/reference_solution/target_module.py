# target_module.py
import hashlib

class MultipartUploader:
    def __init__(self, total_parts: int):
        self.total_parts = total_parts
        self.parts = {}

    def upload_part(self, part_num: int, data: bytes, expected_md5: str) -> bool:
        actual_md5 = hashlib.md5(data).hexdigest()
        if actual_md5 != expected_md5:
            raise ValueError(f"Checksum mismatch on part {part_num}")
        self.parts[part_num] = data
        return True

    def complete_upload(self) -> bytes:
        if len(self.parts) != self.total_parts:
            raise ValueError("Incomplete upload: missing parts")
        assembled = b""
        for i in range(1, self.total_parts + 1):
            if i not in self.parts:
                raise ValueError(f"Missing part sequence: {i}")
            assembled += self.parts[i]
        return assembled
