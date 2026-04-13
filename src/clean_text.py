import re
from typing import List, Dict, Tuple

from config import (
    FRONT_MATTER_KEYWORDS,
    CURRICULUM_END_MARKERS,
    MIN_MEANINGFUL_WORDS_PER_PAGE,
)


def word_count(text: str) -> int:
    return len((text or "").split())


def basic_clean(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\u0003", " ")
    text = text.replace("\uf0b7", "•")
    text = text.replace("\u00a0", " ")

    # gabung kata yang terpotong line break
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # rapikan whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # trim per line
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def remove_common_noise(text: str) -> str:
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    text = re.sub(r"(?m)^\s*(?:[ivxlcdm]+)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?m)^[_\-=\s]{5,}$", "", text)

    text = re.sub(r"(?im)^universitas lampung\s*$", "", text)
    text = re.sub(r"(?im)^kementerian pendidikan.*?$", "", text)
    text = re.sub(r"(?im)^telepon.*?$", "", text)
    text = re.sub(r"(?im)^laman\s+https?://.*?$", "", text)
    text = re.sub(r"(?im)^jalan .*?$", "", text)
    text = re.sub(r"(?im)^salinan\s*$", "", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_heading_like(line: str) -> bool:
    line = line.strip()

    patterns = [
        r"^BAB\s+[IVXLCDM]+",
        r"^Pasal\s+\d+",
        r"^Menimbang:",
        r"^Mengingat:",
        r"^Memutuskan:",
        r"^Menetapkan:",
        r"^\(\d+\)",
        r"^[a-zA-Z]\.",
        r"^\d+\.\d+\.?",
        r"^\d+\.",
    ]

    for p in patterns:
        if re.match(p, line, flags=re.IGNORECASE):
            return True

    # heading uppercase pendek
    if line.isupper() and len(line.split()) <= 12:
        return True

    return False


def normalize_lines(text: str) -> str:
    """
    Gabungkan baris pecah, tapi jangan satukan heading ke paragraf berikutnya.
    """
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines()]
    merged = []

    for line in lines:
        if not line:
            merged.append("")
            continue

        if is_heading_like(line):
            merged.append(line)
            continue

        if not merged:
            merged.append(line)
            continue

        prev = merged[-1]

        # kalau prev heading, jangan digabung
        if is_heading_like(prev):
            merged.append(line)
            continue

        if prev and not prev.endswith((".", ":", ";", "?", "!")):
            merged[-1] = prev + " " + line
        else:
            merged.append(line)

    text = "\n".join(merged)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_front_matter_page(text: str) -> bool:
    t = (text or "").lower().strip()

    if word_count(t) < MIN_MEANINGFUL_WORDS_PER_PAGE:
        return True

    return any(k in t for k in FRONT_MATTER_KEYWORDS)


def page_has_true_start_marker(text: str, doc_type: str) -> bool:
    """
    Cek start marker yang benar-benar ada sebagai heading halaman,
    bukan sekadar tercantum di daftar isi.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    first_lines = lines[:12]

    joined_lower = "\n".join(first_lines).lower()

    # kalau masih daftar isi, jangan dianggap start marker
    if "daftar isi" in joined_lower:
        return False

    if doc_type == "peraturan_akademik":
        for line in first_lines:
            if re.match(r"^BAB\s+I\b", line, flags=re.IGNORECASE):
                return True
            if re.match(r"^Pasal\s+1\b", line, flags=re.IGNORECASE):
                return True

    if doc_type == "kurikulum":
        for line in first_lines:
            if re.match(r"^BAB\s+I\b", line, flags=re.IGNORECASE):
                # harus heading sungguhan, bukan string di daftar isi
                if "identitas program studi" in line.lower():
                    return True

    if doc_type == "peraturan_rektor":
        for line in first_lines:
            if re.match(r"^BAB\s+I\b", line, flags=re.IGNORECASE):
                return True
            if re.match(r"^Pasal\s+1\b", line, flags=re.IGNORECASE):
                return True

    return False


def trim_front_matter(cleaned_pages: List[Dict], doc_type: str) -> List[Dict]:
    if not cleaned_pages:
        return []

    start_idx = 0
    found = False

    for idx, item in enumerate(cleaned_pages):
        if page_has_true_start_marker(item["cleaned_text"], doc_type):
            start_idx = idx
            found = True
            break

    if found:
        return cleaned_pages[start_idx:]

    return cleaned_pages


def trim_curriculum_back_matter(cleaned_pages: List[Dict]) -> List[Dict]:
    if not cleaned_pages:
        return []

    for idx, item in enumerate(cleaned_pages):
        t = item["cleaned_text"].upper()
        for marker in CURRICULUM_END_MARKERS:
            if marker.upper() in t:
                return cleaned_pages[:idx]

    return cleaned_pages


def normalize_chapter_title(lines: List[str], start_idx: int) -> str:
    """
    Ambil chapter_title yang ringkas dan bersih.
    Kalau line pertama hanya 'BAB I', gabungkan dengan line berikutnya jika cocok.
    """
    line = re.sub(r"\.{3,}.*$", "", lines[start_idx]).strip()

    if re.match(r"^BAB\s+[IVXLCDM]+$", line, flags=re.IGNORECASE):
        if start_idx + 1 < len(lines):
            next_line = re.sub(r"\.{3,}.*$", "", lines[start_idx + 1]).strip()
            if next_line and len(next_line.split()) <= 12:
                return f"{line} {next_line}".strip()

    return line.strip()


def extract_structure_metadata(text: str) -> Dict:
    chapter_title = None
    section_title = None
    subsection_title = None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for i, line in enumerate(lines[:50]):
        if re.match(r"^BAB\s+[IVXLCDM]+", line, flags=re.IGNORECASE):
            chapter_title = normalize_chapter_title(lines, i)
            break

    for line in lines[:50]:
        if re.match(r"^Pasal\s+\d+", line, flags=re.IGNORECASE):
            section_title = line.strip()
            break

    for line in lines[:50]:
        if re.match(r"^\d+\.\d+\.?", line):
            subsection_title = line.strip()
            break

    return {
        "chapter_title": chapter_title,
        "section_title": section_title,
        "subsection_title": subsection_title,
    }


def clean_page_text(text: str, doc_type: str) -> str:
    text = basic_clean(text)
    text = remove_common_noise(text)
    text = normalize_lines(text)

    lower = text.lower()

    # daftar isi/tabel/gambar non-substantif
    if (
        ("daftar isi" in lower) or
        ("daftar tabel" in lower) or
        ("daftar gambar" in lower)
    ):
        if not page_has_true_start_marker(text, doc_type):
            return ""

    return text.strip()


def clean_document_pages(pages: List[Dict], doc_type: str) -> List[Dict]:
    cleaned_pages = []

    for item in pages:
        raw_text = item.get("text", "")
        cleaned_text = clean_page_text(raw_text, doc_type)

        if not cleaned_text:
            continue

        if is_front_matter_page(cleaned_text) and not page_has_true_start_marker(cleaned_text, doc_type):
            continue

        meta = extract_structure_metadata(cleaned_text)

        cleaned_pages.append({
            "page": item["page"],
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "chapter_title": meta["chapter_title"],
            "section_title": meta["section_title"],
            "subsection_title": meta["subsection_title"],
        })

    cleaned_pages = trim_front_matter(cleaned_pages, doc_type)

    if doc_type == "kurikulum":
        cleaned_pages = trim_curriculum_back_matter(cleaned_pages)

    return cleaned_pages


def combine_pages_to_document(cleaned_pages: List[Dict]) -> Tuple[str, List[Dict]]:
    parts = []
    page_map = []
    cursor = 0

    for item in cleaned_pages:
        text = item["cleaned_text"].strip()
        if not text:
            continue

        start = cursor
        parts.append(text)
        cursor += len(text)
        end = cursor

        page_map.append({
            "page": item["page"],
            "start_char": start,
            "end_char": end,
            "chapter_title": item.get("chapter_title"),
            "section_title": item.get("section_title"),
            "subsection_title": item.get("subsection_title"),
        })

        parts.append("\n\n")
        cursor += 2

    full_text = "".join(parts).strip()
    return full_text, page_map