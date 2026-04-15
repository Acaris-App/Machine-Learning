import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from parsers.academic_parser import parse_academic_pdf
from parsers.curriculum_parser import parse_curriculum_pdf
from parsers.rector_ocr_parser import parse_rector_pdf
from parsers.utils import load_env_file


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
ENV_PATH = PROJECT_DIR / ".env"

env_vars = load_env_file(ENV_PATH)

POPPLER_PATH = env_vars.get("POPPLER_PATH", "")
TESSERACT_CMD = env_vars.get("TESSERACT_CMD", "")

OUTPUT_ACADEMIC = str(PROJECT_DIR / "output" / "academic")
OUTPUT_CURRICULUM = str(PROJECT_DIR / "output" / "curriculum")
OUTPUT_RECTOR = str(PROJECT_DIR / "output" / "rector")


app = FastAPI(
    title="ACA Parser Service",
    description="Parser dokumen ACA untuk peraturan akademik, kurikulum, dan peraturan rektor",
    version="1.0.0",
)


class ParseRequest(BaseModel):
    file_path: str
    source_name: str


@app.get("/")
def root() -> Dict[str, str]:
    return {"message": "ACA Parser Service is running"}


@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/parse/academic")
def parse_academic(req: ParseRequest) -> Dict[str, List[Dict[str, Any]]]:
    try:
        if not os.path.exists(req.file_path):
            raise HTTPException(
                status_code=404,
                detail=f"File tidak ditemukan: {req.file_path}",
            )

        documents = parse_academic_pdf(
            file_path=req.file_path,
            source_name=req.source_name,
            output_dir=OUTPUT_ACADEMIC,
        )

        return {"documents": documents}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal parse academic PDF: {str(e)}")


@app.post("/parse/curriculum")
def parse_curriculum(req: ParseRequest) -> Dict[str, List[Dict[str, Any]]]:
    try:
        if not os.path.exists(req.file_path):
            raise HTTPException(
                status_code=404,
                detail=f"File tidak ditemukan: {req.file_path}",
            )

        documents = parse_curriculum_pdf(
            file_path=req.file_path,
            source_name=req.source_name,
            output_dir=OUTPUT_CURRICULUM,
        )

        return {"documents": documents}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal parse curriculum PDF: {str(e)}")


@app.post("/parse/rektor")
def parse_rektor(req: ParseRequest) -> Dict[str, List[Dict[str, Any]]]:
    try:
        if not os.path.exists(req.file_path):
            raise HTTPException(
                status_code=404,
                detail=f"File tidak ditemukan: {req.file_path}",
            )

        documents = parse_rector_pdf(
            file_path=req.file_path,
            source_name=req.source_name,
            output_dir=OUTPUT_RECTOR,
            poppler_path=POPPLER_PATH if POPPLER_PATH else None,
            tesseract_cmd=TESSERACT_CMD if TESSERACT_CMD else None,
        )

        return {"documents": documents}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal parse rektor OCR PDF: {str(e)}")