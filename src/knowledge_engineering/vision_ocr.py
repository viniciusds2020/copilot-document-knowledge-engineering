from __future__ import annotations

import base64
import json
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import fitz


class VisionOcrError(RuntimeError):
    pass


class VisionOcrClient(Protocol):
    def extract_page_markdown(self, *, image_png: bytes, page_number: int) -> str:
        """Return faithful Markdown OCR text for a rendered PDF page."""


VISION_OCR_SYSTEM_PROMPT = """You are a strict OCR engine for corporate documents.
Extract only visible text from the provided page image.
Preserve reading order, headings, tables, bullets, numbers, dates and identifiers.
Do not summarize, infer, correct policies, or add explanations.
If a region is unreadable, mark it as [ilegível].
Return Markdown only.
"""


class OpenAIVisionOcrClient:
    """Dependency-free client for OpenAI-compatible multimodal chat endpoints.

    This works with Groq vision models and with other providers that implement
    /chat/completions with image_url message parts, such as DeepSeek-compatible
    OCR gateways when exposed through an OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: int = 90,
        max_tokens: int = 4096,
    ):
        if not api_key:
            raise VisionOcrError("Configure KE_VISION_OCR_API_KEY or KE_GROQ_API_KEY.")
        if not model:
            raise VisionOcrError("Configure KE_VISION_OCR_MODEL for vision OCR.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    def extract_page_markdown(self, *, image_png: bytes, page_number: int) -> str:
        encoded = base64.b64encode(image_png).decode("ascii")
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": VISION_OCR_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"Transcreva fielmente a página {page_number} para Markdown. "
                                "Não resuma e não invente conteúdo."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{encoded}"},
                        },
                    ],
                },
            ],
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise VisionOcrError(f"Vision OCR returned HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise VisionOcrError(f"Could not reach vision OCR endpoint: {exc.reason}") from exc

        try:
            text = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise VisionOcrError("Vision OCR did not return text content.") from exc
        return str(text).strip()


def render_pdf_pages(content: bytes, *, dpi: int, max_pages: int) -> tuple[int, list[tuple[int, bytes]]]:
    try:
        pdf = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        raise VisionOcrError("PDF inválido ou corrompido para OCR visual.") from exc

    scale = dpi / 72
    matrix = fitz.Matrix(scale, scale)
    rendered = []
    for page_index, page in enumerate(pdf, 1):
        if page_index > max_pages:
            break
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        rendered.append((page_index, pixmap.tobytes("png")))
    return len(pdf), rendered


def vision_ocr_markdown(
    content: bytes,
    *,
    client: VisionOcrClient,
    dpi: int,
    max_pages: int,
) -> str:
    total_pages, pages = render_pdf_pages(content, dpi=dpi, max_pages=max_pages)
    sections = []
    for page_number, image_png in pages:
        page_text = client.extract_page_markdown(image_png=image_png, page_number=page_number)
        if not page_text:
            page_text = "[Página sem texto legível pelo OCR visual]"
        sections.append(f"<!-- source_page: {page_number} -->\n\n{page_text}")

    if total_pages > max_pages:
        sections.append(
            "<!-- vision_ocr_warning: document_truncated -->\n\n"
            f"[OCR visual limitado às primeiras {max_pages} de {total_pages} páginas]"
        )
    return "\n\n".join(sections)


def build_vision_ocr_client(config) -> OpenAIVisionOcrClient:
    api_key = config.vision_ocr_api_key or config.groq_api_key
    return OpenAIVisionOcrClient(
        api_key=api_key,
        model=config.vision_ocr_model,
        base_url=config.vision_ocr_base_url,
        timeout_seconds=config.vision_ocr_timeout_seconds,
        max_tokens=config.vision_ocr_max_tokens,
    )
