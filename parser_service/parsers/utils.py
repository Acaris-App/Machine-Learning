import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def ensure_dir(path: str | Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def save_json(output_path: str | Path, data: Any) -> None:
    output_path = Path(output_path)
    ensure_dir(output_path.parent)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def clean_text(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    text = text.replace("￾", "-")
    return text


def clean_basic_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = text.replace("￾", "-")

    # rapikan spasi
    text = re.sub(r"[ \t]+", " ", text)

    # buang nomor halaman tunggal
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"\d+", stripped):
            continue
        if re.fullmatch(r"halaman\s+\d+", stripped.lower()):
            continue
        if re.fullmatch(r"page\s+\d+", stripped.lower()):
            continue
        lines.append(stripped)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def is_heading(text: str) -> bool:
    text = text.strip()
    if not text:
        return False

    # heading kuat
    if re.match(r"^BAB\s+[IVXLC0-9]+$", text, flags=re.IGNORECASE):
        return True
    if re.match(r"^BAB\s+[IVXLC0-9]+\b.*$", text, flags=re.IGNORECASE):
        return True
    if re.match(r"^Pasal\s+\d+[A-Za-z]?$", text, flags=re.IGNORECASE):
        return True
    if re.match(r"^\d+\.\d+", text):
        return True

    # huruf besar pendek
    if text.isupper() and len(text.split()) <= 8:
        return True

    return False


def detect_section_title(text: str) -> str:
    text = text.strip()
    if is_heading(text):
        return text
    return ""


def is_noise(text: str) -> bool:
    noise_patterns = [
        r"^\d+\s*>\s*",
        r"net\s*:",
        r"Tambahan Lembaran Negara",
        r"Lembaran Negara Republik Indonesia",
    ]

    for pattern in noise_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    return False


def merge_fragments(lines: List[str]) -> List[str]:
    """
    Gabung kalimat yang kepotong.
    """
    merged: List[str] = []
    buffer = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if buffer == "":
            buffer = line
            continue

        if (
            not buffer.endswith((".", ";", ":", "?", "!"))
            or buffer.endswith(("tentang", "sebagaimana", "dan", "atau", "yang", "dengan"))
        ):
            buffer += " " + line
        else:
            merged.append(buffer)
            buffer = line

    if buffer:
        merged.append(buffer)

    return merged


def merge_lines_into_semantic_blocks(lines: List[str]) -> List[str]:
    cleaned = [clean_text(l) for l in lines if clean_text(l)]
    if not cleaned:
        return []

    blocks: List[str] = []
    current = ""

    for line in cleaned:
        if is_heading(line):
            if current.strip():
                blocks.append(current.strip())
                current = ""
            blocks.append(line.strip())
            continue

        if re.match(r"^\(?\d+[.)]?\s+", line):
            if current.strip():
                blocks.append(current.strip())
            current = line
            continue

        if not current:
            current = line
            continue

        if current.endswith((".", ";", ":", "?", "!")):
            blocks.append(current.strip())
            current = line
        else:
            current = f"{current} {line}".strip()

    if current.strip():
        blocks.append(current.strip())

    return [b.strip() for b in blocks if b.strip()]


def merge_enumerated_blocks(blocks: List[str]) -> List[str]:
    if not blocks:
        return []

    merged: List[str] = []
    i = 0

    while i < len(blocks):
        current = blocks[i].strip()

        if i + 1 < len(blocks):
            nxt = blocks[i + 1].strip()

            current_is_enum = bool(re.match(r"^(\(?\d+[.)])\s+", current))
            next_is_new_enum = bool(re.match(r"^(\(?\d+[.)])\s+", nxt))

            if current_is_enum and not next_is_new_enum and not is_heading(nxt):
                current = f"{current} {nxt}".strip()
                i += 1

        merged.append(current)
        i += 1

    return merged


def deduplicate_texts(texts: List[str]) -> List[str]:
    seen = set()
    result = []

    for t in texts:
        key = re.sub(r"\s+", " ", t.strip().lower())
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        result.append(t)

    return result


def normalize_table_row(row: str) -> str:
    """
    Ubah:
    2 | Fakultas | Teknik
    menjadi:
    Fakultas adalah Teknik.
    """
    parts = [p.strip() for p in row.split("|") if p.strip()]
    if len(parts) >= 3:
        return f"{parts[1]} adalah {parts[2]}."
    return row


def build_document_item(
    source_name: str,
    document_type: str,
    page: int,
    content: str,
    section_title: str = "",
    content_type: str = "paragraph",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "source": source_name,
        "document_type": document_type,
    }

    if extra_metadata:
        metadata.update(extra_metadata)

    return {
        "page": page,
        "section_title": section_title,
        "content_type": content_type,
        "content": content,
        "metadata": metadata,
    }