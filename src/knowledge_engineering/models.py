from typing import Literal

from pydantic import BaseModel

Status = Literal["draft", "review", "approved", "deprecated"]


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
