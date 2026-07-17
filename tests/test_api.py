from fastapi.testclient import TestClient

from knowledge_engineering import api
from knowledge_engineering.database import Repository


def test_upload_and_workflow(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "repository", Repository(tmp_path / "test.db"))
    client = TestClient(api.app)
    content = b"# Politica\n\nConteudo corporativo aprovado, rastreavel e suficientemente longo."
    created = client.post("/api/documents", files={"file": ("policy.md", content)})
    assert created.status_code == 201
    document = created.json()
    review = client.patch(
        f"/api/documents/{document['id']}/status", json={"status": "review"}
    )
    approved = client.patch(
        f"/api/documents/{document['id']}/status", json={"status": "approved"}
    )
    assert review.status_code == 200
    assert approved.json()["status"] == "approved"


def test_health():
    assert TestClient(api.app).get("/api/health").status_code == 200
