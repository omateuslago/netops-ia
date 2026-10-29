"""Multipart upload exercises the complete PDF preview path."""

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from netops_ai.core.settings import Settings
from netops_ai.main import create_app


def settings(**overrides: object) -> Settings:
    return Settings(environment="test", _env_file=None, **overrides)


def test_preview_returns_page_sources_and_does_not_persist(
    make_pdf: Callable[..., bytes], tmp_path: Path
) -> None:
    config = settings(knowledge_dir=tmp_path / "knowledge", data_dir=tmp_path / "data")
    content = make_pdf(["DHCP\nipconfig /all", "", "DNS\nnslookup example.test"])
    with TestClient(create_app(config)) as client:
        response = client.post(
            "/api/v1/documents/preview", files={"file": ("rede.pdf", content, "application/pdf")}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "preview"
    assert data["persisted"] is False
    assert data["page_count"] == 3
    assert data["empty_pages"] == [2]
    assert data["warnings"]
    assert data["chunk_count"] == len(data["chunks"]) == 2
    assert [chunk["page"] for chunk in data["chunks"]] == [1, 3]
    assert "ipconfig /all" in data["chunks"][0]["text"]
    assert all(chunk["document_id"] == data["document_id"] for chunk in data["chunks"])
    assert not config.knowledge_dir.exists()
    assert not config.data_dir.exists()


@pytest.mark.parametrize(
    ("filename", "content", "status", "code"),
    [
        ("file.txt", b"data", 415, "unsupported_file"),
        ("file.pdf", b"not a pdf", 422, "invalid_pdf"),
        ("file.pdf", b"", 422, "invalid_pdf"),
    ],
)
def test_invalid_upload_responses(filename: str, content: bytes, status: int, code: str) -> None:
    with TestClient(create_app(settings())) as client:
        response = client.post(
            "/api/v1/documents/preview", files={"file": (filename, content, "application/pdf")}
        )
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code


def test_oversized_upload_returns_413(make_pdf: Callable[..., bytes]) -> None:
    with TestClient(create_app(settings(max_upload_bytes=100))) as client:
        response = client.post(
            "/api/v1/documents/preview", files={"file": ("file.pdf", make_pdf(["DHCP"]))}
        )
    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


@pytest.mark.parametrize(
    ("encrypted", "code"), [(False, "no_extractable_text"), (True, "encrypted_pdf")]
)
def test_unusable_pdf_returns_422(
    make_pdf: Callable[..., bytes], encrypted: bool, code: str
) -> None:
    with TestClient(create_app(settings())) as client:
        response = client.post(
            "/api/v1/documents/preview",
            files={"file": ("file.pdf", make_pdf([""], encrypted=encrypted))},
        )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == code


def test_upload_field_is_required_and_documented() -> None:
    with TestClient(create_app(settings())) as client:
        assert client.post("/api/v1/documents/preview").status_code == 422
        schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/documents/preview"]["post"]
    assert "multipart/form-data" in operation["requestBody"]["content"]


def test_chunk_configuration_is_applied(make_pdf: Callable[..., bytes]) -> None:
    with TestClient(create_app(settings(chunk_size=100, chunk_overlap=10))) as client:
        response = client.post(
            "/api/v1/documents/preview", files={"file": ("file.pdf", make_pdf(["DHCP " * 80]))}
        )
    assert response.status_code == 200
    result = response.json()
    assert result["chunk_size"] == 100
    assert result["chunk_overlap"] == 10
    assert result["chunk_count"] > 1
    assert all(len(chunk["text"]) <= 100 for chunk in result["chunks"])
