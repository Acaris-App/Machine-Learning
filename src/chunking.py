import re
from typing import List, Dict


def word_count(text: str) -> int:
    return len(text.split())


def split_into_sections(text: str):
    """
    Pecah berdasarkan heading logis jika ada.
    Cocok untuk BAB / Pasal.
    """
    pattern = r"(?=(?:\bBAB\s+[IVXLCDM]+\b|\bPasal\s+\d+\b))"
    parts = re.split(pattern, text, flags=re.IGNORECASE)

    sections = []
    for part in parts:
        part = part.strip()
        if part:
            sections.append(part)

    return sections if sections else [text]


def sliding_window_chunk(
    text: str,
    chunk_size_words: int = 400,
    overlap_words: int = 80,
    min_chunk_words: int = 40
):
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


def chunk_document_pages(
    cleaned_pages: List[Dict],
    doc_name: str,
    doc_type: str,
    chunk_size_words: int = 400,
    overlap_words: int = 80,
    min_chunk_words: int = 40
):
    """
    Strategi:
    1. per halaman
    2. kalau ada section logis (BAB/Pasal), pecah dulu
    3. baru sliding window
    """
    all_chunks = []
    chunk_counter = 1

    for page_item in cleaned_pages:
        page = page_item["page"]
        cleaned_text = page_item["cleaned_text"]
        chapter_title = page_item.get("chapter_title")
        section_title = page_item.get("section_title")

        if not cleaned_text.strip():
            continue

        sections = split_into_sections(cleaned_text)

        for sec_idx, section_text in enumerate(sections, start=1):
            chunks = sliding_window_chunk(
                section_text,
                chunk_size_words=chunk_size_words,
                overlap_words=overlap_words,
                min_chunk_words=min_chunk_words
            )

            # kalau section kecil tapi bermakna, tetap ambil
            if not chunks and word_count(section_text) >= min_chunk_words:
                chunks = [section_text]

            for local_idx, chunk_text in enumerate(chunks, start=1):
                all_chunks.append({
                    "chunk_id": f"{doc_type}_p{page}_c{chunk_counter:04d}",
                    "doc_name": doc_name,
                    "doc_type": doc_type,
                    "page_start": page,
                    "page_end": page,
                    "chapter_title": chapter_title,
                    "section_title": section_title,
                    "section_index": sec_idx,
                    "chunk_index_in_section": local_idx,
                    "word_count": word_count(chunk_text),
                    "text": chunk_text
                })
                chunk_counter += 1

    return all_chunks