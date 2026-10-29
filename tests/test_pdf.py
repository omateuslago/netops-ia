"""Extraction must retain original pages and reject unusable inputs."""

from collections.abc import Callable
from hashlib import sha256

import pytest

from netops_ai.domain.documents import DocumentError
from netops_ai.infrastructure.pdf import read_pdf

LIMITS = {"max_bytes": 10 * 1024 * 1024, "max_pages": 100, "max_chars": 250_000}


def test_text_and_original_page_numbers_survive_blank_pages(make_pdf: Callable[..., bytes]) -> None:
    content = make_pdf(
        ["Configuração DHCP\nipconfig /all", "", "Consulta DNS\nnslookup exemplo.test"]
    )
    result = read_pdf(content, "rede.pdf", **LIMITS)

    assert [page.number for page in result.pages] == [1, 2, 3]
    assert "Configuração DHCP\nipconfig /all" in result.pages[0].text
    assert result.pages[1].text == ""
    assert "Consulta DNS\nnslookup exemplo.test" in result.pages[2].text
    assert result.document_id == sha256(content).hexdigest()


def test_hash_depends_on_bytes_not_the_filename(make_pdf: Callable[..., bytes]) -> None:
    content = make_pdf(["DHCP"])
    original = read_pdf(content, "original.pdf", **LIMITS)
    renamed = read_pdf(content, "copia.pdf", **LIMITS)
    changed = read_pdf(make_pdf(["DNS"]), "original.pdf", **LIMITS)

    assert original.document_id == renamed.document_id
    assert original.document_id != changed.document_id


@pytest.mark.parametrize("filename", ["../../rede.PDF", r"C:\private\rede.PDF"])
def test_filename_does_not_expose_client_directories(
    make_pdf: Callable[..., bytes], filename: str
) -> None:
    assert read_pdf(make_pdf(["DHCP"]), filename, **LIMITS).filename == "rede.PDF"


@pytest.mark.parametrize("content", [b"", b"not a PDF", b"%PDF-1.7\nbroken content"])
def test_invalid_pdf_fails_with_public_error(content: bytes) -> None:
    with pytest.raises(DocumentError) as error:
        read_pdf(content, "rede.pdf", **LIMITS)
    assert error.value.code == "invalid_pdf"
    assert "broken content" not in str(error.value)


@pytest.mark.parametrize("filename", ["file.txt", "file.pdf.exe", ""])
def test_extension_is_validated(make_pdf: Callable[..., bytes], filename: str) -> None:
    with pytest.raises(DocumentError) as error:
        read_pdf(make_pdf(["DHCP"]), filename, **LIMITS)
    assert error.value.code == "unsupported_file"


@pytest.mark.parametrize("pages", [[], [""], ["", ""]])
def test_pdf_without_extractable_text_is_not_success(
    make_pdf: Callable[..., bytes], pages: list[str]
) -> None:
    with pytest.raises(DocumentError) as error:
        read_pdf(make_pdf(pages), "vazio.pdf", **LIMITS)
    assert error.value.code == "no_extractable_text"


def test_encrypted_pdf_is_rejected(make_pdf: Callable[..., bytes]) -> None:
    with pytest.raises(DocumentError) as error:
        read_pdf(make_pdf(["DHCP"], encrypted=True), "protected.pdf", **LIMITS)
    assert error.value.code == "encrypted_pdf"


@pytest.mark.parametrize(
    ("limit", "value", "code"),
    [
        ("max_bytes", 10, "file_too_large"),
        ("max_pages", 1, "too_many_pages"),
        ("max_chars", 4, "too_much_text"),
    ],
)
def test_processing_limits(
    make_pdf: Callable[..., bytes], limit: str, value: int, code: str
) -> None:
    limits = {**LIMITS, limit: value}
    with pytest.raises(DocumentError) as error:
        read_pdf(make_pdf(["DHCP", "DNS"]), "rede.pdf", **limits)
    assert error.value.code == code


def test_exact_size_and_text_limits_are_accepted(make_pdf: Callable[..., bytes]) -> None:
    content = make_pdf(["DHCP"])
    result = read_pdf(content, "rede.pdf", max_bytes=len(content), max_pages=1, max_chars=4)
    assert result.pages[0].text == "DHCP"
