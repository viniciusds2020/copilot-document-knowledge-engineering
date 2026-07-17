import hashlib
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

import fitz

from .config import Settings
from .models import Document

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md"}


class PipelineError(ValueError):
    pass


def inspect_content(filename: str, content: bytes, threshold: float) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise PipelineError("Formato não suportado. Use PDF, TXT ou Markdown.")
    if suffix == ".pdf" and not content.startswith(b"%PDF"):
        raise PipelineError("Assinatura PDF inválida.")
    if suffix != ".pdf":
        return {"pages": 1, "coverage": 1.0, "needs_ocr": False}
    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise PipelineError("PDF inválido ou corrompido.") from exc
    pages = len(pdf)
    populated = sum(bool(page.get_text().strip()) for page in pdf)
    coverage = populated / pages if pages else 0.0
    return {"pages": pages, "coverage": coverage, "needs_ocr": coverage < threshold}


def fallback_markdown(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".md"}:
        return content.decode("utf-8", errors="replace").strip()
    pdf = fitz.open(stream=content, filetype="pdf")
    sections = []
    for number, page in enumerate(pdf, 1):
        text = page.get_text().strip()
        page_text = text or "[Página sem texto extraível]"
        sections.append(f"<!-- source_page: {number} -->\n\n{page_text}")
    return "\n\n".join(sections)


def docling_markdown(path: Path) -> str:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise PipelineError("Instale o extra 'document' para usar Docling.") from exc
    return DocumentConverter().convert(path).document.export_to_markdown()


def add_front_matter(title: str, sha256: str, markdown: str, needs_ocr: bool) -> str:
    safe_title = re.sub(r"[\r\n]+", " ", title).strip()
    return (
        "---\n"
        f'title: "{safe_title}"\n'
        f"source_sha256: {sha256}\n"
        f"ocr_required: {str(needs_ocr).lower()}\n"
        "status: draft\n"
        "---\n\n"
        f"{markdown.strip()}\n"
    )


def process(filename: str, content: bytes, config: Settings) -> Document:
    if not content:
        raise PipelineError("Arquivo vazio.")
    if len(content) > config.max_upload_mb * 1024 * 1024:
        raise PipelineError("Arquivo excede o limite configurado.")
    metrics = inspect_content(filename, content, config.ocr_text_coverage_threshold)
    digest = hashlib.sha256(content).hexdigest()
    title = Path(filename).stem.replace("_", " ").replace("-", " ").strip().title()
    document_id = uuid.uuid4().hex[:12]
    upload_dir = config.data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    path = upload_dir / f"{document_id}{Path(filename).suffix.lower()}"
    path.write_bytes(content)
    markdown = docling_markdown(path) if config.converter == "docling" else fallback_markdown(
        filename, content
    )
    curated = add_front_matter(title, digest, markdown, metrics["needs_ocr"])
    nonempty = len(markdown.strip()) >= 40
    score = round(0.45 * metrics["coverage"] + 0.35 * float(nonempty) + 0.20, 3)
    return Document(
        id=document_id,
        filename=Path(filename).name,
        title=title,
        status="draft",
        sha256=digest,
        markdown=curated,
        pages=metrics["pages"],
        text_coverage=metrics["coverage"],
        needs_ocr=metrics["needs_ocr"],
        quality_score=score,
        quality_passed=score >= config.min_quality_score,
        created_at=datetime.now(UTC).isoformat(),
    )
