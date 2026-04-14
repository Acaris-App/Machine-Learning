import re
from typing import List, Dict, Tuple

from config import (
    CHUNK_BLACKLIST_KEYWORDS,
    CHUNK_SIZE_WORDS,
    CHUNK_OVERLAP_WORDS,
    MIN_CHUNK_WORDS,
    REKTOR_ALLOWED_PASAL,
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

    return True


# =========================
# REGULATION SPLIT
# =========================

def trim_regulation_to_substantive_text(full_text: str) -> str:
    match = re.search(r"\bPasal\s+1\b", full_text, flags=re.IGNORECASE)
    if match:
        return full_text[match.start():].strip()
    return full_text.strip()


def split_regulation_sections(full_text: str) -> List[str]:
    text = normalize_text(trim_regulation_to_substantive_text(full_text))
    parts = re.split(r"(?=\bPasal\s+\d+\b)", text, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text]


def filter_rektor_allowed_pasal(sections: List[str]) -> List[str]:
    allowed = set(REKTOR_ALLOWED_PASAL)
    kept = []

    for sec in sections:
        m = re.match(r"^\s*Pasal\s+(\d+)\b", sec, flags=re.IGNORECASE)
        if not m:
            continue
        pasal_num = int(m.group(1))
        if pasal_num in allowed:
            kept.append(sec)

    return kept


# =========================
# CURRICULUM SPLIT
# =========================

def split_by_bab(text: str) -> List[str]:
    """
    Split per BAB.
    """
    text = normalize_text(text)
    parts = re.split(r"(?=\bBAB\s+[IVXLCDM]+\b)", text, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text]


def split_bab_by_subsection(text: str) -> List[str]:
    """
    Split per subbagian seperti 1.1, 2.1, 5.2, dst.
    Kalau tidak ada, kembalikan utuh.
    """
    parts = re.split(r"(?=^\d+\.\d+\.?\s)", text, flags=re.MULTILINE)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text]


def split_by_semester_markers(text: str) -> List[str]:
    """
    Split per Semester 1 / Semester 2 / dst kalau ada.
    Ini penting banget untuk pertanyaan mahasiswa tentang distribusi semester.
    """
    parts = re.split(r"(?=\bSemester\s+\d+\b)", text, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    return parts if parts else [text]


def curriculum_section_score(text: str) -> int:
    """
    Skor sederhana untuk mendeteksi section yang kaya informasi retrieval-friendly.
    """
    score = 0
    t = text.lower()

    if "semester" in t:
        score += 2
    if "mata kuliah" in t:
        score += 2
    if "sks" in t:
        score += 2
    if "cpl" in t:
        score += 1
    if "kurikulum" in t:
        score += 1

    return score


def split_curriculum_sections(full_text: str) -> List[str]:
    """
    Strategi baru:
    1. split per BAB
    2. split lagi per subbagian 1.1 / 2.1 / dst
    3. split lagi per Semester N kalau ada

    Tujuan:
    bikin chunk kurikulum jauh lebih granular dan retrieval-friendly.
    """
    full_text = normalize_text(full_text)

    babs = split_by_bab(full_text)
    final_sections = []

    for bab_text in babs:
        subparts = split_bab_by_subsection(bab_text)

        for sub in subparts:
            semester_parts = split_by_semester_markers(sub)

            for part in semester_parts:
                part = normalize_text(part)
                if part:
                    final_sections.append(part)

    return final_sections if final_sections else [full_text]


# =========================
# CHUNKING CORE
# =========================

def sliding_window_chunk(
    text: str,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
    min_chunk_words: int = MIN_CHUNK_WORDS,
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
    semester_title = None

    for line in lines[:50]:
        if re.match(r"^BAB\s+[IVXLCDM]+", line, flags=re.IGNORECASE):
            chapter_title = line
            break

    if doc_type in {"peraturan_akademik", "peraturan_rektor"}:
        for line in lines[:50]:
            if re.match(r"^Pasal\s+\d+", line, flags=re.IGNORECASE):
                section_title = line
                break
    else:
        for line in lines[:50]:
            if re.match(r"^\d+\.\d+\.?", line):
                subsection_title = line
                break

        for line in lines[:50]:
            if re.match(r"^Semester\s+\d+", line, flags=re.IGNORECASE):
                semester_title = line
                break

    return {
        "chapter_title": chapter_title,
        "section_title": section_title,
        "subsection_title": subsection_title,
        "semester_title": semester_title,
    }


def enrich_curriculum_chunk_text(chunk_text: str, titles: Dict) -> str:
    """
    Untuk kurikulum, prepend metadata ke text chunk supaya retrieval lebih mudah.
    Ini penting supaya kata seperti BAB / subbagian / Semester ikut masuk ke embedding.
    """
    prefix_parts = []

    if titles.get("chapter_title"):
        prefix_parts.append(titles["chapter_title"])
    if titles.get("subsection_title"):
        prefix_parts.append(titles["subsection_title"])
    if titles.get("semester_title"):
        prefix_parts.append(titles["semester_title"])

    if prefix_parts:
        prefix = " | ".join(prefix_parts)
        return f"{prefix}\n{chunk_text}"

    return chunk_text


def chunk_document(
    full_text: str,
    page_map: List[Dict],
    doc_name: str,
    doc_type: str,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    overlap_words: int = CHUNK_OVERLAP_WORDS,
    min_chunk_words: int = MIN_CHUNK_WORDS,
) -> List[Dict]:
    full_text = normalize_text(full_text)
    if not full_text:
        return []

    if doc_type == "peraturan_akademik":
        sections = split_regulation_sections(full_text)

    elif doc_type == "peraturan_rektor":
        sections = split_regulation_sections(full_text)
        sections = filter_rektor_allowed_pasal(sections)

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
            min_chunk_words=min_chunk_words,
        )

        if not chunks and word_count(section_text) >= min_chunk_words:
            chunks = [section_text]

        for local_idx, chunk_text in enumerate(chunks, start=1):
            chunk_text = normalize_text(chunk_text)

            if doc_type == "kurikulum":
                chunk_text = enrich_curriculum_chunk_text(chunk_text, titles)

            if not is_valid_chunk(chunk_text):
                continue

            all_chunks.append({
                "chunk_id": f"{doc_type}_c{chunk_counter:04d}",
                "doc_name": doc_name,
                "doc_type": doc_type,
                "page_start": page_start,
                "page_end": page_end,
                "chapter_title": titles.get("chapter_title"),
                "section_title": titles.get("section_title"),
                "subsection_title": titles.get("subsection_title"),
                "semester_title": titles.get("semester_title"),
                "section_index": sec_idx,
                "chunk_index_in_section": local_idx,
                "word_count": word_count(chunk_text),
                "text": chunk_text,
            })
            chunk_counter += 1

    return all_chunks