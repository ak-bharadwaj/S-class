import pytest
import hashlib
from target_module import MultipartUploader

def test_multipart_resumable_upload():
    uploader = MultipartUploader(total_parts=2)
    p1 = b"Hello, "
    p2 = b"World!"
    c1 = hashlib.md5(p1).hexdigest()
    c2 = hashlib.md5(p2).hexdigest()
    
    assert uploader.upload_part(1, p1, c1) is True
    
    # Invalid checksum test
    with pytest.raises(ValueError):
        uploader.upload_part(2, p2, "bad_checksum")
        
    assert uploader.upload_part(2, p2, c2) is True
    res = uploader.complete_upload()
    assert res == b"Hello, World!"
