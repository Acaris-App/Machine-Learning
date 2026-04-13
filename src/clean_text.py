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

    # gabung kata terpotong line break
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

    if line.isupper() and len(line.split()) <= 12:
        return True

    return False


def normalize_lines(text: str) -> str:
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


def looks_like_toc_page(text: str) -> bool:
    """
    Deteksi halaman daftar isi / daftar tabel yang memuat banyak entri
    seperti BAB I ..., 2.1 ..., dst.
    """
    t = text.lower()

    if "daftar isi" in t or "daftar tabel" in t or "daftar gambar" in t:
        return True

    # banyak pola daftar isi
    bab_hits = len(re.findall(r"\bBAB\s+[IVXLCDM]+\b", text, flags=re.IGNORECASE))
    sub_hits = len(re.findall(r"(?m)^\d+\.\d+\.?", text))
    dotted_hits = len(re.findall(r"\.{3,}", text))

    if bab_hits >= 3:
        return True
    if sub_hits >= 5:
        return True
    if dotted_hits >= 5:
        return True

    return False


def page_has_true_start_marker(text: str, doc_type: str) -> bool:
    """
    Untuk regulasi, cek start marker sungguhan, bukan daftar isi.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    first_lines = lines[:12]
    joined_lower = "\n".join(first_lines).lower()

    if "daftar isi" in joined_lower:
        return False

    if doc_type == "peraturan_akademik":
        for line in first_lines:
            if re.match(r"^BAB\s+I\b", line, flags=re.IGNORECASE):
                return True
            if re.match(r"^Pasal\s+1\b", line, flags=re.IGNORECASE):
                return True

    if doc_type == "peraturan_rektor":
        for line in first_lines:
            if re.match(r"^BAB\s+I\b", line, flags=re.IGNORECASE):
                return True
            if re.match(r"^Pasal\s+1\b", line, flags=re.IGNORECASE):
                return True

    return False


def trim_front_matter(cleaned_pages: List[Dict], doc_type: str) -> List[Dict]:
    """
    Reguler untuk regulasi.
    Kurikulum tidak dipotong di sini.
    """
    if not cleaned_pages:
        return []

    if doc_type == "kurikulum":
        return cleaned_pages

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


def normalize_chapter_title(lines: List[str], start_idx: int) -> str:
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

    for i, line in enumerate(lines[:60]):
        if re.match(r"^BAB\s+[IVXLCDM]+", line, flags=re.IGNORECASE):
            chapter_title = normalize_chapter_title(lines, i)
            break

    for line in lines[:60]:
        if re.match(r"^Pasal\s+\d+", line, flags=re.IGNORECASE):
            section_title = line.strip()
            break

    for line in lines[:60]:
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

    # untuk regulasi, daftar isi/tabel/gambar dibuang cepat
    if doc_type != "kurikulum":
        if (
            ("daftar isi" in lower)
            or ("daftar tabel" in lower)
            or ("daftar gambar" in lower)
        ):
            if not page_has_true_start_marker(text, doc_type):
                return ""

    return text.strip()


def trim_curriculum_document_level(cleaned_pages: List[Dict]) -> List[Dict]:
    """
    Khusus kurikulum:
    - abaikan halaman-halaman TOC/front matter
    - mulai dari halaman yang benar-benar isi, bukan sekadar memuat string BAB I di daftar isi
    - stop sebelum BIODATA DOSEN PROGRAM STUDI
    """
    if not cleaned_pages:
        return []

    started = False
    result = []

    for item in cleaned_pages:
        text = item["cleaned_text"]
        text_upper = text.upper()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        first_lines = lines[:15]

        # tolak semua halaman TOC/daftar isi
        if looks_like_toc_page(text):
            continue

        # cari start yang benar:
        # ada heading BAB I pada baris awal, bukan hanya substring biasa
        if not started:
            found_real_start = False
            for idx, line in enumerate(first_lines):
                if re.match(r"^BAB\s+I\b", line, flags=re.IGNORECASE):
                    # kalau "BAB I" berdiri sendiri, cek line berikutnya
                    if "IDENTITAS PROGRAM STUDI" in line.upper():
                        found_real_start = True
                        break
                    if idx + 1 < len(first_lines) and "IDENTITAS PROGRAM STUDI" in first_lines[idx + 1].upper():
                        found_real_start = True
                        break

                # fallback: kadang heading sudah menyatu
                if re.match(r"^BAB\s+I\b.*IDENTITAS PROGRAM STUDI", line, flags=re.IGNORECASE):
                    found_real_start = True
                    break

            if not found_real_start:
                continue

            started = True

        # stop ketika masuk back matter
        stop = False
        for marker in CURRICULUM_END_MARKERS:
            if marker.upper() in text_upper:
                stop = True
                break

        if stop:
            break

        result.append(item)

    return result


def clean_document_pages(pages: List[Dict], doc_type: str) -> List[Dict]:
    cleaned_pages = []

    for item in pages:
        raw_text = item.get("text", "")
        cleaned_text = clean_page_text(raw_text, doc_type)

        if not cleaned_text:
            continue

        if doc_type != "kurikulum":
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
        cleaned_pages = trim_curriculum_document_level(cleaned_pages)

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