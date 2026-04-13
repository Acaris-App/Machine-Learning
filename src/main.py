from pathlib import Path
from tqdm import tqdm

from config import (
    DATA_DIR,
    EXTRACTED_DIR,
    CLEANED_DIR,
    CHUNKED_DIR,
    LOGS_DIR,
    PDF_FILES,
    CHUNK_SIZE_WORDS,
    CHUNK_OVERLAP_WORDS,
    MIN_CHUNK_WORDS,
)
from utils import ensure_dirs, save_json, slugify_filename
from extract_pdf import extract_pdf
from clean_text import clean_document_pages
from chunking import chunk_document_pages


def process_one_pdf(pdf_config: dict, extract_mode: str = "blocks"):
    file_name = pdf_config["file_name"]
    doc_type = pdf_config["doc_type"]
    doc_title = pdf_config["doc_title"]

    pdf_path = DATA_DIR / file_name
    if not pdf_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {pdf_path}")

    print(f"\n=== Processing: {file_name} ===")

    # 1. Extract
    extracted_pages = extract_pdf(str(pdf_path), mode=extract_mode)

    extracted_output_path = EXTRACTED_DIR / f"{slugify_filename(file_name)}_raw.json"
    save_json({
        "doc_name": file_name,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "extract_mode": extract_mode,
        "pages": extracted_pages
    }, extracted_output_path)

    print(f"[OK] Extracted saved -> {extracted_output_path}")

    # 2. Clean
    cleaned_pages = clean_document_pages(extracted_pages, doc_type=doc_type)

    cleaned_output_path = CLEANED_DIR / f"{slugify_filename(file_name)}_cleaned.json"
    save_json({
        "doc_name": file_name,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "pages": cleaned_pages
    }, cleaned_output_path)

    print(f"[OK] Cleaned saved -> {cleaned_output_path}")

    # 3. Chunk
    chunks = chunk_document_pages(
        cleaned_pages=cleaned_pages,
        doc_name=file_name,
        doc_type=doc_type,
        chunk_size_words=CHUNK_SIZE_WORDS,
        overlap_words=CHUNK_OVERLAP_WORDS,
        min_chunk_words=MIN_CHUNK_WORDS
    )

    chunked_output_path = CHUNKED_DIR / f"{slugify_filename(file_name)}_chunks.json"
    save_json({
        "doc_name": file_name,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "chunk_size_words": CHUNK_SIZE_WORDS,
        "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
        "total_chunks": len(chunks),
        "chunks": chunks
    }, chunked_output_path)

    print(f"[OK] Chunks saved -> {chunked_output_path}")
    print(f"[INFO] Total chunks: {len(chunks)}")

    return {
        "file_name": file_name,
        "doc_type": doc_type,
        "total_pages": len(extracted_pages),
        "total_chunks": len(chunks),
        "extract_output": str(extracted_output_path),
        "clean_output": str(cleaned_output_path),
        "chunk_output": str(chunked_output_path)
    }


def main():
    ensure_dirs(EXTRACTED_DIR, CLEANED_DIR, CHUNKED_DIR, LOGS_DIR)

    summary = []

    for pdf_cfg in tqdm(PDF_FILES, desc="Processing PDFs"):
        try:
            result = process_one_pdf(pdf_cfg, extract_mode="blocks")
            summary.append({
                "status": "success",
                **result
            })
        except Exception as e:
            summary.append({
                "status": "failed",
                "file_name": pdf_cfg["file_name"],
                "doc_type": pdf_cfg["doc_type"],
                "error": str(e)
            })
            print(f"[ERROR] {pdf_cfg['file_name']} -> {e}")

    summary_path = LOGS_DIR / "processing_summary.json"
    save_json(summary, summary_path)

    print("\n=== DONE ===")
    print(f"Summary saved -> {summary_path}")


if __name__ == "__main__":
    main()