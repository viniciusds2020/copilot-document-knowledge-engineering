import sqlite3
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Repository
from .models import StatusUpdate
from .pipeline import PipelineError, process

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Copilot Document Knowledge Engineering", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")
repository = Repository(settings.database_path)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "converter": settings.converter}


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
