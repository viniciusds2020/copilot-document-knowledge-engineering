from datetime import UTC, datetime

from knowledge_engineering.models import Document, KnowledgeItem, KnowledgePack
from knowledge_engineering.publishing import build_vector_chunks, write_publication


def document() -> Document:
    return Document(
        id="doc-1",
        filename="manual.pdf",
        title="Manual",
        status="approved",
        sha256="abc",
        markdown=(
            "---\ntitle: Manual\n---\n\n"
            "<!-- source_page: 1 -->\n\n"
            "Primeira regra do documento. Segunda regra do documento."
        ),
        pages=1,
        text_coverage=1,
        needs_ocr=False,
        quality_score=1,
        quality_passed=True,
        created_at=datetime.now(UTC).isoformat(),
    )


def pack() -> KnowledgePack:
    return KnowledgePack(
        id="pack-1",
        domain="PVC Fase 9",
        version="2026.1",
        status="approved",
        source_document_ids=["doc-1"],
        summary="Resumo.",
        knowledge_items=[
            KnowledgeItem(
                topic="Elegibilidade",
                statement="A adesão exige cadastro ativo.",
                kind="rule",
                exceptions=[],
                source_document_id="doc-1",
                source_document="Manual",
                source_sha256="abc",
                source_page=1,
            )
        ],
        conflicts_or_gaps=[],
        markdown="# Base\n\nA adesão exige cadastro ativo.",
        created_at=datetime.now(UTC).isoformat(),
    )


def test_builds_raw_and_curated_vector_chunks():
    chunks = build_vector_chunks(pack(), [document()], raw_chunk_chars=120, raw_chunk_overlap=10)

    assert {chunk.collection for chunk in chunks} == {"raw_chunks", "curated_chunks"}
    assert all(chunk.source_sha256 == "abc" for chunk in chunks)
    assert any(chunk.topic == "Elegibilidade" for chunk in chunks)


def test_writes_publication_artifacts(tmp_path):
    manifest = write_publication(
        pack(),
        [document()],
        export_root=tmp_path,
        raw_chunk_chars=120,
        raw_chunk_overlap=10,
    )

    assert manifest.vector_chunk_count >= 2
    assert (tmp_path / "pvc-fase-9" / "2026-1" / "knowledge_pack.md").exists()
    assert (tmp_path / "pvc-fase-9" / "2026-1" / "knowledge_pack.json").exists()
    assert (tmp_path / "pvc-fase-9" / "2026-1" / "vector_chunks.jsonl").exists()
    assert (tmp_path / "pvc-fase-9" / "2026-1" / "manifest.json").exists()
