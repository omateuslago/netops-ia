"""Values exchanged between extraction, chunking and the API."""

from dataclasses import dataclass


class DocumentError(ValueError):
    """Expected input failure with a public message and a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class DocumentPage:
    number: int  # Physical PDF page, starting at 1; not the printed page label.
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    document_id: str  # SHA-256 of the original bytes, independent of filename.
    filename: str
    pages: tuple[DocumentPage, ...]


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    filename: str
    page: int
    index: int  # Starts at 0 within the page.
    text: str
