"""Real SQLite/Qdrant integration with deterministic vectors, not a semantic benchmark."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from netops_ai.application.knowledge import COLLECTION
from netops_ai.core.settings import Settings
from netops_ai.infrastructure.embeddings import TokenEmbeddings
from netops_ai.main import create_app


class FakeEmbeddings(TokenEmbeddings):
    identity = "tests-only-v1"
    dimension = 3
    max_tokens = 128

    def count_tokens(self, text: str) -> int:
        return len(text.split()) + 2

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(text.lower().count("dhcp")), float(text.lower().count("dns")), 0.01]


@pytest.fixture
def config(tmp_path):
    return Settings(
        environment="test",
        data_dir=tmp_path / "data",
        knowledge_dir=tmp_path / "knowledge",
        model_cache_dir=tmp_path / "models",
        _env_file=None,
    )


@pytest.fixture
def app(config):
    return create_app(config, embeddings=FakeEmbeddings())


def upload(client, content, filename="rede.pdf"):
    return client.post("/api/v1/documents", files={"file": (filename, content, "application/pdf")})


def test_index_sources_duplicate_and_persistence(app, config, make_pdf):
    content = make_pdf(["DHCP concessao", "", "DNS nomes"])
    with TestClient(app) as client:
        result = upload(client, content, "../../rede.pdf")
        assert result.status_code == 200, result.text
        record = result.json()
        assert record["status"] == "indexed" and record["persisted"] is True
        assert record["duplicate"] is False
        assert record["chunk_count"] == 2 and record["page_count"] == 3
        assert record["filename"] == "rede.pdf"
        duplicate = upload(client, content, "renomeado.pdf").json()
        assert duplicate["duplicate"] is True
        assert duplicate["filename"] == "rede.pdf"
        assert len(client.get("/api/v1/documents").json()["documents"]) == 1
        assert app.state.knowledge.client.count(COLLECTION).count == 2
        hit = client.post("/api/v1/search", json={"query": "DNS", "top_k": 1}).json()
        assert hit["answer_generated"] is False
        assert hit["matches"][0]["page"] == 3
        assert hit["matches"][0]["text"] == "DNS nomes"
        assert hit["matches"][0]["document_id"] == record["document_id"]
    assert (config.knowledge_dir / f"{record['document_id']}.pdf").read_bytes() == content
    with TestClient(create_app(config, embeddings=FakeEmbeddings())) as client:
        assert upload(client, content).json()["duplicate"] is True
        assert len(client.post("/api/v1/search", json={"query": "DNS"}).json()["matches"]) == 2


def test_empty_database_does_not_load_model(config):
    with TestClient(create_app(config)) as client:
        assert client.get("/api/v1/documents").json() == {"documents": []}
        result = client.post("/api/v1/search", json={"query": "DNS"})
        assert result.status_code == 200 and result.json()["matches"] == []
    assert not config.model_cache_dir.exists()


def test_filter_limits_to_requested_document(app, make_pdf):
    with TestClient(app) as client:
        first = upload(client, make_pdf(["DHCP somente"])).json()
        upload(client, make_pdf(["DNS somente"]), "dns.pdf")
        result = client.post(
            "/api/v1/search",
            json={
                "query": "DNS",
                "document_id": first["document_id"],
            },
        ).json()
        assert len(result["matches"]) == 1
        assert result["matches"][0]["document_id"] == first["document_id"]
        missing = client.post("/api/v1/search", json={"query": "DNS", "document_id": "0" * 64})
        assert missing.json()["matches"] == []


@pytest.mark.parametrize(
    "body",
    [
        {"query": ""},
        {"query": "   "},
        {"query": "DNS", "top_k": 0},
        {"query": "DNS", "top_k": 11},
        {"query": "DNS", "document_id": "../arquivo"},
        {"query": "DNS", "unexpected": 1},
        {"query": "a" * 2001},
        {},
    ],
)
def test_search_input_validation(app, body):
    with TestClient(app) as client:
        assert client.post("/api/v1/search", json=body).status_code == 422
    assert app.state.knowledge is None


def test_query_tokens_not_silently_truncated(app, make_pdf):
    with TestClient(app) as client:
        upload(client, make_pdf(["DNS"]))
        result = client.post("/api/v1/search", json={"query": "DNS " * 130})
        assert result.status_code == 422
        assert result.json()["detail"]["code"] == "query_too_long"


def test_invalid_pdf_does_not_create_database(app, config):
    with TestClient(app) as client:
        assert upload(client, b"not-pdf").status_code == 422
    assert not config.data_dir.exists()


def test_failed_partial_index_is_hidden_and_retry_recovers(app, make_pdf, monkeypatch):
    with TestClient(app) as client:
        good = upload(client, make_pdf(["DHCP documento completo"])).json()
        service = app.state.knowledge
        original = service.store.add_texts

        def partial_failure(*, texts, metadatas, ids, **kwargs):
            original(texts[:1], metadatas[:1], ids[:1], **kwargs)
            raise RuntimeError("private-document-data-not-for-response")

        content = make_pdf(["DNS incompleto", "DNS segunda pagina"])
        monkeypatch.setattr(service.store, "add_texts", partial_failure)
        response = upload(client, content, "dns.pdf")
        assert response.status_code == 503
        assert "private-document-data" not in response.text
        assert service.client.count(COLLECTION).count == 2  # Includes a hidden orphan.
        states = client.get("/api/v1/documents").json()["documents"]
        assert {doc["status"] for doc in states} == {"indexed", "failed"}
        matches = client.post("/api/v1/search", json={"query": "DNS"}).json()["matches"]
        assert {m["document_id"] for m in matches} == {good["document_id"]}
        monkeypatch.setattr(service.store, "add_texts", original)
        assert upload(client, content).json()["status"] == "indexed"
        assert service.client.count(COLLECTION).count == 3


def test_pending_after_interruption_can_be_retried(config, make_pdf):
    content = make_pdf(["DNS nomes"])
    app = create_app(config, embeddings=FakeEmbeddings())
    with TestClient(app) as client:
        record = upload(client, content).json()
        app.state.knowledge.registry.set_status(record["document_id"], "pending")
    with TestClient(create_app(config, embeddings=FakeEmbeddings())) as client:
        assert client.post("/api/v1/search", json={"query": "DNS"}).json()["matches"] == []
        assert upload(client, content).json()["duplicate"] is False
        assert len(client.post("/api/v1/search", json={"query": "DNS"}).json()["matches"]) == 1


@pytest.mark.parametrize("change", ["chunk_size", "model"])
def test_incompatible_configuration_never_overwrites_database(config, make_pdf, change):
    with TestClient(create_app(config, embeddings=FakeEmbeddings())) as client:
        upload(client, make_pdf(["DNS"])).raise_for_status()
    embeddings = FakeEmbeddings()
    if change == "chunk_size":
        config = config.model_copy(update={"chunk_size": 700})
    else:
        embeddings.identity = "another-model-with-the-same-dimension"
    with TestClient(create_app(config, embeddings=embeddings)) as client:
        response = client.get("/api/v1/documents")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "incompatible_index"


def test_chunk_count_limit(config, make_pdf):
    config = config.model_copy(update={"max_index_chunks": 1})
    with TestClient(create_app(config, embeddings=FakeEmbeddings())) as client:
        response = upload(client, make_pdf(["DHCP", "DNS"]))
        assert response.status_code == 413
        assert client.get("/api/v1/documents").json()["documents"] == []
    assert not config.knowledge_dir.exists()


def test_concurrent_duplicates_are_serialized(app, make_pdf):
    content = make_pdf(["DHCP DNS"])
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(client, content).json(), range(2)))
        assert sorted(record["duplicate"] for record in results) == [False, True]
        assert app.state.knowledge.client.count(COLLECTION).count == 1


def test_two_process_style_clients_cannot_open_same_storage(config):
    with TestClient(create_app(config, embeddings=FakeEmbeddings())) as first:
        assert first.get("/api/v1/documents").status_code == 200
        with TestClient(create_app(config, embeddings=FakeEmbeddings())) as second:
            assert second.get("/api/v1/documents").status_code == 503
        assert first.get("/api/v1/documents").status_code == 200
