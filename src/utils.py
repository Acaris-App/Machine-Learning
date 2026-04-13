import json
from pathlib import Path


def ensure_dirs(*dirs):
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)


def save_json(data, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def slugify_filename(name: str) -> str:
    return (
        name.lower()
        .replace(".pdf", "")
        .replace(" ", "_")
        .replace("-", "_")
    )


def safe_preview(text: str, max_len: int = 220) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."