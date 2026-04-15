import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

from parsers.utils import (
    build_document_item,
    clean_basic_text,
    clean_text,
    deduplicate_texts,
    detect_section_title,
    is_heading,
    merge_enumerated_blocks,
    merge_fragments,
    merge_lines_into_semantic_blocks,
    normalize_table_row,
    save_json,
)


def normalize_table_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def extract_page_text_and_tables(file_path: str) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []

    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            tables = page.extract_tables() or []
            pages.append(
                {
                    "page": page_num,
                    "raw_text": text,
                    "tables": tables,
                }
            )

    return pages


def guess_semester_from_text(text: str) -> str:
    if not text:
        return ""

    lowered = text.lower()
    for i in range(1, 15):
        if f"semester {i}" in lowered:
            return str(i)

    return ""


def page_is_mostly_tabular(cleaned_text: str, tables: List[Any]) -> bool:
    if not tables:
        return False

    lowered = cleaned_text.lower()

    if "identitas program studi" in lowered:
        return True

    if "tabel 11" in lowered and "susunan mata kuliah dan bobot sks" in lowered:
        return True

    return len(tables) >= 1 and len(cleaned_text.split()) < 140


def looks_like_false_heading(block: str) -> bool:
    b = block.strip()
    if not b:
        return False

    if b.startswith(("BAB ", "Pasal ", "Bagian ", "Paragraf ")):
        return False

    if re.match(r"^\d+\.\d+", b):
        return False

    # kalimat naratif panjang jangan dianggap heading
    if len(b.split()) > 8:
        return True

    # heading all caps pendek boleh
    if b.isupper() and len(b.split()) <= 8:
        return False

    # poin enumerasi biasa bukan heading
    if re.match(r"^\d+\.\s+", b):
        return True

    return False


def map_curriculum_row(header: List[str], row: List[str]) -> Dict[str, str]:
    mapped: Dict[str, str] = {}

    normalized_header = [normalize_table_cell(h).lower() for h in header]
    normalized_row = [normalize_table_cell(r) for r in row]

    for i, col_name in enumerate(normalized_header):
        cell_value = normalized_row[i] if i < len(normalized_row) else ""

        if "semester" in col_name:
            mapped["semester"] = cell_value
        elif "kode" in col_name:
            mapped["kode_mk"] = cell_value
        elif (
            "mata kuliah" in col_name
            or "nama mk" in col_name
            or "nama matakuliah" in col_name
            or col_name == "mk"
        ):
            mapped["nama_mk"] = cell_value
        elif "sks" in col_name:
            mapped["sks"] = cell_value
        elif "jenis" in col_name or "kategori" in col_name:
            mapped["jenis"] = cell_value
        elif "prasyarat" in col_name:
            mapped["prasyarat"] = cell_value

    return mapped


def is_course_row(mapped: Dict[str, str]) -> bool:
    return bool(mapped.get("kode_mk") or mapped.get("nama_mk") or mapped.get("sks"))


def row_to_sentence(mapped: Dict[str, str], row_values: List[str], fallback_semester: str = "") -> str:
    semester = mapped.get("semester", "") or fallback_semester
    kode_mk = mapped.get("kode_mk", "")
    nama_mk = mapped.get("nama_mk", "")
    sks = mapped.get("sks", "")
    jenis = mapped.get("jenis", "")
    prasyarat = mapped.get("prasyarat", "")

    if is_course_row(mapped):
        parts: List[str] = []
        if semester:
            parts.append(f"Semester {semester}")
        if kode_mk:
            parts.append(f"kode mata kuliah {kode_mk}")
        if nama_mk:
            parts.append(f"nama mata kuliah {nama_mk}")
        if sks:
            parts.append(f"{sks} SKS")
        if jenis:
            parts.append(f"jenis {jenis}")
        if prasyarat:
            parts.append(f"prasyarat {prasyarat}")

        sentence = ", ".join(parts).strip()
        if sentence:
            sentence += "."
        return sentence

    values = [v for v in row_values if v]
    if len(values) >= 3:
        raw = " | ".join(values[:3])
        return normalize_table_row(raw)
    if len(values) >= 2:
        return " | ".join(values)
    return ""


def is_table_11_section(text: str) -> bool:
    lowered = text.lower()
    return "tabel 11" in lowered and "susunan mata kuliah dan bobot sks" in lowered


def extract_table11_header_semesters(lines: List[str]) -> List[int]:
    """
    Cari header:
    No Kode MK Nama Mata Kuliah SKS 1 2 3 4 5 6 7 8
    """
    joined = " ".join(lines)
    match = re.search(
        r"no\s+kode\s+mk\s+nama\s+mata\s+kuliah\s+sks\s+1\s+2\s+3\s+4\s+5\s+6\s+7\s+8",
        joined,
        flags=re.IGNORECASE,
    )
    if match:
        return [1, 2, 3, 4, 5, 6, 7, 8]
    return []


def parse_table11_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Parse baris seperti:
    1 INF625101 Pengenalan Pemrograman 2 x
    43 INF625306 Mobile Programming 3 x

    Aturan:
    - token pertama = nomor
    - token kedua = kode MK
    - angka terakhir sebelum deretan x = SKS
    - jumlah x dibaca
    """
    line = clean_text(line)
    if not line:
        return None

    # skip header / judul
    lowered = line.lower()
    if lowered.startswith("tabel 11"):
        return None
    if lowered.startswith("no kode mk nama mata kuliah sks"):
        return None

    # pola utama
    m = re.match(
        r"^(\d+)\s+([A-Z]{2,5}\d{5,10}[A-Z0-9]*)\s+(.+?)\s+(\d+)\s+((?:x\s*)+)$",
        line,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    nomor = m.group(1).strip()
    kode_mk = m.group(2).strip()
    nama_mk = m.group(3).strip()
    sks = m.group(4).strip()
    raw_marks = m.group(5).strip()

    x_count = len(re.findall(r"\bx\b", raw_marks, flags=re.IGNORECASE))

    return {
        "row_number": nomor,
        "kode_mk": kode_mk,
        "nama_mk": nama_mk,
        "sks": sks,
        "raw_marks": raw_marks,
        "x_count": x_count,
        "semester": "",  # diisi nanti
    }


def infer_table11_semester(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Heuristik praktis:
    untuk tabel susunan mata kuliah, umumnya 1 baris mata kuliah punya satu x
    dan urutannya di PDF berjalan per semester.

    Strategi aman:
    - gunakan perubahan nomor baris dan blok semantik bila tersedia
    - fallback: kalau x_count == 1 tapi semester tidak bisa diinfer dengan presisi layout,
      semester tetap kosong namun content tetap informatif

    CATATAN:
    untuk presisi 100%, idealnya baca posisi kolom x dari koordinat PDF.
    """
    # Versi aman: belum memaksakan semester kalau posisi kolom tidak terpercaya.
    return rows


def build_table11_sentence(row: Dict[str, Any]) -> str:
    semester = row.get("semester", "")
    kode_mk = row.get("kode_mk", "")
    nama_mk = row.get("nama_mk", "")
    sks = row.get("sks", "")
    x_count = row.get("x_count", 0)

    if semester:
        return f"Semester {semester}, kode mata kuliah {kode_mk}, nama mata kuliah {nama_mk}, {sks} SKS."
    return (
        f"Kode mata kuliah {kode_mk}, nama mata kuliah {nama_mk}, {sks} SKS, "
        f"dengan penanda semester sebanyak {x_count} tanda x pada tabel distribusi semester."
    )


def parse_curriculum_pdf(
    file_path: str,
    source_name: str,
    output_dir: str,
) -> List[Dict[str, Any]]:
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {file_path}")

    pages = extract_page_text_and_tables(file_path)

    documents: List[Dict[str, Any]] = []
    current_section_title = ""

    inside_table11 = False
    table11_rows_buffer: List[Dict[str, Any]] = []

    for page_data in pages:
        page_num = page_data["page"]
        raw_text = page_data["raw_text"]
        tables = page_data["tables"]

        cleaned_text = clean_basic_text(raw_text)
        fallback_semester = guess_semester_from_text(cleaned_text)

        if is_table_11_section(cleaned_text):
            inside_table11 = True

        if inside_table11:
            lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]

            # simpan heading tabel 11
            for line in lines:
                if "tabel 11" in line.lower() and "susunan mata kuliah dan bobot sks" in line.lower():
                    documents.append(
                        build_document_item(
                            source_name=source_name,
                            document_type="kurikulum",
                            page=page_num,
                            section_title="Tabel 11 Susunan Mata Kuliah dan Bobot SKS",
                            content_type="section_heading",
                            content=line,
                            extra_metadata={},
                        )
                    )

            semester_columns = extract_table11_header_semesters(lines)
            if semester_columns:
                documents.append(
                    build_document_item(
                        source_name=source_name,
                        document_type="kurikulum",
                        page=page_num,
                        section_title="Tabel 11 Susunan Mata Kuliah dan Bobot SKS",
                        content_type="table_header",
                        content="No | Kode MK | Nama Mata Kuliah | SKS | Semester 1 | Semester 2 | Semester 3 | Semester 4 | Semester 5 | Semester 6 | Semester 7 | Semester 8",
                        extra_metadata={
                            "semester_columns": semester_columns,
                        },
                    )
                )

            for line in lines:
                parsed = parse_table11_line(line)
                if parsed:
                    parsed["page"] = page_num
                    table11_rows_buffer.append(parsed)

            # stop mode table11 kalau sudah masuk bab besar berikutnya
            lowered = cleaned_text.lower()
            if "bab viii" in lowered or "bab ix" in lowered or "penutup" in lowered:
                inside_table11 = False

            continue

        mostly_tabular = page_is_mostly_tabular(cleaned_text, tables)

        if cleaned_text and not mostly_tabular:
            lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]
            blocks = merge_lines_into_semantic_blocks(lines)
            blocks = merge_enumerated_blocks(blocks)
            blocks = merge_fragments(blocks)
            blocks = deduplicate_texts(blocks)

            i = 0
            while i < len(blocks):
                block = blocks[i]

                if (
                    re.match(r"^\d+\.\s+", block)
                    and i + 1 < len(blocks)
                    and not is_heading(blocks[i + 1])
                    and not re.match(r"^\d+\.\s+", blocks[i + 1])
                ):
                    block = f"{block} {blocks[i + 1]}".strip()
                    i += 1

                detected_title = detect_section_title(block)

                if detected_title and not looks_like_false_heading(block):
                    current_section_title = detected_title
                    content_type = "section_heading"
                else:
                    content_type = "narrative_paragraph"

                if len(block.strip()) >= 5:
                    documents.append(
                        build_document_item(
                            source_name=source_name,
                            document_type="kurikulum",
                            page=page_num,
                            section_title=current_section_title,
                            content_type=content_type,
                            content=block,
                            extra_metadata={},
                        )
                    )

                i += 1

        elif cleaned_text and mostly_tabular:
            lines = [line.strip() for line in cleaned_text.split("\n") if line.strip()]
            for line in lines[:5]:
                detected_title = detect_section_title(line)
                if detected_title and not looks_like_false_heading(line):
                    current_section_title = detected_title
                    documents.append(
                        build_document_item(
                            source_name=source_name,
                            document_type="kurikulum",
                            page=page_num,
                            section_title=current_section_title,
                            content_type="section_heading",
                            content=line,
                            extra_metadata={},
                        )
                    )

        # parser tabel umum biasa
        for table_index, table in enumerate(tables, start=1):
            if not table or len(table) < 2:
                continue

            header = [normalize_table_cell(h) for h in table[0]]
            rows = table[1:]

            row_count = 0
            for row in rows:
                if not row:
                    continue

                normalized_row = [normalize_table_cell(cell) for cell in row]
                if not any(normalized_row):
                    continue

                mapped = map_curriculum_row(header, normalized_row)
                sentence = row_to_sentence(mapped, normalized_row, fallback_semester=fallback_semester)

                if not sentence:
                    continue

                row_count += 1

                documents.append(
                    build_document_item(
                        source_name=source_name,
                        document_type="kurikulum",
                        page=page_num,
                        section_title=current_section_title,
                        content_type="table_row",
                        content=sentence,
                        extra_metadata={
                            "table_index": table_index,
                            "row_index": row_count,
                            "semester": mapped.get("semester", "") or fallback_semester,
                            "kode_mk": mapped.get("kode_mk", ""),
                            "nama_mk": mapped.get("nama_mk", ""),
                            "sks": mapped.get("sks", ""),
                            "jenis": mapped.get("jenis", ""),
                            "prasyarat": mapped.get("prasyarat", ""),
                        },
                    )
                )

            if row_count > 0:
                documents.append(
                    build_document_item(
                        source_name=source_name,
                        document_type="kurikulum",
                        page=page_num,
                        section_title=current_section_title,
                        content_type="table_summary",
                        content=f"Tabel ke-{table_index} pada halaman {page_num} berhasil diekstrak dari dokumen kurikulum.",
                        extra_metadata={"table_index": table_index},
                    )
                )

    # flush Tabel 11
    table11_rows_buffer = infer_table11_semester(table11_rows_buffer)
    for row in table11_rows_buffer:
        documents.append(
            build_document_item(
                source_name=source_name,
                document_type="kurikulum",
                page=row["page"],
                section_title="Tabel 11 Susunan Mata Kuliah dan Bobot SKS",
                content_type="course_row",
                content=build_table11_sentence(row),
                extra_metadata={
                    "row_number": row.get("row_number", ""),
                    "semester": row.get("semester", ""),
                    "kode_mk": row.get("kode_mk", ""),
                    "nama_mk": row.get("nama_mk", ""),
                    "sks": row.get("sks", ""),
                    "x_count": row.get("x_count", 0),
                    "raw_marks": row.get("raw_marks", ""),
                },
            )
        )

    output_path = Path(output_dir) / f"{source_name}_parsed.json"
    save_json(output_path, {"documents": documents})
    return documents