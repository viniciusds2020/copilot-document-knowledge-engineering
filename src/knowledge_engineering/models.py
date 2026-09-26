from typing import Literal

from pydantic import BaseModel, Field

Status = Literal["draft", "review", "approved", "deprecated"]
PackStatus = Literal["draft", "review", "approved", "deprecated"]


class StatusUpdate(BaseModel):
    status: Status


class Document(BaseModel):
    id: str
    filename: str
    title: str
    status: Status
    sha256: str
    markdown: str
    pages: int
    text_coverage: float
    needs_ocr: bool
    quality_score: float
    quality_passed: bool
    created_at: str


class KnowledgeItem(BaseModel):
    topic: str
    statement: str
    kind: str = "fact"
    exceptions: list[str] = Field(default_factory=list)
    source_document_id: str
    source_document: str
    source_sha256: str
    source_page: int | None = None


class KnowledgePackRequest(BaseModel):
    document_ids: list[str] = Field(min_length=1)
    domain: str = Field(min_length=2, max_length=100)
    version: str = Field(min_length=1, max_length=40)


class KnowledgePack(BaseModel):
    id: str
    domain: str
    version: str
    status: PackStatus
    source_document_ids: list[str]
    summary: str
    knowledge_items: list[KnowledgeItem] = Field(default_factory=list)
    conflicts_or_gaps: list[str] = Field(default_factory=list)
    markdown: str
    created_at: str
