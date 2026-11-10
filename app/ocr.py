"""OCR with Tesseract: images and scanned PDFs to text."""
import io

import pytesseract
from PIL import Image, ImageOps


MAX_SIDE = 1800  # big enough for OCR, small enough for a 512 MB server


def ocr_image(image: Image.Image) -> str:
    image.thumbnail((MAX_SIDE, MAX_SIDE))  # shrink very large scans (keeps aspect ratio)
    gray = ImageOps.grayscale(image)          # OCR works better in grayscale
    gray = ImageOps.autocontrast(gray)        # helps faded old paper
    return pytesseract.image_to_string(gray)


def ocr_image_bytes(data: bytes) -> str:
    image = Image.open(io.BytesIO(data))
    if image.format == "JPEG":
        # Decode a big JPEG at reduced size: uses far less memory than decoding it fully first
        image.draft("RGB", (MAX_SIDE, MAX_SIDE))
    return ocr_image(image)


def pdf_text(data: bytes, min_chars: int = 40) -> str:
    """Use the PDF's own text layer if it has one; otherwise OCR each page."""
    import fitz  # PyMuPDF

    pages: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as pdf:
        for page in pdf:
            text = page.get_text().strip()
            if len(text) < min_chars:  # scanned page: no real text layer
                pix = page.get_pixmap(dpi=150)
                text = ocr_image(Image.open(io.BytesIO(pix.tobytes("png"))))
            pages.append(text)
    return "\n\n".join(pages)
