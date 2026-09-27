from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from pathlib import Path

from .models import Document, KnowledgePack, PublicationManifest, VectorChunk


PAGE_MARKER = re.compile(r"<!--\s*source_page:\s*(\d+)\s*-->")


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return normalized.strip("-") or "knowledge-pack"


def _page_sections(markdown: str) -> list[tuple[int | None, str]]:
    matches = list(PAGE_MARKER.finditer(markdown))
    if not matches:
        return [(None, markdown.strip())] if markdown.strip() else []

    sections: list[tuple[int | None, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        text = markdown[start:end].strip()
        if text:
            sections.append((int(match.group(1)), text))
    return sections


def _split_text(text: str, *, max_chars: int, overlap: int) -> list[str]:
    compact = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not compact:
        return []
    if len(compact) <= max_chars:
        return [compact]

    chunks = []
    start = 0
    while start < len(compact):
        end = min(start + max_chars, len(compact))
        boundary = compact.rfind("\n\n", start, end)
        if boundary <= start + max_chars // 2:
            boundary = compact.rfind(". ", start, end)
        if boundary <= start:
            boundary = end
        chunk = compact[start:boundary].strip()
        if chunk:
            chunks.append(chunk)
        if boundary >= len(compact):
            break
        start = max(boundary - overlap, 0)
        if start == boundary:
            start = boundary
    return chunks


def build_raw_chunks(
    pack: KnowledgePack,
    documents: list[Document],
    *,
    max_chars: int,
    overlap: int,
) -> list[VectorChunk]:
    chunks: list[VectorChunk] = []
    for document in documents:
        for page, page_text in _page_sections(document.markdown):
            for offset, text in enumerate(
                _split_text(page_text, max_chars=max_chars, overlap=overlap), 1
            ):
                chunks.append(
                    VectorChunk(
                        id=uuid.uuid4().hex,
                        collection="raw_chunks",
                        domain=pack.domain,
                        version=pack.version,
                        pack_id=pack.id,
                        source_document_id=document.id,
                        source_document=document.title,
                        source_sha256=document.sha256,
                        source_page=page,
                        topic=document.title,
                        text=text,
                        metadata={
                            "chunk_offset": offset,
                            "filename": document.filename,
                            "quality_score": document.quality_score,
                        },
                    )
                )
    return chunks


def build_curated_chunks(pack: KnowledgePack) -> list[VectorChunk]:
    chunks: list[VectorChunk] = []
    for item in pack.knowledge_items:
        exceptions = ""
        if item.exceptions:
            exceptions = "\nExceções: " + "; ".join(item.exceptions)
        chunks.append(
            VectorChunk(
                id=uuid.uuid4().hex,
                collection="curated_chunks",
                domain=pack.domain,
                version=pack.version,
                pack_id=pack.id,
                source_document_id=item.source_document_id,
                source_document=item.source_document,
                source_sha256=item.source_sha256,
                source_page=item.source_page,
                topic=item.topic,
                text=f"{item.statement}{exceptions}",
                metadata={"kind": item.kind},
            )
        )
    return chunks


def build_vector_chunks(
    pack: KnowledgePack,
    documents: list[Document],
    *,
    raw_chunk_chars: int,
    raw_chunk_overlap: int,
) -> list[VectorChunk]:
    return [
        *build_curated_chunks(pack),
        *build_raw_chunks(
            pack,
            documents,
            max_chars=raw_chunk_chars,
            overlap=raw_chunk_overlap,
        ),
    ]


def write_publication(
    pack: KnowledgePack,
    documents: list[Document],
    *,
    export_root: Path,
    raw_chunk_chars: int,
    raw_chunk_overlap: int,
) -> PublicationManifest:
    export_dir = export_root / slugify(pack.domain) / slugify(pack.version)
    export_dir.mkdir(parents=True, exist_ok=True)

    chunks = build_vector_chunks(
        pack,
        documents,
        raw_chunk_chars=raw_chunk_chars,
        raw_chunk_overlap=raw_chunk_overlap,
    )
    files = {
        "knowledge_markdown": export_dir / "knowledge_pack.md",
        "knowledge_json": export_dir / "knowledge_pack.json",
        "vector_jsonl": export_dir / "vector_chunks.jsonl",
        "manifest": export_dir / "manifest.json",
    }

    files["knowledge_markdown"].write_text(pack.markdown, encoding="utf-8")
    files["knowledge_json"].write_text(
        pack.model_dump_json(indent=2),
        encoding="utf-8",
    )
    with files["vector_jsonl"].open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(chunk.model_dump_json() + "\n")

    manifest = PublicationManifest(
        pack_id=pack.id,
        domain=pack.domain,
        version=pack.version,
        status=pack.status,
        source_document_ids=pack.source_document_ids,
        export_dir=str(export_dir),
        files={key: str(path) for key, path in files.items()},
        vector_chunk_count=len(chunks),
        curated_chunk_count=sum(chunk.collection == "curated_chunks" for chunk in chunks),
        raw_chunk_count=sum(chunk.collection == "raw_chunks" for chunk in chunks),
        created_at=datetime.now(UTC).isoformat(),
    )
    files["manifest"].write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest
