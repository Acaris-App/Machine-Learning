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
        "extract_mode": "blocks"
    },
    {
        "file_name": "kurikulum_ti_unika.pdf",
        "doc_type": "kurikulum",
        "doc_title": "Kurikulum Program Studi Teknik Informatika",
        "extract_mode": "blocks"
    },
    {
        "file_name": "peraturan_rektor.pdf",
        "doc_type": "peraturan_rektor",
        "doc_title": "Peraturan Rektor",
        "extract_mode": "text"  # fallback lebih aman untuk file ini
    }
]

# Baseline awal
CHUNK_SIZE_WORDS = 400
CHUNK_OVERLAP_WORDS = 80
MIN_CHUNK_WORDS = 40

# Front matter / bagian non-substantif
ENABLE_FRONT_MATTER_FILTER = True

# Kalau chunk mengandung kata-kata ini secara dominan, dibuang
CHUNK_BLACKLIST_KEYWORDS = [
    "lembar pengesahan",
    "kata pengantar",
    "daftar isi",
    "daftar tabel",
    "daftar gambar",
    "halaman sampul",
    "biodata dosen program studi",
]

# Halaman kosong / ornamental
MIN_MEANINGFUL_WORDS_PER_PAGE = 12