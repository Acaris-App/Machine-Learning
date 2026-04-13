import re
from typing import List, Dict, Tuple

from config import (
    CHUNK_BLACKLIST_KEYWORDS,
    CHUNK_SIZE_WORDS,
    CHUNK_OVERLAP_WORDS,
    MIN_CHUNK_WORDS,
)


def word_count(text: str) -> int:
    return len((text or "").split())


def normalize_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_valid_chunk(text: str) -> bool:
    t = normalize_text(text).lower()
    wc = word_count(t)

    if wc < MIN_CHUNK_WORDS:
        return False

    for bad in CHUNK_BLACKLIST_KEYWORDS:
        if bad in t:
            return False

    if "................................" in t:
        return False

    if "penanggung jawab" in t and "tanda tangan" in t:
        return False

    return True


def split_regulation_sections(full_text: str) -> List[str]:
    """
    Untuk peraturan akademik dan peraturan rektor:
    split utama per Pasal.
    """
    text = normalize_text(full_text)
    parts = re.split(r"(?=\bPasal\s+\d+\b)", text, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text]


def split_curriculum_sections(full_text: str) -> List[str]:
    """
    Untuk kurikulum:
    split per BAB atau subbab utama.
    """
    text = normalize_text(full_text)
    parts = re.split(
        r"(?=(?:\bBAB\s+[IVXLCDM]+\b|^\d+\.\d+\.?\s))",
        text,
        flags=re.IGNORECASE | re.MULTILINE
    )
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text]


def sliding_window_chunk(
    text: str,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
    min_chunk_words: int = MIN_CHUNK_WORDS
) -> List[str]:
    words = text.split()

    if len(words) <= chunk_size_words:
        if len(words) >= min_chunk_words:
            return [" ".join(words)]
        return []

    chunks = []
    start = 0

    while start < len(words):
        end = start + chunk_size_words
        chunk_words = words[start:end]

        if len(chunk_words) < min_chunk_words:
            break

        chunks.append(" ".join(chunk_words))

        if end >= len(words):
            break

        start = end - overlap_words

    return chunks


def find_pages_for_text(page_map: List[Dict], section_text: str, full_text: str) -> Tuple[int, int]:
    """
    Cari estimasi page_start dan page_end dari posisi section_text di full_text.
    """
    section_text = section_text.strip()
    idx = full_text.find(section_text)
    if idx == -1:
        if page_map:
            return page_map[0]["page"], page_map[-1]["page"]
        return 1, 1

    start_char = idx
    end_char = idx + len(section_text)

    page_start = None
    page_end = None

    for p in page_map:
        if page_start is None and p["start_char"] <= start_char <= p["end_char"] + 2:
            page_start = p["page"]
        if p["start_char"] <= end_char <= p["end_char"] + 2:
            page_end = p["page"]

    if page_start is None and page_map:
        page_start = page_map[0]["page"]
    if page_end is None and page_map:
        page_end = page_map[-1]["page"]

    return page_start or 1, page_end or 1


def extract_titles_from_section(section_text: str, doc_type: str) -> Dict:
    lines = [line.strip() for line in section_text.splitlines() if line.strip()]

    chapter_title = None
    section_title = None
    subsection_title = None

    for line in lines[:30]:
        if re.match(r"^BAB\s+[IVXLCDM]+", line, flags=re.IGNORECASE):
            chapter_title = line
            break

    if doc_type in {"peraturan_akademik", "peraturan_rektor"}:
        for line in lines[:30]:
            if re.match(r"^Pasal\s+\d+", line, flags=re.IGNORECASE):
                section_title = line
                break
    else:
        for line in lines[:30]:
            if re.match(r"^\d+\.\d+\.?", line):
                subsection_title = line
                break

    return {
        "chapter_title": chapter_title,
        "section_title": section_title,
        "subsection_title": subsection_title,
    }


def chunk_document(
    full_text: str,
    page_map: List[Dict],
    doc_name: str,
    doc_type: str,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
    min_chunk_words: int = MIN_CHUNK_WORDS
) -> List[Dict]:
    full_text = normalize_text(full_text)
    if not full_text:
        return []

    if doc_type in {"peraturan_akademik", "peraturan_rektor"}:
        sections = split_regulation_sections(full_text)
    else:
        sections = split_curriculum_sections(full_text)

    all_chunks = []
    chunk_counter = 1

    for sec_idx, section_text in enumerate(sections, start=1):
        titles = extract_titles_from_section(section_text, doc_type)
        page_start, page_end = find_pages_for_text(page_map, section_text, full_text)

        chunks = sliding_window_chunk(
            section_text,
            chunk_size_words=chunk_size_words,
            overlap_words=overlap_words,
            min_chunk_words=min_chunk_words
        )

        if not chunks and word_count(section_text) >= min_chunk_words:
            chunks = [section_text]

        for local_idx, chunk_text in enumerate(chunks, start=1):
            chunk_text = normalize_text(chunk_text)
            if not is_valid_chunk(chunk_text):
                continue

            all_chunks.append({
                "chunk_id": f"{doc_type}_c{chunk_counter:04d}",
                "doc_name": doc_name,
                "doc_type": doc_type,
                "page_start": page_start,
                "page_end": page_end,
                "chapter_title": titles["chapter_title"],
                "section_title": titles["section_title"],
                "subsection_title": titles["subsection_title"],
                "section_index": sec_idx,
                "chunk_index_in_section": local_idx,
                "word_count": word_count(chunk_text),
                "text": chunk_text
            })
            chunk_counter += 1

    return all_chunks