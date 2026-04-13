import fitz


def extract_pdf_text_mode(pdf_path: str):
    """
    Ekstraksi sederhana per halaman.
    Cocok kalau layout PDF relatif rapi.
    """
    doc = fitz.open(pdf_path)
    pages = []

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append({
            "page": page_num,
            "text": text if text else ""
        })

    return pages


def extract_pdf_blocks_mode(pdf_path: str):
    """
    Ekstraksi berbasis blok.
    Lebih aman untuk dokumen formal yang kadang punya layout kompleks.
    """
    doc = fitz.open(pdf_path)
    pages = []

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("blocks")

        # sort berdasarkan y (atas-bawah), lalu x (kiri-kanan)
        sorted_blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

        texts = []
        for block in sorted_blocks:
            block_text = block[4].strip()
            if block_text:
                texts.append(block_text)

        page_text = "\n".join(texts)

        pages.append({
            "page": page_num,
            "text": page_text
        })

    return pages


def extract_pdf(pdf_path: str, mode: str = "blocks"):
    """
    mode:
    - text
    - blocks
    """
    if mode == "text":
        return extract_pdf_text_mode(pdf_path)
    return extract_pdf_blocks_mode(pdf_path)