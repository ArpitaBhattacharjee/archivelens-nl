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
    """Read a PDF one page at a time with Poppler (low memory).

    Use the page's own text layer if it has one; otherwise render the page
    to an image and OCR it. Poppler handles more scan formats than other
    libraries (e.g. JPEG 2000 pages saved by macOS Preview).
    """
    import re
    import subprocess
    import tempfile
    from pathlib import Path

    def run(*args: str) -> bytes:
        return subprocess.run(args, capture_output=True, check=True, timeout=180).stdout

    pages: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "doc.pdf"
        pdf.write_bytes(data)
        info = run("pdfinfo", str(pdf)).decode(errors="ignore")
        count = int(re.search(r"Pages:\s+(\d+)", info).group(1))
        for n in range(1, count + 1):
            text = run("pdftotext", "-f", str(n), "-l", str(n), "-layout", str(pdf), "-").decode(errors="ignore")
            # Count real letters/digits: some PDFs have a "text layer" of only invisible characters
            if len(re.findall(r"[A-Za-z0-9]", text)) < min_chars:  # scanned page: no real text layer
                prefix = Path(tmp) / f"page{n}"
                run("pdftoppm", "-r", "150", "-gray", "-f", str(n), "-l", str(n), "-png",
                    "-singlefile", str(pdf), str(prefix))
                png = prefix.with_suffix(".png")
                with Image.open(png) as image:
                    text = ocr_image(image)
                png.unlink(missing_ok=True)
            pages.append(text)
    return "\n\n".join(pages)
