from datetime import UTC, datetime

import pytest

from knowledge_engineering.curation import create_knowledge_pack
from knowledge_engineering.models import Document


class FakeGroq:
    def __init__(self):
        self.calls = 0

    def complete_json(self, *, system: str, user: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            return {
                "summary": "Regra de exemplo.",
                "knowledge_items": [
                    {
                        "topic": "Elegibilidade",
                        "statement": "A adesão exige cadastro ativo.",
                        "kind": "rule",
                        "exceptions": [],
                        "source_page": 2,
                    }
                ],
                "gaps_or_warnings": [],
            }
        return {
            "summary": "Base consolidada de elegibilidade.",
            "knowledge_items": [
                {
                    "topic": "Elegibilidade",
                    "statement": "A adesão exige cadastro ativo.",
                    "kind": "rule",
                    "exceptions": [],
                    "source_document_id": "doc-1",
                    "source_document": "Regulamento",
                    "source_sha256": "abc",
                    "source_page": 2,
                }
            ],
            "conflicts_or_gaps": [],
        }


def approved_document() -> Document:
    return Document(
        id="doc-1",
        filename="regulamento.pdf",
        title="Regulamento",
        status="approved",
        sha256="abc",
        markdown="<!-- source_page: 2 -->\n\nA adesão exige cadastro ativo.",
        pages=2,
        text_coverage=1,
        needs_ocr=False,
        quality_score=1,
        quality_passed=True,
        created_at=datetime.now(UTC).isoformat(),
    )


def test_creates_a_traceable_knowledge_pack():
    pack = create_knowledge_pack(
        [approved_document()], "PVC", "1.0.0", FakeGroq(), max_source_chars=1000
    )

    assert pack.domain == "PVC"
    assert pack.knowledge_items[0].source_page == 2
    assert "Evidência: Regulamento, página 2" in pack.markdown


def test_rejects_non_approved_documents():
    document = approved_document()
    document.status = "review"

    with pytest.raises(ValueError, match="Only approved"):
        create_knowledge_pack([document], "PVC", "1.0.0", FakeGroq(), 1000)
