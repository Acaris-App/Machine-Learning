import pymupdf as fitz
from PIL import Image
import io

from config import OCR_LANG, OCR_DPI

try:
    import pytesseract
except ImportError:
    pytesseract = None


def extract_pdf_text_mode(pdf_path: str):
    doc = fitz.open(pdf_path)
    pages = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text") or ""
        pages.append({
            "page": page_num,
            "text": text
        })

    return pages


def extract_pdf_blocks_mode(pdf_path: str):
    doc = fitz.open(pdf_path)
    pages = []

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("blocks")
        sorted_blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

        texts = []
        for block in sorted_blocks:
            block_text = (block[4] or "").strip()
            if block_text:
                texts.append(block_text)

        page_text = "\n".join(texts)
        pages.append({
            "page": page_num,
            "text": page_text
        })

    return pages


def count_non_empty_pages(pages):
    return sum(1 for p in pages if (p.get("text") or "").strip())


def ocr_pdf_pages(pdf_path: str, lang: str = OCR_LANG, dpi: int = OCR_DPI):
    """
    OCR fallback untuk PDF scan / image-based.
    Butuh Tesseract OCR terinstall di OS.
    """
    if pytesseract is None:
        raise RuntimeError(
            "pytesseract belum terinstall. Jalankan: pip install pytesseract Pillow"
        )

    doc = fitz.open(pdf_path)
    pages = []
    matrix = fitz.Matrix(dpi / 72, dpi / 72)

    for page_num, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img_bytes = pix.tobytes("png")
        image = Image.open(io.BytesIO(img_bytes))

        text = pytesseract.image_to_string(image, lang=lang)
        pages.append({
            "page": page_num,
            "text": text or ""
        })

    return pages


def extract_pdf(pdf_path: str, mode: str = "blocks", use_ocr_fallback: bool = False):
    """
    Urutan:
    1. coba mode utama
    2. coba mode alternatif
    3. kalau diminta dan masih banyak kosong -> OCR
    """
    if mode == "blocks":
        primary = extract_pdf_blocks_mode(pdf_path)
        secondary = extract_pdf_text_mode(pdf_path)
        primary_name = "blocks"
        secondary_name = "text"
    else:
        primary = extract_pdf_text_mode(pdf_path)
        secondary = extract_pdf_blocks_mode(pdf_path)
        primary_name = "text"
        secondary_name = "blocks"

    primary_non_empty = count_non_empty_pages(primary)
    secondary_non_empty = count_non_empty_pages(secondary)

    if secondary_non_empty > primary_non_empty:
        best_pages = secondary
        used_mode = secondary_name
        best_non_empty = secondary_non_empty
    else:
        best_pages = primary
        used_mode = primary_name
        best_non_empty = primary_non_empty

    # OCR fallback kalau hasil masih sangat buruk
    if use_ocr_fallback and best_non_empty <= max(1, int(len(best_pages) * 0.1)):
        ocr_pages = ocr_pdf_pages(pdf_path)
        ocr_non_empty = count_non_empty_pages(ocr_pages)
        if ocr_non_empty > best_non_empty:
            return ocr_pages, "ocr"

    return best_pages, used_mode