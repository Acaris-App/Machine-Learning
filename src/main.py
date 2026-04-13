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
from clean_text import clean_document_pages, combine_pages_to_document
from chunking import chunk_document


def process_one_pdf(pdf_config: dict):
    file_name = pdf_config["file_name"]
    doc_type = pdf_config["doc_type"]
    doc_title = pdf_config["doc_title"]
    extract_mode = pdf_config.get("extract_mode", "blocks")
    use_ocr_fallback = pdf_config.get("use_ocr_fallback", False)

    pdf_path = DATA_DIR / file_name
    if not pdf_path.exists():
        raise FileNotFoundError(f"File tidak ditemukan: {pdf_path}")

    print(f"\n=== Processing: {file_name} ===")

    extracted_pages, used_mode = extract_pdf(
        str(pdf_path),
        mode=extract_mode,
        use_ocr_fallback=use_ocr_fallback,
    )

    extracted_output_path = EXTRACTED_DIR / f"{slugify_filename(file_name)}_raw.json"
    save_json({
        "doc_name": file_name,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "requested_extract_mode": extract_mode,
        "used_extract_mode": used_mode,
        "pages": extracted_pages,
    }, extracted_output_path)

    print(f"[OK] Extracted saved -> {extracted_output_path}")

    cleaned_pages = clean_document_pages(extracted_pages, doc_type=doc_type)

    cleaned_output_path = CLEANED_DIR / f"{slugify_filename(file_name)}_cleaned.json"
    save_json({
        "doc_name": file_name,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "used_extract_mode": used_mode,
        "total_cleaned_pages": len(cleaned_pages),
        "pages": cleaned_pages,
    }, cleaned_output_path)

    print(f"[OK] Cleaned saved -> {cleaned_output_path}")
    print(f"[INFO] Total cleaned pages: {len(cleaned_pages)}")

    full_text, page_map = combine_pages_to_document(cleaned_pages)

    chunks = chunk_document(
        full_text=full_text,
        page_map=page_map,
        doc_name=file_name,
        doc_type=doc_type,
        chunk_size_words=CHUNK_SIZE_WORDS,
        overlap_words=CHUNK_OVERLAP_WORDS,
        min_chunk_words=MIN_CHUNK_WORDS,
    )

    chunked_output_path = CHUNKED_DIR / f"{slugify_filename(file_name)}_chunks.json"
    save_json({
        "doc_name": file_name,
        "doc_type": doc_type,
        "doc_title": doc_title,
        "used_extract_mode": used_mode,
        "chunk_size_words": CHUNK_SIZE_WORDS,
        "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
        "total_chunks": len(chunks),
        "chunks": chunks,
    }, chunked_output_path)

    print(f"[OK] Chunks saved -> {chunked_output_path}")
    print(f"[INFO] Total chunks: {len(chunks)}")

    return {
        "file_name": file_name,
        "doc_type": doc_type,
        "used_extract_mode": used_mode,
        "total_pages": len(extracted_pages),
        "total_cleaned_pages": len(cleaned_pages),
        "total_chunks": len(chunks),
        "extract_output": str(extracted_output_path),
        "clean_output": str(cleaned_output_path),
        "chunk_output": str(chunked_output_path),
    }


def main():
    ensure_dirs(EXTRACTED_DIR, CLEANED_DIR, CHUNKED_DIR, LOGS_DIR)

    summary = []

    for pdf_cfg in tqdm(PDF_FILES, desc="Processing PDFs"):
        try:
            result = process_one_pdf(pdf_cfg)
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