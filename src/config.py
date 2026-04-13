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
        "use_ocr_fallback": False,
    },
    {
        "file_name": "kurikulum_ti_unika.pdf",
        "doc_type": "kurikulum",
        "doc_title": "Kurikulum Program Studi Teknik Informatika",
        "extract_mode": "blocks",
        "use_ocr_fallback": False,
    },
    {
        "file_name": "peraturan_rektor.pdf",
        "doc_type": "peraturan_rektor",
        "doc_title": "Peraturan Rektor",
        "extract_mode": "text",
        "use_ocr_fallback": True,
    },
]

# Ukuran chunk yang lebih aman untuk dokumen regulasi dan kurikulum
CHUNK_SIZE_WORDS = 320
CHUNK_OVERLAP_WORDS = 60
MIN_CHUNK_WORDS = 40

# OCR
# Isi dengan path Tesseract yang benar di Windows kamu
# Contoh:
# TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Kalau language data "ind" ada, pakai "ind+eng"
# Kalau tidak ada, ganti ke "eng"
OCR_LANG = "ind+eng"
OCR_DPI = 250

CHUNK_BLACKLIST_KEYWORDS = [
    "lembar pengesahan",
    "kata pengantar",
    "daftar isi",
    "daftar tabel",
    "daftar gambar",
    "halaman sampul",
    "biodata dosen program studi",
    "penanggung jawab",
    "tanda tangan",
]

FRONT_MATTER_KEYWORDS = [
    "lembar pengesahan",
    "kata pengantar",
    "daftar isi",
    "daftar tabel",
    "daftar gambar",
]

CURRICULUM_END_MARKERS = [
    "BIODATA DOSEN PROGRAM STUDI",
]

MIN_MEANINGFUL_WORDS_PER_PAGE = 12