from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

EXTRACTED_DIR = OUTPUT_DIR / "extracted"
CLEANED_DIR = OUTPUT_DIR / "cleaned"
CHUNKED_DIR = OUTPUT_DIR / "chunked"
LOGS_DIR = OUTPUT_DIR / "logs"

PDF_FILES = [
    {
        "file_name": "peraturan_akademik.pdf",
        "doc_type": "peraturan_akademik",
        "doc_title": "Peraturan Akademik",
        "extract_mode": "blocks",
        "use_ocr_fallback": False
    },
    {
        "file_name": "kurikulum_ti_unika.pdf",
        "doc_type": "kurikulum",
        "doc_title": "Kurikulum Program Studi Teknik Informatika",
        "extract_mode": "blocks",
        "use_ocr_fallback": False
    },
    {
        "file_name": "peraturan_rektor.pdf",
        "doc_type": "peraturan_rektor",
        "doc_title": "Peraturan Rektor",
        "extract_mode": "text",
        "use_ocr_fallback": True
    }
]

CHUNK_SIZE_WORDS = 350
CHUNK_OVERLAP_WORDS = 60
MIN_CHUNK_WORDS = 40

CHUNK_BLACKLIST_KEYWORDS = [
    "lembar pengesahan",
    "kata pengantar",
    "daftar isi",
    "daftar tabel",
    "daftar gambar",
    "halaman sampul",
    "tanda tangan",
    "penanggung jawab",
    "biodata dosen program studi",
]

MIN_MEANINGFUL_WORDS_PER_PAGE = 12
OCR_LANG = "ind+eng"
OCR_DPI = 220