from datetime import UTC, datetime

import pytest

from knowledge_engineering.curation import create_knowledge_pack
from knowledge_engineering.models import Document


def document():
    return Document(
        id="d1",
        filename="source.md",
        title="Source",
        status="approved",
        sha256="hash1",
        markdown="<!-- source_page: 1 -->\nAn approved policy.",
        pages=1,
        text_coverage=1,
        needs_ocr=False,
        quality_score=1,
        quality_passed=True,
        created_at=datetime.now(UTC).isoformat(),
    )


class MaliciousReference:
    calls = 0

    def complete_json(self, *, system, user):
        self.calls += 1
        if self.calls == 1:
            return {
                "summary": "ok",
                "knowledge_items": [
                    {"topic": "Policy", "statement": "An approved policy.", "source_page": 1}
                ],
            }
        return {
            "summary": "ok",
            "knowledge_items": [
                {
                    "topic": "Policy",
                    "statement": "An approved policy.",
                    "source_document_id": "unknown",
                    "source_document": "Fake",
                    "source_sha256": "wrong",
                    "source_page": 99,
                }
            ],
            "conflicts_or_gaps": [],
        }


def test_rejects_forged_consolidation_source_reference():
    with pytest.raises(ValueError, match="source|evidence|refer"):
        create_knowledge_pack([document()], "Policy", "v1", MaliciousReference(), 1000)
