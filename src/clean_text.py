import re
from typing import List, Dict


def basic_clean(text: str) -> str:
    if not text:
        return ""

    # karakter null / aneh
    text = text.replace("\x00", " ")
    text = text.replace("\uf0b7", "•")
    text = text.replace("\u00a0", " ")

    # gabungkan hyphen line break: akade-\nmik -> akademik
    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

    # hapus spasi/tab berlebih
    text = re.sub(r"[ \t]+", " ", text)

    # rapikan spasi sebelum newline
    text = re.sub(r" +\n", "\n", text)

    # rapikan newline berlebih
    text = re.sub(r"\n{3,}", "\n\n", text)

    # trim tiap baris
    text = "\n".join(line.strip() for line in text.splitlines())

    # hapus baris kosong beruntun
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def remove_common_noise(text: str) -> str:
    """
    Noise umum dokumen formal.
    """
    # hapus nomor halaman tunggal di satu baris
    text = re.sub(r"(?m)^\s*\d+\s*$", "", text)

    # hapus nomor romawi tunggal: i, ii, iii, iv, dst
    text = re.sub(r"(?m)^\s*(?:[ivxlcdm]+)\s*$", "", text, flags=re.IGNORECASE)

    # hapus garis / underscore panjang
    text = re.sub(r"(?m)^[_\-=\s]{5,}$", "", text)

    # rapikan lagi
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def remove_document_headers_footers(text: str, doc_type: str) -> str:
    """
    Hapus header/footer berulang secara hati-hati.
    Sesuaikan regex jika nanti hasil PDF asli berbeda.
    """
    patterns = [
        r"(?im)^universitas .*?$",
        r"(?im)^fakultas .*?$",
        r"(?im)^program studi .*?$",
        r"(?im)^lampiran .*?$",
        r"(?im)^salinan .*?$",
    ]

    # tambahan opsional berdasarkan jenis dokumen
    if doc_type == "peraturan_rektor":
        patterns.extend([
            r"(?im)^peraturan rektor .*?$",
            r"(?im)^rektor .*?$",
        ])

    if doc_type == "peraturan_akademik":
        patterns.extend([
            r"(?im)^peraturan akademik.*?$",
        ])

    if doc_type == "kurikulum":
        patterns.extend([
            r"(?im)^kurikulum.*?$",
        ])

    cleaned = text
    for p in patterns:
        cleaned = re.sub(p, "", cleaned)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def merge_broken_lines(text: str) -> str:
    """
    Gabungkan baris yang terpotong tapi masih satu kalimat.
    Tetap usahakan heading / pasal / poin tidak rusak.
    """
    lines = text.splitlines()
    merged_lines = []

    for i, line in enumerate(lines):
        line = line.strip()

        if not line:
            merged_lines.append("")
            continue

        # jika line tampak seperti heading, pasal, atau poin, biarkan
        if re.match(r"^(BAB\s+[IVXLCDM]+|Pasal\s+\d+|[A-Z][A-Z\s]{4,}|^\(\d+\)|^[a-zA-Z]\.)", line):
            merged_lines.append(line)
            continue

        # jika baris sebelumnya tidak kosong dan line sekarang tampak lanjutan kalimat
        if merged_lines:
            prev = merged_lines[-1]
            if (
                prev
                and not prev.endswith((".", ":", ";", "?", "!"))
                and not re.match(r"^(BAB\s+[IVXLCDM]+|Pasal\s+\d+|^\(\d+\)|^[a-zA-Z]\.)", line)
            ):
                merged_lines[-1] = prev + " " + line
            else:
                merged_lines.append(line)
        else:
            merged_lines.append(line)

    text = "\n".join(merged_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_structure_metadata(text: str):
    """
    Ambil metadata sederhana dari isi halaman:
    - chapter_title
    - section_title (mis. Pasal)
    """
    chapter_title = None
    section_title = None

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines[:10]:
        if re.match(r"^BAB\s+[IVXLCDM]+", line, flags=re.IGNORECASE):
            chapter_title = line
            break

    for line in lines[:15]:
        if re.match(r"^Pasal\s+\d+", line, flags=re.IGNORECASE):
            section_title = line
            break

    return {
        "chapter_title": chapter_title,
        "section_title": section_title
    }


def clean_page_text(text: str, doc_type: str) -> str:
    text = basic_clean(text)
    text = remove_common_noise(text)
    text = remove_document_headers_footers(text, doc_type)
    text = merge_broken_lines(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_document_pages(pages: List[Dict], doc_type: str) -> List[Dict]:
    cleaned_pages = []

    for item in pages:
        raw_text = item.get("text", "")
        cleaned_text = clean_page_text(raw_text, doc_type)
        struct_meta = extract_structure_metadata(cleaned_text)

        cleaned_pages.append({
            "page": item["page"],
            "raw_text": raw_text,
            "cleaned_text": cleaned_text,
            "chapter_title": struct_meta["chapter_title"],
            "section_title": struct_meta["section_title"]
        })

    return cleaned_pages