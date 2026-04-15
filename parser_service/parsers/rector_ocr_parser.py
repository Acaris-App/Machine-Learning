from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

from parsers.utils import (
    build_document_item,
    deduplicate_texts,
    detect_section_title,
    extract_ayat,
    extract_bab,
    extract_pasal,
    merge_enumerated_blocks,
    merge_lines_into_semantic_blocks,
    normalize_ocr_text,
    save_json,
)


OCR_FRONT_NOISE = {
    "salinan",
    "tentang",
    "dengan rahmat tuhan yang maha esa",
}


def preprocess_image_for_ocr(pil_image: Image.Image) -> Image.Image:
    image = np.array(pil_image)
    image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    return Image.fromarray(gray)


def ocr_image(pil_image: Image.Image) -> str:
    config = r"--oem 3 --psm 6"
    return pytesseract.image_to_string(pil_image, lang="ind+eng", config=config)


def clean_ocr_lines(text: str) -> List[str]:
    cleaned = normalize_ocr_text(text)
    if not cleaned:
        return []

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    result = []

    for line in lines:
        lowered = line.lower().strip()
        if lowered in OCR_FRONT_NOISE:
            continue

        # buang line header kampus yang terlalu administratif
        if "jalan prof. dr. soemantri" in lowered:
            continue
        if "telepon" in lowered and "fax" in lowered:
            continue

        result.append(line)

    return result


def classify_rector_block(block: str, current_pasal: str) -> str:
    b = block.strip()

    if not current_pasal:
        if b.startswith(("Menimbang", "Mengingat", "Memutuskan", "Menetapkan")):
            return "front_matter"
        if b.startswith(tuple(str(i) + "." for i in range(1, 50))) or b.startswith(("a.", "b.", "c.")):
            return "legal_basis_item"
        return "front_matter"

    if b.startswith("Pasal "):
        return "ocr_pasal_heading"

    return "ocr_pasal_body"


def parse_rector_pdf(
    file_path: str,
    source_name: str,
    output_dir: str,
    poppler_path: str | None = None,
    tesseract_cmd: str | None = None,
) -> List[Dict[str, Any]]:
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    images = convert_from_path(
        file_path,
        dpi=300,
        poppler_path=poppler_path,
    )

    documents: List[Dict[str, Any]] = []
    current_section_title = ""
    current_bab = ""
    current_pasal = ""
    current_ayat = ""

    for page_num, image in enumerate(images, start=1):
        preprocessed = preprocess_image_for_ocr(image)
        raw_text = ocr_image(preprocessed)

        lines = clean_ocr_lines(raw_text)
        if not lines:
            continue

        blocks = merge_lines_into_semantic_blocks(lines)
        blocks = merge_enumerated_blocks(blocks)
        blocks = deduplicate_texts(blocks)

        for block in blocks:
            detected_title = detect_section_title(block)
            if detected_title:
                current_section_title = detected_title

            found_bab = extract_bab(block)
            if found_bab:
                current_bab = found_bab

            found_pasal = extract_pasal(block)
            if found_pasal:
                current_pasal = found_pasal

            found_ayat = extract_ayat(block)
            if found_ayat:
                current_ayat = found_ayat

            if len(block.strip()) < 5:
                continue

            documents.append(
                build_document_item(
                    source_name=source_name,
                    document_type="peraturan_rektor",
                    page=page_num,
                    section_title=current_section_title,
                    content_type=classify_rector_block(block, current_pasal),
                    content=block,
                    extra_metadata={
                        "bab": current_bab,
                        "pasal": current_pasal,
                        "ayat": current_ayat,
                    },
                )
            )

    output_path = Path(output_dir) / f"{source_name}_parsed.json"
    save_json(output_path, {"documents": documents})
    return documents