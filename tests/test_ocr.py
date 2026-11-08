import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

pytestmark = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")


def _fake_scan(text: str) -> bytes:
    img = Image.new("RGB", (1400, 200), "white")
    font = ImageFont.load_default(size=64)
    ImageDraw.Draw(img).text((40, 60), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_ocr_reads_text_from_image():
    from app.ocr import ocr_image_bytes

    result = ocr_image_bytes(_fake_scan("NEWFOUNDLAND ARCHIVE 1892"))
    assert "ARCHIVE" in result.upper()
