import fitz
import pytest

from knowledge_engineering.config import Settings
from knowledge_engineering.pipeline import PipelineError, inspect_content, process


def make_pdf(text="Política corporativa válida e aprovada para todos os colaboradores."):
    pdf = fitz.open()
    page = pdf.new_page()
    if text:
        page.insert_text((72, 72), text)
    return pdf.tobytes()


def test_native_pdf_does_not_require_ocr():
    result = inspect_content("policy.pdf", make_pdf(), 0.7)
    assert result == {"pages": 1, "coverage": 1.0, "needs_ocr": False}


def test_image_only_pdf_requires_ocr():
    result = inspect_content("scan.pdf", make_pdf(""), 0.7)
    assert result["needs_ocr"] is True


def test_process_adds_traceability(tmp_path):
    config = Settings(data_dir=tmp_path, min_quality_score=0.7)
    document = process("politica.pdf", make_pdf(), config)
    assert "source_sha256:" in document.markdown
    assert "source_page: 1" in document.markdown
    assert document.quality_passed


def test_rejects_fake_pdf():
    with pytest.raises(PipelineError, match="Assinatura"):
        inspect_content("fake.pdf", b"not a pdf", 0.7)
