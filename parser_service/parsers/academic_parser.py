from pathlib import Path
from typing import Any, Dict, List

import pdfplumber

from parsers.utils import (
    build_document_item,
    clean_basic_text,
    deduplicate_texts,
    detect_section_title,
    extract_bab,
    extract_pasal,
    merge_enumerated_blocks,
    merge_lines_into_semantic_blocks,
    save_json,
)


ACADEMIC_HEADER_NOISE = {
    "kementerian pendidikan, kebudayaan,",
    "riset, dan teknologi",
    "universitas lampung",
    "jalan prof. dr. soemantri brojonegoro no. 1 bandar lampung 35145",
    "telepon (0721) 701609, 702673, 702971, 703475, fax. (0721) 702767",
    "laman https://www.unila.ac.id",
    "dengan rahmat tuhan yang maha esa",
}


def extract_text_per_page(file_path: str) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            raw_text = page.extract_text() or ""
            pages.append({"page": page_num, "raw_text": raw_text})

    return pages


def clean_academic_lines(raw_text: str) -> List[str]:
    cleaned = clean_basic_text(raw_text)
    if not cleaned:
        return []

    lines = [line.strip() for line in cleaned.split("\n") if line.strip()]
    result: List[str] = []

    for line in lines:
        lowered = line.lower().strip()
        if lowered in ACADEMIC_HEADER_NOISE:
            continue
        result.append(line)

    return result


def classify_academic_block(block: str, current_pasal: str) -> str:
    b = block.strip()

    if not current_pasal:
        if b.startswith(("Menimbang", "Memperhatikan", "Memutuskan", "Menetapkan")):
            return "front_matter"
        if b.startswith(tuple(str(i) + "." for i in range(1, 40))):
            return "legal_basis_item"
        return "front_matter"

    if b.startswith("Pasal "):
        return "pasal_heading"

    return "pasal_body"


def parse_academic_pdf(
    file_path: str,
    source_name: str,
    output_dir: str,
) -> List[Dict[str, Any]]:
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    pages = extract_text_per_page(file_path)

    documents: List[Dict[str, Any]] = []
    current_section_title = ""
    current_bab = ""
    current_pasal = ""

    for page_data in pages:
        page_num = page_data["page"]
        raw_text = page_data["raw_text"]

        lines = clean_academic_lines(raw_text)
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

            if len(block.strip()) < 5:
                continue

            documents.append(
                build_document_item(
                    source_name=source_name,
                    document_type="peraturan_akademik",
                    page=page_num,
                    section_title=current_section_title,
                    content_type=classify_academic_block(block, current_pasal),
                    content=block,
                    extra_metadata={
                        "bab": current_bab,
                        "pasal": current_pasal,
                    },
                )
            )

    output_path = Path(output_dir) / f"{source_name}_parsed.json"
    save_json(output_path, {"documents": documents})
    return documents