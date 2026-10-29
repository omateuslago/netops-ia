"""Public values and expected failures of local retrieval."""

from dataclasses import dataclass

from netops_ai.domain.documents import DocumentChunk


class RetrievalError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass(frozen=True)
class IndexedDocument:
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    status: str
    created_at: str


@dataclass(frozen=True)
class SearchHit:
    chunk: DocumentChunk
    score: float
