import re
from typing import List, Dict, Tuple

from config import MIN_MEANINGFUL_WORDS_PER_PAGE


def word_count(text: str) -> int:
    return len((text or "").split())


def basic_clean(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\x00", " ")
    text = text.replace("\u0003", " ")
    text = text.replace("\uf0b7", "•")
    text = text.replace("\u00a0", " ")

    # gabung kata terpotong oleh hyphen line break
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # rapikan whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # trim tiap baris
    text = "\n".join(line.strip() for line in text.splitlines())

    # rapikan baris kosong
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def remove_common_noise(text: str) -> str:
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)
    text = re.sub(r"(?m)^\s*(?:[ivxlcdm]+)\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"(?m)^[_\-=\s]{5,}$", "", text)

    # header/footer umum
    text = re.sub(r"(?im)^universitas lampung\s*$", "", text)
    text = re.sub(r"(?im)^kementerian pendidikan.*?$", "", text)
    text = re.sub(r"(?im)^telepon.*?$", "", text)
    text = re.sub(r"(?im)^laman\s+https?://.*?$", "", text)
    text = re.sub(r"(?im)^jalan .*?$", "", text)
    text = re.sub(r"(?im)^salinan\s*$", "", text)

    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_lines(text: str) -> str:
    """
    Gabungkan line yang pecah tapi tetap jaga heading/pasal/subjudul.
    """
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines()]
    merged = []

    heading_pattern = re.compile(
        r"^(BAB\s+[IVXLCDM]+|Pasal\s+\d+|Menimbang:|Mengingat:|Memutuskan:|Menetapkan:|\(\d+\)|[a-zA-Z]\.|"
        r"\d+\.\d+\.?|\d+\.)",
        flags=re.IGNORECASE
    )

    for line in lines:
        if not line:
            merged.append("")
            continue

        if heading_pattern.match(line):
            merged.append(line)
            continue

        if not merged:
            merged.append(line)
            continue

        prev = merged[-1]
        if (
            prev
            and not prev.endswith((".", ":", ";", "?", "!"))
            and not heading_pattern.match(line)
        ):
            merged[-1] = prev + " " + line
        else:
            merged.append(line)

    text = "\n".join(merged)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_front_matter_page(text: str, doc_type: str) -> bool:
    t = (text or "").lower().strip()
    wc = word_count(t)

    if wc < MIN_MEANINGFUL_WORDS_PER_PAGE:
        return True

    common_front = [
        "lembar pengesahan",
        "kata pengantar",
        "daftar isi",
        "daftar tabel",
        "daftar gambar",
        "halaman sampul",
    ]

    if any(x in t for x in common_front):
        if "bab i" not in t and "pasal 1" not in t:
            return True

    if doc_type == "kurikulum":
        if "tim penyusun kurikulum" in t or "dokumen kurikulum program studi" in t:
            return True

    return False


def page_has_substantive_start(text: str, doc_type: str) -> bool:
    t = (text or "").lower()

    if doc_type == "kurikulum":
        return "bab i identitas program studi" in t

    if doc_type == "peraturan_akademik":
        return ("bab i ketentuan umum" in t) or ("pasal 1" in t)

    if doc_type == "peraturan_rektor":
        return ("bab i ketentuan umum" in t) or ("pasal 1" in t)

    return False


def trim_document_front_matter(cleaned_pages: List[Dict], doc_type: str) -> List[Dict]:
    """
    Buang halaman awal sampai ketemu bagian isi utama.
    """
    if not cleaned_pages:
        return []

    start_idx = 0
    found = False

    for idx, item in enumerate(cleaned_pages):
        text = item.get("cleaned_text", "")
        if page_has_substantive_start(text, doc_type):
            start_idx = idx
            found = True
            break

    if found:
        return cleaned_pages[start_idx:]

    # fallback: kalau tidak ketemu, pakai hasil yang sudah ada
    return cleaned_pages


def extract_structure_metadata(text: str) -> Dict:
    chapter_title = None
    section_title = None
    subsection_title = None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines[:30]:
        if re.match(r"^BAB\s+[IVXLCDM]+", line, flags=re.IGNORECASE):
            chapter_title = line
            break

    for line in lines[:30]:
        if re.match(r"^Pasal\s+\d+", line, flags=re.IGNORECASE):
            section_title = line
            break

    for line in lines[:30]:
        if re.match(r"^\d+\.\d+\.?", line):
            subsection_title = line
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

    # buang sisa halaman yang full daftar isi/tabel
    lower = text.lower()
    if (
        "daftar isi" in lower
        or "daftar tabel" in lower
        or "daftar gambar" in lower
    ):
        if "bab i" not in lower and "pasal 1" not in lower:
            return ""

    return text.strip()


def clean_document_pages(pages: List[Dict], doc_type: str) -> List[Dict]:
    cleaned_pages = []

    for item in pages:
        raw_text = item.get("text", "")
        cleaned_text = clean_page_text(raw_text, doc_type=doc_type)

        if not cleaned_text:
            continue

        if is_front_matter_page(cleaned_text, doc_type=doc_type):
            continue

        struct_meta = extract_structure_metadata(cleaned_text)

        cleaned_pages.append({
            "page": item["page"],
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "chapter_title": struct_meta["chapter_title"],
            "section_title": struct_meta["section_title"],
            "subsection_title": struct_meta["subsection_title"],
        })

    cleaned_pages = trim_document_front_matter(cleaned_pages, doc_type=doc_type)
    return cleaned_pages


def combine_pages_to_document(cleaned_pages: List[Dict]) -> Tuple[str, List[Dict]]:
    """
    Gabungkan seluruh halaman menjadi satu dokumen, tapi tetap simpan page map.
    """
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