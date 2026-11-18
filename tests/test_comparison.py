import hashlib
import io
import numpy as np
import pytest
from PIL import Image
from core.comparison import comparison_images
from core.detector import Config, detect, read_image
from core.dataset import DATA_ROOT
from core.comparison import reference_image


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


def test_reference_marks_annotated_cells_only():
    data=(DATA_ROOT/'distinct/images/103.png').read_bytes()
    annotation=(DATA_ROOT/'distinct/bbs/103.txt').read_bytes()
    marked=reference_image(data,annotation,7)
    pixels=np.array(Image.open(io.BytesIO(marked)))
    assert np.any(np.all(pixels==[41,153,255],axis=2))
    assert not np.array_equal(pixels,np.array(read_image(data)))
    with pytest.raises(ValueError,match='정답 표시'):
        reference_image(data,annotation,8)
