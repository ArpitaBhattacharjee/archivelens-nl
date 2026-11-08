"""OCR with Tesseract: images and scanned PDFs to text."""
import io

import pytesseract
from PIL import Image, ImageOps


def ocr_image(image: Image.Image) -> str:
    gray = ImageOps.grayscale(image)          # OCR works better in grayscale
    gray = ImageOps.autocontrast(gray)        # helps faded old paper
    return pytesseract.image_to_string(gray)


def ocr_image_bytes(data: bytes) -> str:
    return ocr_image(Image.open(io.BytesIO(data)))


def pdf_text(data: bytes, min_chars: int = 40) -> str:
    """Use the PDF's own text layer if it has one; otherwise OCR each page."""
    import fitz  # PyMuPDF

    pages: list[str] = []
    with fitz.open(stream=data, filetype="pdf") as pdf:
        for page in pdf:
            text = page.get_text().strip()
            if len(text) < min_chars:  # scanned page: no real text layer
                pix = page.get_pixmap(dpi=200)
                text = ocr_image(Image.open(io.BytesIO(pix.tobytes("png"))))
            pages.append(text)
    return "\n\n".join(pages)
