import hashlib
import io
import numpy as np
import pytest
from PIL import Image
from core.comparison import comparison_images
from core.detector import Config, detect, read_image
from core.dataset import DATA_ROOT


def test_before_unchanged_after_has_detection_marks():
    data=(DATA_ROOT/'distinct/images/101.png').read_bytes()
    expected=detect(read_image(data),Config())['count']
    before,after=comparison_images(data,Config(),expected,hashlib.sha256(data).hexdigest())
    original=np.array(read_image(data))
    assert np.array_equal(np.array(Image.open(io.BytesIO(before))),original)
    assert not np.array_equal(np.array(Image.open(io.BytesIO(after))),original)
    assert Image.open(io.BytesIO(after)).size==(640,640)
    with pytest.raises(ValueError,match='다릅니다'):
        comparison_images(data,Config(),expected+1,hashlib.sha256(data).hexdigest())
    with pytest.raises(ValueError,match='변경'):
        comparison_images(data,Config(),expected,'wrong-hash')
