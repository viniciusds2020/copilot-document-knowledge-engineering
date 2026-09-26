from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Protocol

from .models import Document, KnowledgeItem, KnowledgePack


class JsonCompletionClient(Protocol):
    def complete_json(self, *, system: str, user: str) -> dict: ...


SYSTEM_PROMPT = """You curate corporate knowledge for a chatbot.
Use only the supplied source. Never invent values, dates, rules, links, or citations.
Return valid JSON only. Preserve uncertainty and identify conflicts explicitly."""


def _source_excerpt(markdown: str, limit: int) -> str:
    # Content remains traceable through the page comments written by the pipeline.
    return markdown[:limit]


def _items(payload: dict, document: Document) -> list[KnowledgeItem]:
    items: list[KnowledgeItem] = []
    for raw in payload.get("knowledge_items", []):
        page = raw.get("source_page")
        items.append(
            KnowledgeItem(
                topic=str(raw.get("topic", "Sem categoria")).strip(),
                statement=str(raw.get("statement", "")).strip(),
                kind=str(raw.get("kind", "fact")).strip(),
                exceptions=[str(value) for value in raw.get("exceptions", [])],
                source_document_id=document.id,
                source_document=document.title,
                source_sha256=document.sha256,
                source_page=page if isinstance(page, int) and page > 0 else None,
            )
        )
    return [item for item in items if item.statement]


def extract_document_knowledge(
    document: Document, client: JsonCompletionClient, max_source_chars: int
) -> tuple[str, list[KnowledgeItem], list[str]]:
    payload = client.complete_json(
        system=SYSTEM_PROMPT,
        user=f"""Extract knowledge from this single approved document.
Return exactly this JSON shape:
{{
  "summary": "short, faithful summary",
  "knowledge_items": [
    {{
      "topic": "topic",
      "statement": "atomic, complete statement",
      "kind": "definition|rule|process|exception|deadline|contact|metric|fact",
      "exceptions": ["only explicit exceptions"],
      "source_page": 1
    }}
  ],
  "gaps_or_warnings": ["OCR uncertainty or ambiguity only when present"]
}}

Document title: {document.title}
Document SHA-256: {document.sha256}
Source content:
{_source_excerpt(document.markdown, max_source_chars)}""",
    )
    return (
        str(payload.get("summary", "")).strip(),
        _items(payload, document),
        [str(value) for value in payload.get("gaps_or_warnings", [])],
    )


def render_markdown(pack: KnowledgePack) -> str:
    lines = [
        "---",
        f'title: "{pack.domain} — Base Consolidada"',
        f"version: {pack.version}",
        f"status: {pack.status}",
        f"source_documents: {len(pack.source_document_ids)}",
        "---",
        "",
        "# Resumo executivo",
        pack.summary,
        "",
        "# Conhecimento consolidado",
    ]
    for item in pack.knowledge_items:
        evidence = item.source_document
        if item.source_page:
            evidence += f", página {item.source_page}"
        lines.extend([f"## {item.topic}", item.statement, f"_Evidência: {evidence}_"])
        if item.exceptions:
            lines.append("**Exceções:** " + "; ".join(item.exceptions))
        lines.append("")
    if pack.conflicts_or_gaps:
        lines.extend(["# Lacunas e conflitos", *[f"- {value}" for value in pack.conflicts_or_gaps]])
    return "\n".join(lines).strip() + "\n"


def create_knowledge_pack(
    documents: list[Document],
    domain: str,
    version: str,
    client: JsonCompletionClient,
    max_source_chars: int,
) -> KnowledgePack:
    if not documents:
        raise ValueError("Select at least one approved document.")
    rejected = [document.title for document in documents if document.status != "approved"]
    if rejected:
        raise ValueError("Only approved documents can be consolidated: " + ", ".join(rejected))

    extracted = [
        extract_document_knowledge(document, client, max_source_chars)
        for document in documents
    ]
    candidate_items = [item.model_dump() for _, items, _ in extracted for item in items]
    source_summaries = [
        {"title": document.title, "sha256": document.sha256, "summary": summary}
        for document, (summary, _, _) in zip(documents, extracted, strict=True)
    ]
    consolidation_request = f"""Consolidate the approved document summaries and atomic facts
below into one knowledge base. Merge only semantically identical items.
Do not resolve contradictions. List them in conflicts_or_gaps.
Every output knowledge item must retain source_document_id, source_document,
source_sha256 and source_page exactly as one of its inputs.
Return exactly this JSON shape:
{{
  "summary": "executive summary",
  "knowledge_items": [
    {{
      "topic": "...",
      "statement": "...",
      "kind": "...",
      "exceptions": [],
      "source_document_id": "...",
      "source_document": "...",
      "source_sha256": "...",
      "source_page": 1
    }}
  ],
  "conflicts_or_gaps": ["..."]
}}
Domain: {domain}
Document summaries: {json.dumps(source_summaries, ensure_ascii=False)}
Candidate facts: {json.dumps(candidate_items, ensure_ascii=False)}"""
    payload = client.complete_json(system=SYSTEM_PROMPT, user=consolidation_request)

    items = [KnowledgeItem.model_validate(item) for item in payload.get("knowledge_items", [])]
    warnings = [warning for _, _, values in extracted for warning in values]
    pack = KnowledgePack(
        id=uuid.uuid4().hex[:12],
        domain=domain.strip(),
        version=version.strip(),
        status="draft",
        source_document_ids=[document.id for document in documents],
        summary=str(payload.get("summary", "")).strip(),
        knowledge_items=items,
        conflicts_or_gaps=warnings + [str(value) for value in payload.get("conflicts_or_gaps", [])],
        markdown="",
        created_at=datetime.now(UTC).isoformat(),
    )
    pack.markdown = render_markdown(pack)
    return pack
