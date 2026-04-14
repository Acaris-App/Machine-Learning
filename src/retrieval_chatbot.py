import json
import os
import re
import time
from pathlib import Path
from typing import List, Dict, Tuple

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from google import genai


# =========================
# CONFIG
# =========================

BASE_DIR = Path(__file__).resolve().parent.parent

CHUNK_FILES = [
    BASE_DIR / "output" / "chunked" / "peraturan_akademik_chunks.json",
    BASE_DIR / "output" / "chunked" / "kurikulum_ti_unika_chunks.json",
    BASE_DIR / "output" / "chunked" / "peraturan_rektor_chunks.json",
]

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"
GEMINI_MODEL_NAME = "gemini-2.5-flash"

TOP_K_RETRIEVE = 12
TOP_K_CONTEXT = 4


# =========================
# LOAD CHUNKS
# =========================

def load_chunks(files: List[Path]) -> List[Dict]:
    all_chunks = []

    for file_path in files:
        if not file_path.exists():
            raise FileNotFoundError(f"Chunk file tidak ditemukan: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        chunks = data.get("chunks", [])
        all_chunks.extend(chunks)

    if not all_chunks:
        raise ValueError("Tidak ada chunks yang berhasil dimuat.")

    return all_chunks


# =========================
# TEXT UTILS
# =========================

def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-zA-Z0-9À-ÿ\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    return normalize_text(text).split()


def unique_tokens(text: str) -> set:
    return set(tokenize(text))


def short_text(text: str, max_len: int = 350) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


# =========================
# LIGHT QUERY EXPANSION
# =========================

def expand_query(query: str) -> str:
    """
    Bukan hard rule yang membatasi pertanyaan user.
    Ini cuma menambahkan istilah dekat supaya retrieval lebih presisi.
    """
    q = normalize_text(query)
    expansions = [query]

    related_terms = {
        "sks": ["beban studi", "bobot sks", "jumlah sks", "kurikulum", "mata kuliah"],
        "lulus": ["kelulusan", "syarat lulus", "standar kompetensi lulusan"],
        "semester": ["distribusi mata kuliah", "struktur kurikulum", "mata kuliah semester"],
        "mata kuliah": ["kurikulum", "distribusi semester", "bobot sks"],
        "skripsi": ["tugas akhir", "ujian tugas akhir", "pembimbing", "penguji"],
        "ijazah": ["transkrip akademik", "skpi", "sertifikat kompetensi"],
        "pembimbing akademik": ["pa", "rencana studi", "validasi rs", "monitor perkembangan studi"],
        "krs": ["rencana studi", "rs", "pengambilan mata kuliah", "beban studi"],
    }

    for trigger, extra_terms in related_terms.items():
        if trigger in q:
            expansions.extend(extra_terms)

    # deduplicate
    seen = set()
    clean_parts = []
    for item in expansions:
        norm = normalize_text(item)
        if norm not in seen:
            seen.add(norm)
            clean_parts.append(item)

    return " ".join(clean_parts)


# =========================
# LOAD MODEL + INDEX
# =========================

print("Loading chunks...")
chunks = load_chunks(CHUNK_FILES)
texts = [c["text"] for c in chunks]
print(f"Total chunks loaded: {len(texts)}")

print(f"Loading embedding model: {EMBED_MODEL_NAME}")
embed_model = SentenceTransformer(EMBED_MODEL_NAME)

print("Embedding all chunks...")
embeddings = embed_model.encode(texts, show_progress_bar=True)
embeddings = np.array(embeddings).astype("float32")

dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(embeddings)

print("FAISS index ready!")


# =========================
# GEMINI SETUP
# =========================

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise EnvironmentError(
        'GEMINI_API_KEY belum di-set. Contoh PowerShell: $env:GEMINI_API_KEY="ISI_API_KEY_KAMU"'
    )

client = genai.Client(api_key=api_key)


# =========================
# HYBRID SCORING
# =========================

def lexical_overlap_score(query: str, chunk_text: str) -> float:
    q_tokens = unique_tokens(query)
    c_tokens = unique_tokens(chunk_text)

    if not q_tokens:
        return 0.0

    overlap = q_tokens.intersection(c_tokens)
    return len(overlap) / max(len(q_tokens), 1)


def domain_boost(query: str, item: Dict) -> float:
    """
    Boost ringan berbasis jenis dokumen.
    Tujuannya memperbaiki kasus seperti:
    - pertanyaan SKS/semester/mata kuliah -> kurikulum harus naik
    - pertanyaan ijazah/transkrip -> peraturan_rektor/peraturan_akademik bisa naik
    """
    q = normalize_text(query)
    doc_type = item.get("doc_type", "")
    text = normalize_text(item.get("text", ""))

    boost = 0.0

    if any(k in q for k in ["sks", "semester", "mata kuliah", "kurikulum", "cpl"]):
        if doc_type == "kurikulum":
            boost += 0.25

    if any(k in q for k in ["ijazah", "transkrip", "skpi", "sertifikat"]):
        if doc_type in {"peraturan_akademik", "peraturan_rektor"}:
            boost += 0.15

    if any(k in q for k in ["skripsi", "tugas akhir", "sidang"]):
        if "tugas akhir" in text or "skripsi" in text:
            boost += 0.15

    if any(k in q for k in ["pembimbing akademik", "pa", "rencana studi", "krs"]):
        if "pembimbing akademik" in text or "rencana studi" in text or "rs" in text:
            boost += 0.15

    return boost


def rerank_results(query: str, candidates: List[Dict]) -> List[Dict]:
    reranked = []

    for item in candidates:
        distance = float(item.get("_distance", 9999.0))
        semantic_score = 1.0 / (1.0 + distance)
        lexical_score = lexical_overlap_score(query, item.get("text", ""))
        boost = domain_boost(query, item)

        final_score = (0.55 * semantic_score) + (0.30 * lexical_score) + boost

        new_item = dict(item)
        new_item["_semantic_score"] = round(semantic_score, 4)
        new_item["_lexical_score"] = round(lexical_score, 4)
        new_item["_boost"] = round(boost, 4)
        new_item["_final_score"] = round(final_score, 4)
        reranked.append(new_item)

    reranked.sort(key=lambda x: x["_final_score"], reverse=True)
    return reranked


# =========================
# SEARCH
# =========================

def search(query: str, top_k: int = TOP_K_RETRIEVE) -> List[Dict]:
    expanded_query = expand_query(query)

    query_vec = embed_model.encode([expanded_query]).astype("float32")
    distances, indices = index.search(query_vec, top_k)

    candidates = []
    for rank, idx in enumerate(indices[0]):
        item = dict(chunks[idx])
        item["_distance"] = float(distances[0][rank])
        candidates.append(item)

    reranked = rerank_results(query, candidates)
    return reranked


# =========================
# CONTEXT BUILDING
# =========================

def build_context(results: List[Dict], top_k_context: int = TOP_K_CONTEXT) -> str:
    selected = results[:top_k_context]
    context_parts = []

    for i, r in enumerate(selected, start=1):
        context_parts.append(
            f"[Sumber {i}]\n"
            f"Dokumen: {r.get('doc_type')}\n"
            f"Bab: {r.get('chapter_title')}\n"
            f"Pasal/Subbagian: {r.get('section_title') or r.get('subsection_title')}\n"
            f"Halaman: {r.get('page_start')} - {r.get('page_end')}\n"
            f"Isi: {r.get('text')}\n"
        )

    return "\n\n".join(context_parts)


# =========================
# GEMINI ANSWER
# =========================

def fallback_answer(query: str, retrieved_results: List[Dict]) -> str:
    """
    Jawaban sederhana kalau Gemini lagi error / 503.
    """
    if not retrieved_results:
        return "Maaf ya, aku belum nemu konteks yang relevan buat jawab pertanyaan kamu."

    best = retrieved_results[0]
    snippet = short_text(best.get("text", ""), 280)

    return (
        "Aku lagi gagal bikin jawaban natural karena model AI-nya lagi sibuk banget.\n\n"
        "Tapi konteks paling relevan yang ketarik saat ini adalah:\n"
        f"- Dokumen: {best.get('doc_type')}\n"
        f"- Bab: {best.get('chapter_title')}\n"
        f"- Pasal/Subbagian: {best.get('section_title') or best.get('subsection_title')}\n"
        f"- Halaman: {best.get('page_start')} - {best.get('page_end')}\n"
        f"- Isi ringkas: {snippet}\n\n"
        "Jadi untuk sementara kamu bisa cek konteks itu dulu ya."
    )


def generate_answer(query: str, retrieved_results: List[Dict], max_retries: int = 3) -> str:
    context = build_context(retrieved_results)

    prompt = f"""
Kamu adalah asisten akademik kampus.

Aturan gaya:
- jawab pakai bahasa Indonesia yang ramah, santai, enak dibaca, dan mudah dipahami mahasiswa
- boleh terasa gaul seperti anak kampus sekarang, tapi tetap sopan
- jangan kasar, jangan sarkastik, jangan menyinggung
- jangan terlalu template
- jangan terlalu formal kaku
- tetap jelas dan langsung ke inti

Aturan isi:
- jawab berdasarkan konteks yang diberikan
- utamakan jawaban langsung dulu di kalimat awal
- kalau konteks tidak cukup untuk memastikan angka/fakta tertentu, bilang jujur bahwa detail angkanya belum terlihat jelas di konteks
- jangan mengarang
- kalau perlu, sebut bahwa jawaban ini berdasarkan dokumen kampus yang ketarik
- kalau pertanyaan mahasiswa bisa ditafsirkan lebih dari satu cara, pilih tafsir yang paling masuk akal dari konteks

Konteks:
{context}

Pertanyaan mahasiswa:
{query}

Berikan jawaban yang terasa seperti chatbot kampus yang ramah dan helpful:
"""

    last_error = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt,
            )
            return response.text.strip()

        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_seconds = 2 ** attempt
                time.sleep(wait_seconds)
            else:
                return fallback_answer(query, retrieved_results)

    return fallback_answer(query, retrieved_results)


# =========================
# DEBUG VIEW
# =========================

def print_retrieval_results(query: str, results: List[Dict], top_n: int = 8) -> None:
    print("\n=== HASIL RETRIEVAL ===")
    print(f"Query: {query}")

    for i, r in enumerate(results[:top_n], start=1):
        print(f"\n--- Rank {i} ---")
        print(f"Doc        : {r.get('doc_type')}")
        print(f"Bab        : {r.get('chapter_title')}")
        print(f"Pasal      : {r.get('section_title')}")
        print(f"Halaman    : {r.get('page_start')} - {r.get('page_end')}")
        print(f"Distance   : {r.get('_distance'):.4f}")
        print(f"Semantic   : {r.get('_semantic_score')}")
        print(f"Lexical    : {r.get('_lexical_score')}")
        print(f"Boost      : {r.get('_boost')}")
        print(f"Final score: {r.get('_final_score')}")
        print(f"Text       : {short_text(r.get('text', ''))}")


# =========================
# MAIN LOOP
# =========================

def main():
    print("\nChatbot retrieval siap.")
    print("Ketik pertanyaan. Ketik 'exit' untuk keluar.\n")

    while True:
        query = input("Tanya: ").strip()

        if query.lower() == "exit":
            print("Selesai.")
            break

        if not query:
            print("Pertanyaan kosong. Coba lagi.\n")
            continue

        retrieved = search(query, top_k=TOP_K_RETRIEVE)

        print_retrieval_results(query, retrieved)

        print("\n=== JAWABAN CHATBOT ===\n")
        answer = generate_answer(query, retrieved)
        print(answer)
        print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()