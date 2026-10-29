"""Fail fast on configurations that would make ingestion unsafe or loop forever."""

import pytest
from pydantic import ValidationError

from netops_ai.core.settings import Settings


@pytest.mark.parametrize(
    "overrides",
    [
        {"chunk_size": 900, "chunk_overlap": 900},
        {"chunk_overlap": -1},
        {"max_upload_bytes": 0},
        {"max_pdf_pages": 0},
        {"max_extracted_chars": 0},
    ],
)
def test_invalid_limits_are_rejected(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **overrides)


def test_environment_can_configure_preview_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NETOPS_CHUNK_SIZE", "500")
    monkeypatch.setenv("NETOPS_CHUNK_OVERLAP", "50")
    monkeypatch.setenv("NETOPS_MAX_PDF_PAGES", "20")
    settings = Settings(_env_file=None)
    assert (settings.chunk_size, settings.chunk_overlap, settings.max_pdf_pages) == (500, 50, 20)
