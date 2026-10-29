"""Small synthetic PDF fixtures; no copyrighted or private documents."""

import os
from collections.abc import Callable
from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption("--run-semantic", action="store_true", help="Executar o modelo local em cache")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if not config.getoption("--run-semantic"):
        for item in items:
            if "semantic" in item.keywords:
                item.add_marker(
                    pytest.mark.skip(reason="Use --run-semantic; exige modelo em cache.")
                )


@pytest.fixture(autouse=True)
def clean_settings_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in os.environ:
        if name.startswith("NETOPS_"):
            monkeypatch.delenv(name)


@pytest.fixture
def make_pdf() -> Callable[..., bytes]:
    def build(pages: list[str], *, encrypted: bool = False) -> bytes:
        writer = PdfWriter()
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        for text in pages:
            page = writer.add_blank_page(width=595, height=842)
            if not text:
                continue
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            lines = [f"<{line.encode('cp1252').hex()}> Tj T*" for line in text.splitlines()]
            stream = DecodedStreamObject()
            stream.set_data(("BT /F1 12 Tf 14 TL 50 780 Td " + " ".join(lines) + " ET").encode())
            # The writer's object helper is confined to test fixture construction.
            page[NameObject("/Contents")] = writer._add_object(stream)
        if encrypted:
            writer.encrypt("test-password", algorithm="RC4-128")
        output = BytesIO()
        writer.write(output)
        writer.close()
        return output.getvalue()

    return build
