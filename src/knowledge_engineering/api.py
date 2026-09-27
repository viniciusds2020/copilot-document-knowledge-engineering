import sqlite3
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .curation import create_knowledge_pack
from .database import Repository
from .groq_client import GroqClient, GroqError
from .models import KnowledgePackRequest, PackStatusUpdate, StatusUpdate
from .pipeline import PipelineError, process
from .publishing import write_publication

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Copilot Document Knowledge Engineering", version="0.4.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
repository = Repository(settings.database_path)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "converter": settings.converter,
        "groq_configured": bool(settings.groq_api_key),
        "vision_ocr_configured": bool(
            (settings.vision_ocr_api_key or settings.groq_api_key) and settings.vision_ocr_model
        ),
    }


@app.get("/api/documents")
def list_documents():
    return repository.list()


@app.get("/api/documents/{document_id}")
def get_document(document_id: str):
    document = repository.get(document_id)
    if not document:
        raise HTTPException(404, "Documento não encontrado.")
    return document


@app.post("/api/documents", status_code=201)
async def create_document(file: UploadFile = File(...)):
    try:
        document = process(file.filename or "document", await file.read(), settings)
        repository.save(document)
        return document
    except PipelineError as exc:
        raise HTTPException(422, str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, "Este conteúdo já foi processado.") from exc


@app.patch("/api/documents/{document_id}/status")
def update_status(document_id: str, update: StatusUpdate):
    document = repository.get(document_id)
    if not document:
        raise HTTPException(404, "Documento não encontrado.")
    allowed = {
        "draft": {"review", "deprecated"},
        "review": {"draft", "approved", "deprecated"},
        "approved": {"deprecated"},
        "deprecated": set(),
    }
    if update.status not in allowed[document.status]:
        raise HTTPException(409, "Transição de status inválida.")
    if update.status == "approved" and not document.quality_passed:
        raise HTTPException(409, "Quality gate reprovado; aprovação bloqueada.")
    document.status = update.status
    repository.update(document)
    return document


@app.get("/api/knowledge-packs")
def list_knowledge_packs():
    return repository.list_packs()


@app.get("/api/knowledge-packs/{pack_id}")
def get_knowledge_pack(pack_id: str):
    pack = repository.get_pack(pack_id)
    if not pack:
        raise HTTPException(404, "Pacote de conhecimento não encontrado.")
    return pack


@app.post("/api/knowledge-packs", status_code=201)
def create_pack(request: KnowledgePackRequest):
    documents = []
    missing = []
    for document_id in request.document_ids:
        document = repository.get(document_id)
        if document:
            documents.append(document)
        else:
            missing.append(document_id)
    if missing:
        raise HTTPException(404, "Documentos não encontrados: " + ", ".join(missing))
    try:
        client = GroqClient(
            settings.groq_api_key, settings.groq_model, settings.groq_timeout_seconds
        )
        pack = create_knowledge_pack(
            documents,
            request.domain,
            request.version,
            client,
            settings.max_source_chars_per_document,
        )
        repository.save_pack(pack)
        return pack
    except (GroqError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            409, "Já existe um pacote com este domínio e versão."
        ) from exc


@app.patch("/api/knowledge-packs/{pack_id}/status")
def update_pack_status(pack_id: str, update: PackStatusUpdate):
    pack = repository.get_pack(pack_id)
    if not pack:
        raise HTTPException(404, "Pacote de conhecimento não encontrado.")
    allowed = {
        "draft": {"review", "deprecated"},
        "review": {"draft", "approved", "deprecated"},
        "approved": {"deprecated"},
        "deprecated": set(),
    }
    if update.status not in allowed[pack.status]:
        raise HTTPException(409, "Transição de status inválida.")
    if update.status == "approved" and pack.conflicts_or_gaps:
        raise HTTPException(
            409, "Pacote contém lacunas ou conflitos; aprovação bloqueada."
        )
    pack.status = update.status
    repository.update_pack(pack)
    return pack


@app.post("/api/knowledge-packs/{pack_id}/publish", status_code=201)
def publish_pack(pack_id: str):
    pack = repository.get_pack(pack_id)
    if not pack:
        raise HTTPException(404, "Pacote de conhecimento não encontrado.")
    if pack.status != "approved":
        raise HTTPException(409, "Apenas pacotes aprovados podem ser publicados.")

    documents = []
    missing = []
    for document_id in pack.source_document_ids:
        document = repository.get(document_id)
        if document:
            documents.append(document)
        else:
            missing.append(document_id)
    if missing:
        raise HTTPException(
            404, "Documentos de origem não encontrados: " + ", ".join(missing)
        )

    return write_publication(
        pack,
        documents,
        export_root=settings.publication_path,
        raw_chunk_chars=settings.raw_chunk_chars,
        raw_chunk_overlap=settings.raw_chunk_overlap,
    )
